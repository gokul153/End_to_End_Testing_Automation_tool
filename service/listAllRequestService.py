import requests
import json
from pymongo import MongoClient
from typing import List
mongo_uri = "mongodb://localhost:27017/"  # Adjust based on your database location
db_name = "gen-ai"  # Replace with your database name
collection_name = "requests_entity_collection"

class RequestEntity:
    def __init__(self, method: str = "GET", url: str = "", headers: dict = None, data: str = None,name : str =None, body: dict = None):
        self.method = method
        self.url = url
        self.headers = headers if headers is not None else {}
        self.data = data 
        self.name = name
        self.body = body if body is not None else {}

    def __repr__(self):
        return f"RequestEntity(method='{self.method}', url='{self.url}', headers={self.headers}, data='{self.data}')"

def readallRequest(requestname: str) -> list[RequestEntity]:
      client = MongoClient(mongo_uri)
      db = client[db_name]
      collection = db[collection_name]
      if requestname:
          query = {"name": requestname}
      else:
          query = {}    
      documents = []
      for document in collection.find(query):
        document.pop('_id', None)
        documents.append(RequestEntity(**document))
      client.close()  # Close the client connection  
      return documents
   

   