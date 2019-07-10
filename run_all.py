import sys
import requests
import os
response = requests.get(os.environ['APP_URL'])
data = response.json()
for x in data:
    sender_id = x['app_id']
    server_key = x['app_key']
    os.system("python run.py "+sender_id+" "+server_key)
