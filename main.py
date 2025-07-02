from fastapi import FastAPI, HTTPException
from schema import CurlRequestInput, RequestEntityDB
from service.parsecurlService import parse_curl_to_entity

app = FastAPI()

@app.post("/parse-curl", response_model=RequestEntityDB)
def parse_curl(input: CurlRequestInput):
    try:
        result = parse_curl_to_entity(input.curl_command)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@app.post("/curlpython", response_model=RequestEntityDB)   
def parse_python_curl(input : str):
    return "test" 
