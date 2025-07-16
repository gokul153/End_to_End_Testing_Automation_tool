from pydantic import BaseModel, Field, HttpUrl
from typing import Dict, Optional

class RequestEntityDB(BaseModel):
    url: HttpUrl = Field(..., description="Target endpoint URL")
    method: str = Field(..., description="HTTP method, e.g., GET, POST")
    headers: Optional[Dict[str, str]] = Field(default_factory=dict, description="Request headers")
    params: Optional[Dict[str, str]] = Field(default_factory=dict, description="Query parameters")
    body: Optional[Dict] = Field(default_factory=dict, description="JSON body payload")
    name : str  = Field(..., description="name of request")

class CurlRequestInput(BaseModel):
    curl_command: str = Field(..., description="Full cURL command string")

   