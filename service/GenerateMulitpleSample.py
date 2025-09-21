from typing import TypedDict, List, Dict, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pymongo import MongoClient
import os
import uuid
import json
import ast

from service.BigQueryService import BigQueryService
bq_service = BigQueryService()
load_dotenv()
# MongoDB Connection Setup
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
client = MongoClient(MONGO_URL)
db = client["gen-ai"]
collection = db["requests_entity_collection"]

# LLM Setup (using OpenAI, but can be swapped)
llm = ChatOpenAI(temperature=0.7)

class State(TypedDict):
    original_body: Dict
    user_inputs: Dict
    generated_bodies: List[Dict]
    request_name : str
    metadata: Dict  # To hold url, method, headers
# Step 1: Load Data from DB
def load_data(state: State):
    print("Loading API Request Data from Database...")
    data = collection.find_one({"name": state["request_name"]})
    if not data:
        raise ValueError("No data found")
    # Store the full original metadata (url, method, headers)
    metadata = {
        "url": data.get("url"),
        "method": data.get("method"),
        "headers": data.get("headers")
    }
    return Command(
        goto="get_user_input",
        update={"original_body": data["body"], "user_inputs": {}, "generated_bodies": [], "metadata": metadata}
    )

# Step 2: Get User Input per Field
def get_user_input(state: State):
    print("Original Body:", state["original_body"])
     # Always start from previously collected user inputs
    user_inputs = state.get("user_inputs", {}).copy()
    SPECIAL_FIELDS = {"hospital", "doctor", "billing Amount"}
     # Track progress: which fields have been processed
    processed_keys = set(user_inputs.keys())
    # Find the next unprocessed field
    next_field = None
    for key in state["original_body"].keys():
        if key not in processed_keys:
            next_field = key
            break

    # If no more fields left → move to generate_payloads
    if not next_field:
        return Command(goto="generate_payloads", update={"user_inputs": user_inputs})
    
    print(f"Current Field: {next_field}, Current Value: {state['original_body'][next_field]}")

    # Handle special fields via BigQuery auto-fill
    print(next_field.lower() + " Next Feild")
    print(SPECIAL_FIELDS + " special_feilds")
    if next_field.lower() in SPECIAL_FIELDS:
        try:
            rows = bq_service.get_hospitals(next_field)  # returns List[Dict]
            if rows:
                sample_values = [list(r.values())[0] for r in rows if r]
                user_inputs[next_field] = sample_values
                print(f"Auto-filled '{next_field}' with {len(sample_values)} values from BigQuery")
                # Immediately call get_user_input again to continue with next field
                return Command(goto="get_user_input", update={"user_inputs": user_inputs})
        except Exception as e:
            print(f"BigQuery failed for {next_field}: {e}. Falling back to user interrupt.")

    # Otherwise: pause and ask the user
    return interrupt({
        "key": next_field,
        "message": "Provide feedback for field: " + next_field,
    })


# Step 3: Generate Similar Payloads Using LLM
def generate_payloads(state: State):
    print("Generating Payloads with LLM...")
    prompt_parts = []
    for field, instruction in state["user_inputs"].items():
        if instruction.strip():
            prompt_parts.append(f"- Field `{field}`: {instruction}")
    prompt = f"""
    You are given an original JSON request body with fields and instructions for how to vary them:
     Original body:
    {state["original_body"]}
    Instructions for variations:
    {chr(10).join(prompt_parts)}
     Using this, generate 5 new JSON request bodies with variations as per the instructions, but keeping the structure the same. Output a JSON array only.
     ❗ Return **only** a strict JSON array of objects. Use **double quotes**, no comments, no trailing commas.
     """
    response = llm.predict(prompt)
    
    try:
       response_fixed = response.replace("'", '"')
       #generated = json.loads(response_fixed)
       generated = ast.literal_eval(response)
       if not isinstance(generated, list):
            raise ValueError("Expected a list of payloads")
    except Exception as e:
        print("❌ Failed to parse LLM output:", e)
        generated = []
    return Command(goto="store_payloads", update={"generated_bodies": generated})

# Step 4: Store to DB
def store_payloads(state: State):
    print(f"💾 Storing {len(state['generated_bodies'])} payloads to the DB...")
    for body in state["generated_bodies"]:
        collection.insert_one({
           "url": state["metadata"]["url"],
            "method": state["metadata"]["method"],
            "headers": state["metadata"]["headers"],
            "body": body,
            "name":   state["request_name"] +"_generated_by_langgraph"
        })
    print(f"Stored {len(state['generated_bodies'])} payloads to the database.")
    return Command(goto=END)

# Build the Graph
def executeMultipleSample(request_name):
    initial_state: State = {
        "original_body": {},
        "user_inputs": {},
        "generated_bodies": [],
        "request_name": request_name,
        "metadata": {}
    }

    # Try loading data while catching exceptions
    try:
      command = load_data(initial_state)
    except ValueError as e:
      print(f"Error: {e}")

    graph = StateGraph(State)
    graph.add_node("load_data", load_data)
    graph.add_node("get_user_input", get_user_input)
    graph.add_node("generate_payloads", generate_payloads)
    graph.add_node("store_payloads", store_payloads)
    graph.set_entry_point("load_data")

    graph.add_edge(START, "load_data")
    graph.add_edge("load_data", "get_user_input")
    graph.add_edge("get_user_input", "generate_payloads")
    graph.add_edge("generate_payloads", "store_payloads")
    graph.add_edge("store_payloads", END)
    # Compile the application
    from langgraph.checkpoint.memory import MemorySaver
    memory = MemorySaver()
    app = graph.compile(checkpointer=memory)
    thread_config = {"configurable": {
    "thread_id": uuid.uuid4()
     }}
    # Example Run
     # config = {"configurable": {"thread_id": "dynamic_payload_1"}}
    
    # result = app.invoke(initial_state, config, stream_mode="updates")
    for chunk in app.stream(initial_state, config=thread_config):
      for node_id, value in chunk.items():
        #  If we reach an interrupt, continuously ask for human feedback

        if(node_id == "__interrupt__"):
            key = value.get("key")
            while True: 
                 
                 user_feedback = input(f"Feedback for {key} (or type 'done'): ")
                 if user_feedback.lower() == "done":
                   break

                

                 # Resume execution at get_user_input again
                 app.invoke(Command(resume={"user_inputs": new_inputs}), config=thread_config)
            break

