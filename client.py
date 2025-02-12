import requests

url = "http://127.0.0.1:8000/request_ambulance/"

# Example data with hospital_id and patient location (latitude, longitude)
data = {
    "hospital_id": 1,
    "patient_id": 123,  # Assuming patient ID 123
    "client_location": "19.0760,72.8777"  # Replace with real location
}

response = requests.post(url, json=data)  
print(response.status_code)
print(response.json())
