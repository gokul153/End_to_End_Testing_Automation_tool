from fastapi import FastAPI, HTTPException
from schema import CurlRequestInput, RequestEntityDB
from service.parsecurlService import parse_curl_to_entity
from service.hitRequestService import make_api_call
from service.listAllRequestService import readallRequest
from service.GenerateMulitpleSample import executeMultipleSample
from fastapi import FastAPI, UploadFile, File, HTTPException
import os
from service.CsvService import CSVService;
app = FastAPI()
mongo_uri = "mongodb://localhost:27017/"
db_name = "gen-ai"
collection_name = "request-recieved-csv"

csv_service = CSVService(mongo_uri, db_name, collection_name)

@app.post("/parse-curl", response_model=RequestEntityDB)
def parse_curl(input: CurlRequestInput):
    try:
        print("parsing")
        result = parse_curl_to_entity(input.curl_command)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@app.post("/curlpython")   
def hit_request(input : str):
    print("Trying to trigger the request"+ " "+ input)
    return make_api_call(input)
     

@app.post("/upload-csv/")
async def upload_csv(file: UploadFile = File(...)):
     # Save the uploaded file temporarily
    try:
        file_location = await csv_service.save_file(file)
        # Process the CSV file
        csv_service.process_csv(file_location)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up the temporary file
        csv_service.cleanup_file(file_location)

    return {"message": "File successfully processed and stored."}

@app.get("/list")
async def show_all_request(request_name:str):
    try:
        print("fetching all request")
        result = readallRequest(requestname=request_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@app.post("/generate_sample")
async def generateSampleJson(request_name:str):
    try:
        print("generating sample")
        executeMultipleSample(request_name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))    




