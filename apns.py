"""
Use HTTP/2 send APNS Example main reference
===========================================
http://gobiko.com/blog/token-based-authentication-http2-example-apns/
Error 410 to detect uninstalls
==============================
https://leftshift.io/mobile-tracking-uninstalls-on-ios-and-android
https://developer.apple.com/library/content/documentation/NetworkingInternet/Conceptual/RemoteNotificationsPG/CommunicatingwithAPNs.html#//apple_ref/doc/uid/TP40008194-CH11-SW1
Expected result from below code:
410
{"reason":"Unregistered","timestamp":1496371306210}
HTTP/2 push
===========
https://tpu.thinkpower.com.tw/tpu/File/html/201611/20161122001842_f.html?f=3dj6j8kd38895ksgtdddd93865jhr9sn3rqkh
"""

import json
import jwt
import time
import sys
from hyper import HTTPConnection, HTTP20Connection

ALGORITHM = 'ES256'

APNS_KEY_ID = sys.argv[1]

# http://disq.us/p/1ecxfqv:
# CMD: fold -w 64 APNsAuthKey_my_id.p8 > certs/APNsAuthKey_my_id_fold.p8
APNS_AUTH_KEY = sys.argv[2]

TEAM_ID = sys.argv[3]
BUNDLE_ID = sys.argv[4]

PUSH_ID = sys.argv[5]

f = open(APNS_AUTH_KEY)
secret = f.read()

token = jwt.encode(
    {
        'iss': TEAM_ID,
        'iat': time.time()
    },
    secret,
    algorithm= ALGORITHM,
    headers={
        'alg': ALGORITHM,
        'kid': APNS_KEY_ID
    }
)

path = '/3/device/{0}'.format(PUSH_ID)

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
#conn = HTTP20Connection('api.development.push.apple.com:443', force_proto='h2')

# Production
conn = HTTP20Connection('api.push.apple.com:443', force_proto='h2')

payload_data = {
    'aps': {
        'alert' : 'Are you correcting the test?',
		# This is silent push
        'sound' : '',
		# Key to silent push
        'content-available': 1
    }
}
payload = json.dumps(payload_data).encode('utf-8')

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

# If we are sending multiple requests, use the same connection
payload_data = {
    'aps': {
        'alert' : 'You have no chance to survive. Make your time.',
        'sound' : '',
        'content-available': 1
    }
}
payload = json.dumps(payload_data).encode('utf-8')

conn.request(
    'POST',
    path,
    payload,
    headers=request_headers
)

resp = conn.get_response()
print(resp.status)
print(resp.read())