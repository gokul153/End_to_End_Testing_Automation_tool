from pydantic import BaseModel ,Field
from typing import Any,Optional

class TriggerResponse(BaseModel):
    error_code: Optional[int] = Field(default=None)
    response: Optional[Any] = Field(default=None)
    request_name: Optional[str] = Field(default=None)
    request_key: Optional[str] = Field(default=None)
    duration_ms: Optional[float] = Field(default=None)
    timestamp: Optional[str] = Field(default=None)  # ISO format string
    method: Optional[str] = Field(default=None)
    url: Optional[str] = Field(default=None)
    # @property
    # def error_code(self) -> int:
    #     """Getter for error_code."""
    #     return self._error_code

    # @error_code.setter
    # def error_code(self, value: int) -> None:
    #     """Setter for error_code; ensures it's an integer."""
    #     if not isinstance(value, int):
    #         raise ValueError("error_code must be an integer.")
    #     self._error_code = value

    # @property
    # def response(self) -> Any:
    #     """Getter for response."""
    #     return self._response
    

    # @response.setter
    # def response(self, value: Any) -> None:
    #     """Setter for response; can accept any data type."""
    #     self._response = value
    # @property
    # def request_name(self) -> Any:
    #     """Getter for response."""
    #     return self.request_name
    # @response.setter
    # def request_name(self, value: Any) -> None:
    #     """Setter for response; can accept any data type."""
    #     self.request_name = value    