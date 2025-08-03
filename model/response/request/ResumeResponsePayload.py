from pydantic import BaseModel
from typing import Optional, Dict, Any
from typing import List
class ResumePayloadResponse(BaseModel):
    thread_id: str
    feilds: List[str]  # should include monitored_fields and ignored_fields