from typing import TypedDict, List, Dict, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pymongo import MongoClient
import os
import uuid
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



# Step 2: Get User Input per Field
def get_user_input(state: State):
    print("Original Body:", state["original_body"])
    user_inputs = {}

    for key, value in state["original_body"].items():
        print(f"Current Field: {key}, Current Value: {value},Feedback: awaited from user")
        #generated input need resume fuction to be called via UI 
        user_feedback = interrupt( {
            "key": key, 
            "message": "provide feedback for field: " + key,
        })
        user_inputs[key] = user_feedback if user_feedback.strip() != "" else value
    return Command(goto="generate_payloads", update={"user_inputs": user_inputs})

# Step 3: Generate Similar Payloads Using LLM
def generate_payloads(state: State):
    prompt = f"""
    Given the following user input fields and values:
    {state["user_inputs"]}
    take user input and based on the user input generate the same feild based on the instruction given in user inputs
    Generate 5 variations of JSON request bodies with realistic differences but keeping the structure same.
    Output as a JSON list.
    """
    response = llm.predict(prompt)
    import json
    try:
        generated = json.loads(response)
    except json.JSONDecodeError:
        print("Failed to decode JSON from LLM response, fallback to empty list.")
        generated = []
    return Command(goto="store_payloads", update={"generated_bodies": generated})

# Step 4: Store to DB
def store_payloads(state: State):
    for body in state["generated_bodies"]:
        collection.insert_one({
            "url": "https://reqres.in/api/register",
            "method": "GET",
            "headers": {
                "Content-Type": "application/json",
                "x-api-key": "reqres-free-v1"
            },
            "body": body,
            "name": "generated_by_langgraph"
        })
    print(f"Stored {len(state['generated_bodies'])} payloads to the database.")
    return Command(goto=END)

# Build the Graph
def executeMultipleSample(request_name):
    initial_state: State = {
        "original_body": {},
    "user_inputs": {},
    "generated_bodies": [],
    "request_name": request_name
    }
    # Try loading data while catching exceptions
    try:
      command = get_user_input(initial_state)
    except ValueError as e:
      print(f"Error: {e}")

    graph = StateGraph(State)
    graph.add_node("get_user_input", get_user_input)
    graph.add_node("generate_payloads", generate_payloads)
    graph.add_node("store_payloads", store_payloads)
    graph.set_entry_point("load_data")

    graph.add_edge(START, "get_user_input")
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
    config = {"configurable": {"thread_id": "dynamic_payload_1"}}
    
    result = app.invoke(initial_state, config, stream_mode="updates")
    # for chunk in app.stream(initial_state, config=thread_config):
    #   for node_id, value in chunk.items():
    #     #  If we reach an interrupt, continuously ask for human feedback

    #     if(node_id == "__interrupt__"):
    #         while True: 
    #             user_feedback = input("Provide feedback (or type 'done' when finished to be done): ")

    #             # Resume the graph execution with the user's feedback
    #             app.invoke(Command(resume=user_feedback), config=thread_config)

    #             # Exit loop if user says done
    #             if user_feedback.lower() == "done":
    #                 break

