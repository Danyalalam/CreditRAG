import json
import requests

# Load the JSON file
with open('identityiq_1.json', 'r') as file:
    test_cases = json.load(file)

# API URL
api_url = "http://localhost:8000/api/process/"  # Update with your actual API URL

# Iterate through each test case and make a GET request
for case in test_cases:
    params = {
        "payment_status": case["payment_status"],
        "account_status": case["account_status"],
        "creditor_remark": case["creditor_remark"]
    }
    
    # Make the GET request
    response = requests.get(api_url, params=params)
    
    # Print the response
    print(f"Test Case: {params}")
    print(f"Response Status Code: {response.status_code}")
    print(f"Response Data: {response.json()}\n")
