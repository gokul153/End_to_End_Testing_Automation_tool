from pydantic import BaseModel
from typing import List, Dict, Optional

from pydantic import BaseModel, Field
from typing import List, Dict

class InsightResult(BaseModel):
    field_changes: List[str] = Field(
        ...,
        description="List of key field changes observed in the request/response data, such as changes in headers, payload values, or structures if there are more than 25 changes list the top 25 changes."
    )

    anomalies: List[str] = Field(
        ...,
        description="List of unusual patterns or unexpected behaviors, like sudden latency spikes, error surges, or missing fields like one  request have 200 and other failed."
    )

    error_trends: List[str] = Field(
        ...,
        description="List of error patterns observed over time, such as increasing error rates or specific error codes that have become more frequent.")

    duration_trend: List[str] = Field(
        ...,
        description="List describing performance changes over time in terms of response durations (in milliseconds), highlighting increasing or decreasing trends not more than 25 changes."
    )

    response_similarity_scores: Dict[str, float] = Field(
        ...,
        description="Dictionary mapping response version pairs (e.g., 'v1->v2') to similarity scores (0.0 to 1.0), where 1.0 means identical responses and 0.0 means completely different."
    )

    performance_score: float = Field(
        ...,
        description="A computed score between 0 and 100 representing the overall backend health based on stability, speed, and error trends. Higher is better."
    )

    summary: str = Field(
        ...,
        description="A human-readable summary of key insights derived from the analysis, written in natural language for end-user understanding."
    )
