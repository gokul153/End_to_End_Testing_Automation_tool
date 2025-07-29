from pydantic import BaseModel ,Field
from typing import Any

class TriggerResponse(BaseModel):
    error_code: int = Field(..., alias='error_code')  # Private field for error_code
    response: Any = Field(..., alias='response')      # Private field for response
    request_name: str = Field(..., alias='request_name')  # New field for request name
   
    @property
    def error_code(self) -> int:
        """Getter for error_code."""
        return self._error_code

    @error_code.setter
    def error_code(self, value: int) -> None:
        """Setter for error_code; ensures it's an integer."""
        if not isinstance(value, int):
            raise ValueError("error_code must be an integer.")
        self._error_code = value

    @property
    def response(self) -> Any:
        """Getter for response."""
        return self._response
    

    @response.setter
    def response(self, value: Any) -> None:
        """Setter for response; can accept any data type."""
        self._response = value
    @property
    def request_name(self) -> Any:
        """Getter for response."""
        return self.request_name
    @response.setter
    def request_name(self, value: Any) -> None:
        """Setter for response; can accept any data type."""
        self.request_name = value    