from pydantic import BaseModel

class ResumeRequest(BaseModel):
    thread_id: str
    feedback: str
