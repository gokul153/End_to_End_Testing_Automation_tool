import requests
import json
from pymongo import MongoClient
from model.response.TriggerResponse import TriggerResponse
from service.SaveResponseToDb import save_trigger_response
# MongoDB connection details
mongo_uri = "mongodb://localhost:27017/"  # Adjust based on your database location
db_name = "gen-ai"  # Replace with your database name
collection_name = "requests_entity_collection"


def load_request_entity_from_db(name: str):
    client = MongoClient(mongo_uri)
    db = client[db_name]
    collection = db[collection_name]
    # Find the request entity by name
    request_entity = collection.find_one({"name": name})
    # Close the client
    client.close()
    if request_entity:
        return request_entity
    else:
        print(f"No request entity found with name: {name}")
        return None
    
def make_api_call(name:str):
    # Extract url, method, headers, and body from the request entity
    request_entity = load_request_entity_from_db(name)
    url = request_entity['url']
    method = request_entity['method'].upper()
    headers = request_entity['headers']
    body = request_entity.get('body', {})
    
    # Ensure body is a JSON string for application/json content type
    if headers.get('Content-Type') == 'application/json':
        body = json.dumps(body)
        triggerResponse = TriggerResponse()
    # Perform the API call based on the method
    try:
        if method == 'POST':
            response = requests.post(url, headers=headers, data=body)
        elif method == 'GET':
            response = requests.get(url, headers=headers)
        elif method == 'PUT':
            response = requests.put(url, headers=headers, data=body)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers)
        else:
            raise ValueError("HTTP method not supported")
        
        # Print status code and response content
        triggerResponse.error_code = response.status_code
        triggerResponse.response = response.text
        triggerResponse.request_name = name
        print(f'Status Code: {response.status_code}')
        print(f'Response: {response.text}')
        save_trigger_response(triggerResponse)
        return triggerResponse
    except Exception as e:
        print(f'Error during API call: {str(e)}')    