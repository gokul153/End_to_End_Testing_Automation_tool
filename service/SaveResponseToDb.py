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

def save_trigger_response(trigger_response: TriggerResponse, user_inputs: list = None):
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
    ),
      Document(
        page_content=f"User has given feed back based on the response it includes which of the feilds are to be monitered:  {user_inputs}",
        metadata={
            "type": "user_feedback",
            "request_key": trigger_response.request_key,
            "timestamp": trigger_response.timestamp
        }
    )
    ]

    load_dotenv()
    embedding_function = OpenAIEmbeddings()
    persist_dir = "./chroma_db"  # Set persistent directory

    # 4. Initialize or load the persistent Chroma DB
    if os.path.exists(persist_dir):
      # Load existing store
      db = Chroma(persist_directory=persist_dir, embedding_function=embedding_function)
    else:
       # First-time init with new docs
      db = Chroma.from_documents(docs, embedding_function, persist_directory=persist_dir)

     # 5. Add new documents to the store
      db.add_documents(docs)

     # 6. Persist to disk
      db.persist()

     # 7. Return document IDs
      return db._collection.get()["ids"]