import requests

endpoint = "http://127.0.0.1:8000/auth/test4-7573d9/login/"
data = {
"username": "testing",
"password": "testing321"
}

response = requests.post(endpoint, data=data)

print(response.status_code)
print(response.json())