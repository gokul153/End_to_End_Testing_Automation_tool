import requests
import json
from pymongo import MongoClient
from model.response.TriggerResponse import TriggerResponse
from service.SaveResponseToDb import save_trigger_response
from typing import List
from datetime import datetime
import time
import uuid
# MongoDB connection details
mongo_uri = "mongodb://localhost:27017/"  # Adjust based on your database location
db_name = "gen-ai"  # Replace with your database name
collection_name = "requests_entity_collection"


def load_request_entity_from_db(name: str):
    client = MongoClient(mongo_uri)
    db = client[db_name]
    collection = db[collection_name]
    # Find the request entity by name
    request_entity = collection.find({"name": name})
    # Close the client
    if request_entity:
        return request_entity
    else:
        print(f"No request entity found with name: {name}")
        return None
    
def make_api_call(name:str):
    # Extract url, method, headers, and body from the request entity
    responses: List[TriggerResponse] = []
    request_entities = load_request_entity_from_db(name)
    for entity in request_entities:
        url = entity["url"]
        method = entity["method"].upper()
        headers = entity.get("headers", {})
        body = entity.get("body", {})
        request_key = entity.get("request_key", None)
        # Convert body to JSON string if needed
        if headers.get("Content-Type") == "application/json":
            body = json.dumps(body)
    
        trigger_response = TriggerResponse()
        start_time = time.time()
    
        try:
            if method == "POST":
                response = requests.post(url, headers=headers, data=body)
            elif method == "GET":
                response = requests.get(url, headers=headers)
            elif method == "PUT":
                response = requests.put(url, headers=headers, data=body)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers)
            else:
                raise ValueError(f"HTTP method '{method}' not supported")
            duration_ms = int((time.time() - start_time) * 1000)
    
            # Store response info
            trigger_response.error_code = response.status_code
            trigger_response.response = response.text
            trigger_response.request_name = entity["name"]
            trigger_response.request_key = request_key
            trigger_response.duration_ms = duration_ms
            trigger_response.timestamp = datetime.now(datetime.timezone.utc).isoformat()
            trigger_response.method = method
            trigger_response.url = url
    
            print(f"📡 {method} {url}")
            print(f"🔢 Status Code: {response.status_code}")
            print(f"📨 Response: {response.text}")
        except Exception as e:
            trigger_response.error_code = 500
            trigger_response.response = str(e)
            trigger_response.request_name = entity["name"]
            print(f"❌ Error triggering request: {e}")
            trigger_response.request_name = entity["name"]
            print(f"❌ Error triggering request: {e}")

        save_trigger_response(trigger_response)
        responses.append(trigger_response)
    return responses

def hit_individual_request(entity: any):
    url = entity["url"]
    method = entity["method"].upper()
    headers = entity.get("headers", {})
    body = entity.get("body", {})
    request_key = entity.get("request_key", None)
    start_time = time.time()
    # Convert body to JSON string if needed
    if headers.get("Content-Type") == "application/json":
        body = json.dumps(body)

        trigger_response = TriggerResponse()

        try:
            if method == "POST":
                response = requests.post(url, headers=headers, data=body)
            elif method == "GET":
                response = requests.get(url, headers=headers)
            elif method == "PUT":
                response = requests.put(url, headers=headers, data=body)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers)
            else:
                raise ValueError(f"HTTP method '{method}' not supported")
            duration_ms = int((time.time() - start_time) * 1000)

            # Store response info
            trigger_response.error_code = response.status_code
            trigger_response.response = response.text
            trigger_response.request_name = entity["name"]
            trigger_response.request_key = request_key
            trigger_response.duration_ms = duration_ms
            trigger_response.timestamp = datetime.utcnow().isoformat()
            trigger_response.method = method
            trigger_response.url = url

            print(f"📡 {method} {url}")
            print(f"🔢 Status Code: {response.status_code}")
            print(f"📨 Response: {response.text}")
        except Exception as e:
            trigger_response.error_code = 500
            trigger_response.response = str(e)
            trigger_response.request_name = entity["name"]
            print(f"❌ Error triggering request: {e}")
        return trigger_response   
            