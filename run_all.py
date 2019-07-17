import sys
import json
import redis
import requests
import os
import json
import jwt
import time
import sys
from hyper import HTTPConnection, HTTP20Connection
response = requests.get(os.environ['APP_URL'])
data = response.json()
r = redis.Redis(host=os.environ['REDIS_HOST'], port=6379, db=0)
for x in data:
    sender_id = x['app_id']
    server_key = x['app_key']
    while True:
        flen = r.llen(sender_id)
        if flen > 0:
            os.system("python run.py " + sender_id + " " + server_key)
        else:
            print("no messages for " + str(sender_id))
            break


def send_ios_push(id,key,team_id,bundle_id,tokens,title,message):
    ALGORITHM = 'ES256'

    APNS_KEY_ID = id

    # http://disq.us/p/1ecxfqv:
    # CMD: fold -w 64 APNsAuthKey_my_id.p8 > certs/APNsAuthKey_my_id_fold.p8
    APNS_AUTH_KEY = key

    TEAM_ID = team_id
    BUNDLE_ID = bundle_id

    #PUSH_ID = device_token

    f = open(APNS_AUTH_KEY)
    secret = f.read()

    token = jwt.encode(
        {
            'iss': TEAM_ID,
            'iat': time.time()
        },
        secret,
        algorithm=ALGORITHM,
        headers={
            'alg': ALGORITHM,
            'kid': APNS_KEY_ID
        }
    )


    request_headers = {
        'apns-expiration': '0',
        'apns-priority': '10',
        'apns-topic': BUNDLE_ID,
        'authorization': 'bearer {0}'.format(token.decode('ascii'))
    }

    # Open a connection the APNS server

    # https://github.com/genesluder/python-apns/pull/3
    # https://github.com/genesluder/python-apns/pull/3/commits/0f543b773c25b1a1d817f5f681912ed3c9c2ca35

    # Development
    # conn = HTTP20Connection('api.development.push.apple.com:443', force_proto='h2')

    # Production
    conn = HTTP20Connection('api.push.apple.com:443', force_proto='h2')

    for token in tokens:
        payload_data = {
            'aps': {
                'alert': message,
                'title': title,
                # This is silent push
                'sound': 'default',
                # Key to silent push
                'content-available': 1
            },
            'payload': {
                'title': title,
                'body': message,
                'message': message,
                'message_id': token['message_id'],
                'sent_id': token['sent_id'],
                'received_message_id': token['received_message_id']
            }
        }
        del payload_data['payload']
        print(payload_data)
        payload = json.dumps(payload_data).encode('utf-8')
        path = '/3/device/{0}'.format(token['token'])

        # Send our request
        conn.request(
            'POST',
            path,
            payload,
            headers=request_headers
        )

        # https://github.com/genesluder/python-apns/pull/3
        # http://www.ehowstuff.com/how-to-install-and-update-openssl-on-centos-6-centos-7/
        resp = conn.get_response()
        print(resp.status)
        print(resp.read())
raw_msg = r.rpop('all_ios')
while raw_msg:
    msg = json.loads(raw_msg.decode('utf-8'))

    send_ios_push(msg['id'],msg['key'],msg['team_id'],msg['topic'],msg['tokens'],msg['title'],msg['message'])
    raw_msg = r.rpop('all_ios')