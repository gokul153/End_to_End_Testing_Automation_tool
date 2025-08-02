import requests
import json
from pymongo import MongoClient
from model.response.TriggerResponse import TriggerResponse
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
import os
from dotenv import load_dotenv
from langchain_community.document_loaders import JSONLoader
# MongoDB connection setup
client = MongoClient('mongodb://localhost:27017/')  # Replace with your MongoDB URI
db = client['gen-ai']  
collection = db['response-logging']  

def save_trigger_response(trigger_response: TriggerResponse):
    # Convert the Pydantic model to a dictionary
    response_dict = trigger_response.dict(by_alias=True)
    
    # Insert the document into MongoDB
    result = collection.insert_one(response_dict)
    ## Attempting to store the same to the vector data base 
    # Load environment variables from .env
    docs = [
        Document(
            page_content=str(trigger_response.response),
            metadata={
               "type": "response",
               "request_key": trigger_response.request_key,
               "request_name": trigger_response.request_name,
               "error_code": trigger_response.error_code,
               "duration_ms": trigger_response.duration_ms,
               "timestamp": trigger_response.timestamp,
               "method": trigger_response.method,
               "url": trigger_response.url
            }
        ),
        Document(
            page_content=trigger_response.request_name,
            metadata={
                "type": "request_name",
                "request_key": trigger_response.request_key,
                "timestamp": trigger_response.timestamp
            }
        ),
        Document(
            page_content=str(trigger_response.error_code),
            metadata={
                "type": "error_code",
                "request_key": trigger_response.request_key
            }
        ),
          Document(
        page_content=f"Duration: {trigger_response.duration_ms} ms",
        metadata={
            "type": "duration",
            "request_key": trigger_response.request_key,
            "timestamp": trigger_response.timestamp
        }
    )
    ]

    load_dotenv()
    embedding_function = OpenAIEmbeddings()
    db = Chroma.from_documents(docs, embedding_function)
    return db._collection.get()["ids"]  # Or use db.add_documents() and track IDs if using persistent DB
 