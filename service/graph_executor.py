from typing import TypedDict, List, Dict, Literal, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pymongo import MongoClient
import os
import uuid
import json
import ast

from langgraph.checkpoint.memory import MemorySaver
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
    current_field_index: Optional[int]
# Step 1: Load Data from DB
async def load_data(state: State):
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
async def get_user_input(state: State):
    original_body = state["original_body"]
    field_keys = list(original_body.keys())

    index = state.get("current_field_index", 0)
    # If all fields are processed, go to generate step
    if index >= len(field_keys):
        return Command(goto="generate_payloads")

    current_key = field_keys[index]
    current_value = original_body[current_key]

    # Ask for feedback on current field
    user_feedback = interrupt({
        "key": current_key,
        "message": f"Provide feedback for field: {current_key}"
    })

    # After resuming, store the feedback
    state["user_inputs"][current_key] = user_feedback or current_value

    # Move to next field
    return Command(
        goto="get_user_input",
        update={
            "user_inputs": state["user_inputs"],
            "current_field_index": index + 1
        }
    )

# Step 3: Generate Similar Payloads Using LLM
async def generate_payloads(state: State):
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
     Using this, generate 3 new JSON request bodies with variations as per the instructions, but keeping the structure the same. Output a JSON array only.
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
async def store_payloads(state: State):
    print(f"💾 Storing {len(state['generated_bodies'])} payloads to the DB...")
    for body in state["generated_bodies"]:
        collection.insert_one({
           "url": state["metadata"]["url"],
            "method": state["metadata"]["method"],
            "headers": state["metadata"]["headers"],
            "body": body,
            "name":   state["request_name"] ,
            "generated_by": "ai_agent",
            "request_key": state["request_name"] + "_" + str(uuid.uuid4())  # Unique key for each request
        })
    print(f"Stored {len(state['generated_bodies'])} payloads to the database.")
    return Command(goto=END)
# Class to manage sessions
class LangGraphRunner:
    def __init__(self):
        self.graph = self._build_graph()
        self.memory = MemorySaver()
        self.app = self.graph.compile(checkpointer=self.memory)
        self.thread_map = {}  # Stores sessions by thread_id

    def _build_graph(self):
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
        return graph

    async def start(self, request_name: str, thread_id: str):
        state: State = {
            "original_body": {},
            "user_inputs": {},
            "generated_bodies": [],
            "request_name": request_name,
            "metadata": {}
        }
        config = {"configurable": {"thread_id": thread_id}}
        return self.app.astream(state, config=config)

    async def resume(self, thread_id: str, feedback: str):
        command = Command(resume=feedback)
        config = {"configurable": {"thread_id": thread_id}}
        return self.app.astream(command, config=config)
# Build the Graph
