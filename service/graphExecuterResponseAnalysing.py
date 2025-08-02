from typing import TypedDict, List, Dict, Literal, Optional,Any
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pymongo import MongoClient
import os
import uuid
import json
import ast
from service.hitRequestService import load_request_entity_from_db,hit_individual_request
from langgraph.checkpoint.memory import MemorySaver
from model.response.TriggerResponse import TriggerResponse
from service.SaveResponseToDb import save_trigger_response
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from model.response.LLmReportResponse import InsightResult
from collections import defaultdict
from langchain_core.language_models import BaseChatModel
# === Build the graph ===
from langgraph.graph import StateGraph

load_dotenv()
llm = ChatOpenAI()
class State(TypedDict):
    original_response: Dict[str, Any]   # Original response from Agent 1
    previous_responses: List[TriggerResponse]  # List of previous responses
    new_response_trigger: bool                  # Whether a new response is received
    user_inputs: Dict[str, Any]         # User-defined monitored/ignored fields
    request_name: str                   # Name or label of the request
    metadata: Dict[str, Any]            # URL, headers, method, etc.
    current_field_index: Optional[int]  # For iterating through fields
    trigger_response: Optional[TriggerResponse]  # Response from the triggered request
    vector_ids: Optional[List[str]]



# Step 1: Trigger the request and get the response 
def trigger_request(state: State):
    print("Triggering request and getting response...")
    # Simulate triggering the request and getting a response
    responses: List[TriggerResponse] = []
    request_entities = load_request_entity_from_db(state["request_name"])
    first_time = True
    for entity in request_entities:
        trigger_response = hit_individual_request(entity)
        if first_time:
            state["original_response"] = trigger_response.response
            first_time = False
            return Command(
            goto="get_user_input",
            update={"original_response": trigger_response.response, "user_inputs": {}, "generated_bodies": [],"previous_responses": [], "trigger_response": trigger_response, "request_name": entity["name"]})
            ## get needed feilds from the response from user to get into a interupt
        else :
            ## if the response is same as previous one then skip it just check the fields
            ## need to do 
              return Command(
            goto="store_response",
            update={"original_response": trigger_response.response, "user_inputs": {}, "generated_bodies": [],"previous_responses": [], "trigger_response": trigger_response,"request_name": entity["name"]})
     
## get user feed back on the response if the resposne is new or it its for the first time
# 
def get_user_input(state: State):
    request_name = state["request_name"]
    original_response = state["original_response"]
    field_keys = list(original_response.keys())
    index = state.get("current_field_index", 0)
      # If all fields are processed, go to generate step
    if index >= len(field_keys):
        return Command(goto="store_response",
                       update={"user_inputs": state["user_inputs"], "current_field_index": None})
    
    ## need to store the user input with request name and field name list because we need to use it later       
    client = MongoClient("mongodb://localhost:27017")
    db = client["gen-ai"]
    collection = db["response-monitering-feild-logs"]

    config = collection.find_one({"request_name": request_name})

    if config:
        print("Configuration found in DB:", config)
        monitored = set(config.get("monitored_fields", []))
        ignored = set(config.get("ignored_fields", []))
        total_configured_fields = monitored.union(ignored)

        current_field_set = set(field_keys)

        # 3. If the set of fields exactly matches, use saved config and skip interrupt
        if current_field_set == total_configured_fields:
            return Command(
                update={
                    "user_inputs": {
                        "monitored_fields": list(monitored),
                        "ignored_fields": list(ignored)
                    }
                },
                goto="store_to_vector_db"
            )

    # 4. Else, raise an interrupt for human-in-the-loop UI with field payload
    userInput = interrupt(
        name="field_selector_ui",
        args={
            "request_name": request_name,
            "fields": field_keys,
            "response_preview": str(original_response)
        }
    )     
    if not userInput:
        print("No user input received, using default fields.")
    monitored_fields = userInput.get("monitored_fields", [])
    ignored_fields = userInput.get("ignored_fields", [])
    collection.update_one(
        {"request_name": request_name},
        {
            "$set": {
                "request_name": request_name,
                "response_preview": str(original_response),
                "monitored_fields": monitored_fields,
                "ignored_fields": ignored_fields
            }
        },
        upsert=True
    )

    # state["user_inputs"] = {
    #     "monitored_fields": userInput.get("monitored_fields", []),
    #     "ignored_fields": userInput.get("ignored_fields", [])
    # }
    return Command(
        update={
            "user_inputs": {
                "monitored_fields": monitored_fields,
                "ignored_fields": ignored_fields
            },
            "current_field_index": None
        },
        goto="store_to_vector_db"
    )

# Step 3: Store the response to vector DB
def store_to_vector_db(state: State):
    trigger_response = state.get("trigger_response")

    if not trigger_response:
        raise ValueError("No trigger_response found in state")

    # Save to MongoDB and vector DB
    vector_ids = save_trigger_response(trigger_response)
    return Command(goto="report_generator", update={"vector_ids": vector_ids})

# Step 4: Generate a report based on the response
def generate_report(state: dict, chroma_collection, llm: BaseChatModel):
    print("Generating report based on the response...")
    # Here you can implement the logic to generate a report based on the response
    results = chroma_collection.get(
    where={"request_name": state["request_name"]},
    include=["metadatas", "documents"]
   )

    grouped_docs = sorted(
    zip(results["documents"], results["metadatas"]),
    key=lambda x: x[1].get("timestamp", 0)
    )
    # Step 2: Group by request_key
   # Step 3: Reconstruct grouped data by request_key
    grouped_data = defaultdict(dict)
    for doc, meta in grouped_docs:
        grouped_data[meta["request_key"]][meta["type"]] = {
            "content": doc,
            "meta": meta
        }

  # Step 4: Construct text prompt for LLM
    doc_summaries = "\n\n".join([
        f"Timestamp: {meta['timestamp']}, Error: {meta.get('error_code')}, Duration: {meta.get('duration_ms')}ms\nResponse: {doc}"
        for doc, meta in grouped_docs
    ])
    prompt = f"""
    You are an observability expert and automatic tester. Given the following historical API responses for the request named '{state["request_name"]}', identify:

    1. Changes between each response version.
    2. Any anomaly in duration or errors.
    3. What fields have changed over time.
    4. Overall trend in response similarity.
    5. Give a score from 1 to 10 on how stable the API is based on these responses.
    6. Note any error trends or patterns.

    Respond using the structured schema.
    
   API Responses:
   {doc_summaries}
"""
   # Step 5: Create structured LLM wrapper
    structured_llm = llm.with_structured_output(InsightResult)

    # Step 6: Generate the structured report
    result: InsightResult = structured_llm.invoke({"input": prompt})

    # Step 7: Optionally save or return
    state["report"] = result.dict()
    return state
class LangGraphRunnerResponseAnalyser:
    def __init__(self):
        self.memory = MemorySaver()
        self.graph = self._build_graph()
        self.app = self.graph.compile(checkpointer=self.memory)
        self.thread_map = {}  # Optional: can be used to track thread states

    def _build_graph(self):
         graph = StateGraph(State)

          # Register nodes
         graph.add_node("trigger_request", trigger_request)
         graph.add_node("get_user_input", get_user_input)
         graph.add_node("store_to_vector_db", store_to_vector_db)
         graph.add_node("report_generator", lambda state: Command(END))  # Final state ends

         # Define entry and transitions
         graph.set_entry_point("trigger_request")
         graph.add_edge(START, "trigger_request")
         graph.add_edge("trigger_request", "get_user_input")
         graph.add_edge("get_user_input", "store_to_vector_db")
         graph.add_edge("store_to_vector_db", "report_generator")
         graph.add_edge("report_generator", END)
         # Add edges
         graph.set_entry_point("trigger_request")

         graph.add_edge("trigger_request", "get_user_input")
         graph.add_edge("get_user_input", "store_to_vector_db")
         graph.add_edge("store_to_vector_db", "report_generator")

        # Define exit
         graph.set_finish_point("report_generator")

         # Build the graph
         graph = graph.compile()
         

    async def start(self, request_name: str, thread_id: str):
        # Initial state for the graph execution
        state: State = {
            "request_name": request_name,
            "original_response": {},
            "previous_responses": [],
            "new_response_trigger": True,
            "user_inputs": {},
           "metadata": {},
           "current_field_index": 0,
           "trigger_response": None,
           "vector_ids": []
       }


        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }

        # Start streaming with initial state
        return self.app.astream(state, config=config)

    async def resume(self, thread_id: str, feedback: str):
        # Resume execution using a Command object with user feedback
        command = Command(resume=feedback)

        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }

        # Resume streaming based on thread ID
        return self.app.astream(command, config=config)

