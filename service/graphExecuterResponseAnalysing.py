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
import json

load_dotenv()
llm = ChatOpenAI()
class State(TypedDict):
    original_response: Dict[str, Any]   # Original response from Agent 1
    previous_responses: List[TriggerResponse]  # List of previous responses
    new_response_trigger: bool                  # Whether a new response is received
    user_inputs: Any        # User-defined monitored/ignored fields  ## need to ccnge this to Dict[str, Any] for more flexibility
    request_name: str                   # Name or label of the request
    metadata: Dict[str, Any]            # URL, headers, method, etc.
    current_field_index: Optional[int]  # For iterating through fields
    trigger_response: Optional[TriggerResponse]  # Response from the triggered request
    vector_ids: Optional[List[str]]
    user_feedback_needed_fields:  Optional[List[str]]
    response_count: int = 0  # Counter for the number of responses received
    total_responses: int = 0  # Total number of responses to process



# Step 1: Trigger the request and get the response 
def trigger_request(state: State) -> Command:
    print("Triggering request and getting response...")
    # Simulate triggering the request and getting a response
    responses: List[TriggerResponse] = []
    request_entities = list(load_request_entity_from_db(state["request_name"]))
    total_response_count = len(request_entities)
    state["total_responses"] = total_response_count
    
    for index, entity in enumerate(request_entities):
        if index < state["response_count"]: 
            # Skip already processed responses
            print(f"Skipping already processed response for entity: {entity['name']}+ {index}")
            continue
        print(f"Total responses to process: {total_response_count} and current executing response: {index + 1 }")
      
      
        # if state["new_response_trigger"]:
        #     response_dict = json.loads(trigger_response.response)
        #      # Get the field keys
        #     field_keys = list(response_dict.keys())
        #     state["original_response"] = response_dict
        #     state["response_count"] += 1
        #     return Command(
        #     goto="get_user_input",
            
        #     update={"original_response": response_dict, "user_inputs": {}, "generated_bodies": [],
        #             "previous_responses": [], "trigger_response": trigger_response,"new_response_trigger":False,
        #             "response_count": state["response_count"],"total_responses": state["total_responses"],
        #             "user_feedback_needed_fields":field_keys, "request_name": entity["name"]})
        #     ## get needed feilds from the response from user to get into a interupt
        if state["response_count"] < total_response_count:
            trigger_response = hit_individual_request(entity)
            response_dict = json.loads(trigger_response.response)
            state["original_response"] = response_dict
            state["response_count"] += 1
             # Get the field keys
            field_keys = list(response_dict.keys())
            return Command(
            goto="get_user_input",
            update={"original_response": response_dict, "user_inputs": {}, "generated_bodies": [],"previous_responses": [],
                    "response_count": state["response_count"],"total_responses": state["total_responses"], "user_feedback_needed_fields":field_keys,
                     "trigger_response": trigger_response,"request_name": entity["name"]})
        else:
            print("No more responses to process.")
            return Command(goto="generate_report", update={"trigger_response": state["trigger_response"],
                             "response_count": state["response_count"], "request_name": state["request_name"], "total_responses": state["total_responses"]})
## get user feed back on the response if the resposne is new or it its for the first time
# 
def get_user_input(state: State):
    print("Getting user input for response fields...")
    request_name = state["request_name"]
    original_response = state["original_response"]
   
    client = MongoClient("mongodb://localhost:27017")
    db = client["gen-ai"]
    collection = db["response-monitering-feild-logs"]
   
    currentResponse = state["trigger_response"].response
    config = collection.find_one({"request_name": request_name,
                                  "response_preview": str(original_response)})

    if config:
        print("Configuration found in DB:", config)
        monitored = list(config.get("monitored_fields", []))
        ignored = list(config.get("ignored_fields", []))
        total_configured_fields = monitored + ignored
        return Command(
                update={
                    "user_inputs": {
                        "monitored_fields": list(monitored),
                        "ignored_fields": list(ignored)
                    },"response_count": state["response_count"],"total_responses": state["total_responses"]
                },
                goto="store_to_vector_db"
            )
    else:
        print("No configuration found in DB, asking user to select fields...")
        # 1. If no config, ask user to select fields
        field_keys = list(original_response.keys())
        print("Getting user input for response fields..."+ str(field_keys))
        # 2. If user feedback is empty, use all fields
        user_feedback = interrupt({
          "key": state["user_feedback_needed_fields"],
          "message": f"Provide feedback for fields: {', '.join(state['user_feedback_needed_fields'])}",
      })
       # After resuming, store the feedback
        state["user_inputs"] = user_feedback or {}
        userInput = state["user_inputs"]
        if not userInput:
           print("No user input received, using default fields.")
        else:
            print("User input received:", userInput)

        monitored_fields = userInput
        ignored_fields =[field for field in field_keys if field not in monitored_fields]
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

        return Command(
        update={
            "user_inputs": {
                "monitored_fields": monitored_fields,
                "ignored_fields": ignored_fields
            },
            "current_field_index": None,
            "response_count": state["response_count"],
            "total_responses": state["total_responses"],
            "trigger_response": state["trigger_response"],
            "request_name": state[request_name]

        },
        goto="store_to_vector_db"
        )

# Step 3: Store the response to vector DB
def store_to_vector_db(state: State):
    trigger_response = state.get("trigger_response")
    if not trigger_response:
        raise ValueError("No trigger_response found in state")
    # Save to MongoDB and vector DB
    vector_ids = save_trigger_response(trigger_response,state["user_inputs"])
    if "vector_ids" not in state:
        state["vector_ids"] = []

    # Append new vector_ids (can be list or single ID)
    if isinstance(vector_ids, list):
        state["vector_ids"].extend(vector_ids)
    else:
        state["vector_ids"].append(vector_ids)
    ## to do if the count of responses is less than the total responses
    if state["response_count"] < state["total_responses"]:
        return Command(
            goto="trigger_request",
            update={"new_response_trigger": False,
                "response_count": state["response_count"],
                "request_name": state["request_name"],
                "total_responses": state["total_responses"],
                "vector_ids": state["vector_ids"]}
        )
    else:
        print("All responses processed, generating report...")
        # Generate the report based on the stored responsesf
        print("ideally this should be the last step")
        print("No more responses to process.")
        return Command(goto="generate_report", update={"vector_ids": vector_ids,"request_name": state["request_name"], "total_responses": state["total_responses"]})

# Step 4: Generate a report based on the response
def generate_report(state: State):
    print("Generating report based on the response...")
    persist_dir = "./chroma_db"
    embedding_function = OpenAIEmbeddings()
    chroma_collection = Chroma(persist_directory=persist_dir, embedding_function=embedding_function)
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
    print("Reconstructing grouped data by request_key...", grouped_docs)
    grouped_data = defaultdict(dict)
    for doc, meta in grouped_docs:
      request_key = meta.get("request_key")
      doc_type = meta.get("type")
    
      if not request_key or not doc_type:
        print(f"Skipping doc due to missing request_key or type in metadata: {meta}")
        continue  # Skip malformed docs

      grouped_data[request_key][doc_type] = {
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
    print("Generated report:", result)
    # Step 7: Optionally save or return
    state["report"] = result.dict()
    return Command(goto=END)

class LangGraphRunnerResponseAnalyser:
    def __init__(self):
        self.memory = MemorySaver()
        self.graph = self._build_graph()
        self.app = self.graph.compile(checkpointer=self.memory)
       

    def _build_graph(self):
         graph = StateGraph(State)

          # Register nodes
         graph.add_node("trigger_request", trigger_request)
         graph.add_node("get_user_input", get_user_input)
         graph.add_node("store_to_vector_db", store_to_vector_db)
         graph.add_node("generate_report",generate_report)  # Final state ends

         # Define entry and transitions
         graph.set_entry_point("trigger_request")
         graph.add_edge(START, "trigger_request")
         graph.add_edge("trigger_request", "get_user_input")
         graph.add_edge("get_user_input", "store_to_vector_db")
         graph.add_edge("store_to_vector_db", "generate_report")
         graph.add_edge("generate_report", END)
         # Add edges
         graph.set_entry_point("trigger_request")

         graph.add_edge("trigger_request", "get_user_input")
         graph.add_edge("get_user_input", "store_to_vector_db")
         graph.add_edge("store_to_vector_db", "generate_report")

        # Define exit
         graph.set_finish_point("generate_report")

        
         return graph
         

    async def start_response(self, request_name: str, thread_id: str):
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
           "vector_ids": [],
           "user_feedback_needed_fields": [],
           "response_count": 0,
           "total_responses": 0
       }


        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }

        # Start streaming with initial state
        return self.app.astream(state, config=config)

    async def resume_response(self, thread_id: str, fields: list):
        # Resume execution using a Command object with user feedback
        command = Command(resume=fields)

        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }

        # Resume streaming based on thread ID
        return self.app.astream(command, config=config)

