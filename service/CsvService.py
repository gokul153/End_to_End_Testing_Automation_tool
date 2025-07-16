import os
import pandas as pd
from pymongo import MongoClient
from service.parsecurlService import parse_curl_to_entity

class CSVService:
    def __init__(self, mongo_uri: str, db_name: str, collection_name: str):
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

    async def save_file(self, file) -> str:
        file_location = f"temp/{file.filename}"
        with open(file_location, "wb") as f:
            f.write(await file.read())
        return file_location

    def process_csv(self, file_location: str) -> None:
        df = pd.read_csv(file_location)
        for index, row in df.iterrows():
            request_id = row['request_id']  # Extract request_id
            request_name = row['request_Name']  # Extract request_Name
            curl_request = row['curl_request']  # Extract curl_request
            
            # Store the CURL request and other fields in MongoDB
            self.collection.insert_one({
                "request_id": request_id,
                "request_name": request_name,
                "curl_request": curl_request
            })
            result = parse_curl_to_entity(curl_request,request_name)


    def cleanup_file(self, file_location: str) -> None:
        os.remove(file_location)
