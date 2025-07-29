import requests
import json
from pymongo import MongoClient
from model.response.TriggerResponse import TriggerResponse
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
    # Dynamic Extraction of the Transactions Field
    response = trigger_response.response
    data_field = "data"
    transaction_field = "transactions"

    if data_field in response:
       transactions = response[data_field].get(transaction_field, [])
    else:
       transactions = []

    # Step 1: Display Available Fields
    available_fields = set()
    if transactions:
       for transaction in transactions:
         available_fields.update(transaction.keys())

    print("Available fields:")
    for index, field in enumerate(available_fields, start=1):
      print(f"{index}. {field}")

    # Step 2: Take User Input for Fields
    field_selection = input("Please enter the numbers of the fields you wish to extract, separated by commas (e.g., 1,3): ")
    selected_indices = [int(i.strip()) for i in field_selection.split(",")]

    # Map field index back to field names
    selected_fields = list(available_fields)
    user_selected_fields = [selected_fields[i - 1] for i in selected_indices if 0 < i <= len(selected_fields)]

    
    
    # Optionally, return the insertion result or the created ID
    return result.inserted_id

