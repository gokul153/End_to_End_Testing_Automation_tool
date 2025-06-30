from fastapi import FastAPI, HTTPException
from schema import CurlRequestInput, RequestEntity
from service.parsecurlService import parse_curl_to_entity

app = FastAPI()

@app.post("/parse-curl", response_model=RequestEntity)
def parse_curl(input: CurlRequestInput):
    try:
        result = parse_curl_to_entity(input.curl_command)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
