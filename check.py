from model.response.TriggerResponse import TriggerResponse

def main():
    # Create an instance of TriggerResponse
    trigger_response = TriggerResponse()

    # Set values for error_code and response
    trigger_response.error_code = 200
    trigger_response.response = {"message": "Success"}

    # Print the values to check if everything is working fine
    print(f"Error Code: {trigger_response.error_code}")
    print(f"Response: {trigger_response.response}")
if __name__ == '__main__':
    main()