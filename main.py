from fastapi import FastAPI, HTTPException, Request
from typing import TypedDict, Annotated, Optional
from schema import CurlRequestInput, RequestEntityDB
from service.parsecurlService import parse_curl_to_entity
from service.hitRequestService import make_api_call
from service.listAllRequestService import readallRequest
from service.GenerateMulitpleSample import executeMultipleSample
from service.graph_executor import LangGraphRunner
from service.graphExecuterResponseAnalysing import LangGraphRunnerResponseAnalyser
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi import Query
import os
import json
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from service.CsvService import CSVService;
from sse_starlette.sse import EventSourceResponse
import uuid
from fastapi import Body
from model.response.request.ResumeRequest import ResumeRequest
from model.response.request.ResumeResponsePayload import ResumePayloadResponse
from typing import List, Dict, Optional
from service.BigQueryService import BigQueryService
from pydantic import BaseModel ,Field
# Define the Pydantic model for the request body
class BigQueryRequest(BaseModel):
    feild_name: Optional[str] = None
app = FastAPI()
runner = LangGraphRunner()
runner_response_analyser = LangGraphRunnerResponseAnalyser()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"], 
    expose_headers=["Content-Type"], 
)
mongo_uri = "mongodb://localhost:27017/"
db_name = "gen-ai"
collection_name = "request-recieved-csv"
# Instantiate the service class
bq_service = BigQueryService()
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
sessions = {}
@app.get("/chat_stream_response/{request_name}")
async def chat_stream_response(request_name: str, checkpoint_id: Optional[str] = Query(None)):
    thread_id = checkpoint_id if checkpoint_id else str(uuid.uuid4())
    if thread_id not in sessions:
        sessions[thread_id] = []
    stream = await runner_response_analyser.start_response(request_name, thread_id)

    async def event_generator():
        async for chunk in stream:
            for node, output in chunk.items():
                if node == "__interrupt__":
                    interrupt_obj = output[0]  # Get the Interrupt instance
                    interrupt_data = getattr(interrupt_obj, "value", {})
                    yield {
                        ## need explaination on this
                        "event": "interrupt",
                        "data": json.dumps({
                            "message": interrupt_data.get("message", ""),
                            "fields": interrupt_data.get("key", [])
                        })
                        
                    }
                else:
                    yield {
                       
                        "event": "update",
                        "data": f"{node}: {output}"
                    }
        yield {"event": "end", "data": "Execution finished"}

    return EventSourceResponse(event_generator())

@app.post("/resume_response")
async def resume_response(payload: ResumePayloadResponse):
    stream = await runner_response_analyser.resume_response(payload.thread_id, payload.feilds)

    async def resume_generator():
        async for chunk in stream:
            for node, output in chunk.items():
                if node == "__interrupt__":
                    interrupt_obj = output[0]
                    interrupt_data = getattr(interrupt_obj, "value", {})
                    yield {
                        "event": "interrupt",
                       "data": json.dumps({
                            "message": interrupt_data.get("message", ""),
                            "fields": interrupt_data.get("fields", [])
                        })
                      
                    }
                else:
                    yield {
                        "event": "update",
                        "data": f"{node}: {output}"
                    }

        yield {"event": "end", "data": "Execution resumed and finished"}

    return EventSourceResponse(resume_generator())
@app.get("/chat_stream/{request_name}")
async def chat_stream(request_name: str, checkpoint_id: Optional[str] = Query(None)):
    thread_id = checkpoint_id
    sessions[thread_id] = []
    stream = await runner.start(request_name, thread_id)

    async def event_generator():
        async for chunk in stream:
            for node, output in chunk.items():
               
                if node == "__interrupt__":
                    interrupt_obj = output[0]  # Get the Interrupt instance
                    interrupt_data = getattr(interrupt_obj, "value", {})
                    yield {
                        "event": "interrupt",
                        "data": interrupt_data["message"],
                        "id": interrupt_data["key"]
                    }
                else:
                    yield {
                        "event": "update",
                        "data": f"{node}: {output}"
                    }
        yield {"event": "end", "data": "Execution finished"}

    return EventSourceResponse(event_generator())


@app.post("/resume")
async def resume(payload: ResumeRequest):
    thread_id = payload.thread_id
    feedback = payload.feedback
    stream = await runner.resume(thread_id, feedback)

    async def resume_generator():
        async for chunk in stream:
            for node, output in chunk.items():
                if node == "__interrupt__":
                    print("Interrupt received:", output)
                    interrupt_obj = output[0]  # Get the Interrupt instance
                    interrupt_data = getattr(interrupt_obj, "value", {})
                    yield {
                        "event": "interrupt",
                        "data": interrupt_data["message"],
                        "id": interrupt_data["key"]
                    }
                else:
                    yield {
                        "event": "update",
                        "data": f"{node}: {output}"
                    }
        yield {"event": "end", "data": "Execution resumed and finished"}

    return EventSourceResponse(resume_generator())


@app.post("/hospitals/", response_model=List[Dict])
def get_hospital_data(request: BigQueryRequest):
    """
    API endpoint to fetch a list of hospitals from BigQuery
    using a request body.
    
    Args:
        request: A JSON object in the request body with the key 'hospital_name'.
    
    Returns:
        A JSON array of hospital records.
    """
    try:
        # Pass the hospital_name from the request body to the service
        hospitals = bq_service.get_hospitals(request.feild_name)
        return hospitals
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))