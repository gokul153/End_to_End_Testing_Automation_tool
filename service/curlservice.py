import shlex
import json
from schema import RequestEntity 
from schema import CurlRequestInput

class CurlService:
    # def __init__(self, method: str = "GET", url: str = "", headers: dict = None, data: str = None):
    #     self.method = method
    #     self.url = url
    #     self.headers = headers if headers is not None else {}
    #     self.data = data

    # def __repr__(self):
    #     return f"RequestEntity(method='{self.method}', url='{self.url}', headers={self.headers}, data='{self.data}')"
    @staticmethod
    def parse_curl_to_entity(curl_input: CurlRequestInput) -> RequestEntity:
      request_entity = RequestEntity()
      original_tokens = shlex.split(curl) # Keep original for URL fallback

      tokens = original_tokens[:] # Work with a copy
      if tokens and tokens[0] == "curl":
        tokens = tokens[1:]

      i = 0
      while i < len(tokens):
        token = tokens[i]

        if token == "-X" or token == "--request":
             if i + 1 < len(tokens):
                request_entity.method = tokens[i + 1].upper()
                i += 2
             else:
                i += 1 # Skip this flag if no value
        elif token == "-H" or token == "--header" or token == "\n--header":
            if i + 1 < len(tokens):
                header_parts = tokens[i + 1].split(":", 1)
                if len(header_parts) == 2:
                    request_entity.headers[header_parts[0].strip()] = header_parts[1].strip()
                i += 2
            else:
                i += 1 # Skip this flag if no value
        elif token in ["-d", "--data", "--data-raw", "--data-binary", "--data-urlencode","\n--data-raw"]:
            if i + 1 < len(tokens):
                request_entity.data = tokens[i + 1]
                i += 2
            else:
                i += 1 # Skip this flag if no value
        elif not token.startswith("-"):
            # This is likely the URL if it hasn't been set yet
            if not request_entity.url:
                request_entity.url = token
            i += 1
        else:
            i += 1 # Unknown flag or other argument, just advance
    
         # Post-processing for common curl behaviors
          # If method is not explicitly set, and data is present, assume POST
        if not request_entity.method and request_entity.data:
          request_entity.method = "POST"
    
        # If URL is still empty, try to find it as the last non-flag argument from original tokens
        if not request_entity.url:
         for token in reversed(original_tokens):
            if not token.startswith("-") and token != "curl":
                request_entity.url = token
                break
        print("Extracted Request Enity --\n"+request_entity)
        request_entity.data.replace("\\n","")
        return request_entity
