import requests
access = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzU0MjU4OTI0LCJpYXQiOjE3NTQyNTg2MjQsImp0aSI6IjQwMGZmY2QyODU5MTQ4NGU4MTJmZTM0YjU2M2EzMzc5IiwidXNlcl9pZCI6M30.TyCNvRPettKO8iRCQW6XHZn016uvUdQRUpKRqR6KSUg"


endpoint = "http://127.0.0.1:8000/api/test4-7573d9/add-whish"

data = {
    'product_id': 1,
}

headers = {
    "Authorization": f"Bearer {access}"
}



response = requests.post(endpoint, data=data, headers=headers)

print(response.status_code)
print(response)
print(headers)
