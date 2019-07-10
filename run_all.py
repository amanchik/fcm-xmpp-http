import sys
import redis
import requests
import os
response = requests.get(os.environ['APP_URL'])
data = response.json()
for x in data:
    sender_id = x['app_id']
    server_key = x['app_key']
    r = redis.Redis(host=os.environ['REDIS_HOST'], port=6379, db=0)
    flen=r.llen(sender_id)
    if flen>0:
        os.system("python run.py "+sender_id+" "+server_key)
    else:
        print("no messages for "+str(sender_id))
