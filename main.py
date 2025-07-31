from fastapi import FastAPI, HTTPException, Request
from typing import TypedDict, Annotated, Optional
from schema import CurlRequestInput, RequestEntityDB
from service.parsecurlService import parse_curl_to_entity
from service.hitRequestService import make_api_call
from service.listAllRequestService import readallRequest
from service.GenerateMulitpleSample import executeMultipleSample
from service.graph_executor import LangGraphRunner
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi import Query
import os
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from service.CsvService import CSVService;
from sse_starlette.sse import EventSourceResponse
import uuid
from fastapi import Body
from model.response.request.ResumeRequest import ResumeRequest

app = FastAPI()
runner = LangGraphRunner()
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
