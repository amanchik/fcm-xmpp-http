from slixmpp import ClientXMPP
from slixmpp.xmlstream.handler import Callback
from slixmpp.xmlstream.matcher import StanzaPath
from bs4 import BeautifulSoup
import os
import json
import logging

logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)
log = logging.getLogger(__name__)
import requests
import datetime
import time

import asyncio
from aiohttp import web
import redis
import queue
XMPP = {}
app_keys = {}
message_senders = {}
failure_reasons = {'DEVICE_UNREGISTERED': 1, 'BAD_REGISTRATION': 2}
r = redis.Redis(host=os.environ['REDIS_HOST'], port=6379, db=0)
sent_messages = {}
q = queue.Queue()
max_message_limit = 10000
class FCM(ClientXMPP):

    def __init__(self, sender_id, server_key):
        print(sender_id)
        print(server_key)
        ClientXMPP.__init__(self, sender_id + '@fcm.googleapis.com', server_key)
        self.default_port = 5235
        self.connected_future = asyncio.Future()
        self.add_event_handler("session_start", self.session_start)
        self.add_event_handler("message", self.message)
        self.register_handler(
            Callback('FCM Message', StanzaPath('message'), self.fcm_message)
        )

    def session_start(self, event):
        print("start callback")
        self.send_presence()
        self.get_roster()

    def message(self, msg):
        print("got message")
        if msg['type'] in ('chat', 'normal'):
            msg.reply("Thanks for sending\n%(body)s" % msg).send()

    def fcm_message(self, data):
        global sent_messages
        print(data)
        y = BeautifulSoup(str(data), features='html.parser')
        print(y.message.gcm.text)
        obj = json.loads(y.message.gcm.text)

        print(obj)
        today = '{0:%d-%m-%Y}'.format(datetime.datetime.now())
        look_for = today + '_status_' + obj['message_id']
        if obj['message_type'] == 'ack':
            sent_messages[message_senders[obj['message_id']]] -= 1
            op = {'online_notification_sent_at': int(time.time()), 'message_id': obj['message_id']}
            r.publish("reports",json.dumps({'id':look_for,'data':op}))
            r.set(look_for,
                  json.dumps(op))
            if 'from' in obj:
                ack = {'to': obj['from'], 'message_id': obj['message_id'], 'message_type': 'ack'}
                XMPP[message_senders[obj['message_id']]].fcm_send(json.dumps(ack))
        elif obj['message_type'] == 'nack':
            sent_messages[message_senders[obj['message_id']]] -= 1
            op = {'online_notification_sent_at': int(time.time()), 'message_id': obj['message_id'],
                  'error': obj['error']}
            if obj['error'] in failure_reasons:
                op['failure_reason'] = failure_reasons[obj['error']]
            else:
                op['failure_reason'] = 3
            r.publish("reports", json.dumps({'id': look_for, 'data': op}))
            r.set(look_for,
                  json.dumps(op))
        elif obj['message_type'] == 'receipt':
            look_for = today + '_message_' + obj['message_id'][4:]
            op = {'notification_delivered_at': int(time.time()), 'message_id': obj['message_id'][4:]}
            r.publish("reports", json.dumps({'id': look_for, 'data': op}))
            r.set(look_for,
                  json.dumps(op))

    def start(self):
        self.connect(address=('fcm-xmpp.googleapis.com', 5235), use_ssl=True, disable_starttls=False)

    def fcm_send(self, payload):
        self.send_raw('<message><gcm xmlns="google:mobile:data">{0}</gcm></message>'.format(payload))

    def reset_future(self):
        "Reset the future in case of disconnection"
        self.connected_future = asyncio.Future()
def reconnect():
    global XMPP,sent_messages
    for fcm_sender_id in app_keys:
        if not XMPP[fcm_sender_id].is_connected() or  sent_messages[fcm_sender_id]>=max_message_limit:
            sent_messages[fcm_sender_id]=0
            XMPP[fcm_sender_id] = FCM(fcm_sender_id, app_keys[fcm_sender_id])
            # XMPP= FCM(os.environ['FCM_SENDER_ID'], os.environ['FCM_SERVER_KEY'])
            XMPP[fcm_sender_id].start()
            # XMPP.connect()
            XMPP[fcm_sender_id].reset_future()
response = requests.get(os.environ['APP_URL'])
data = response.json()

while True:
    print("coming here")
    raw_msg = r.rpop("all_messages")
    if raw_msg:
        reconnect()
        msg = json.loads(raw_msg.decode('utf-8'))
        fcm_sender_id = msg['id']
        message=msg['message']
        if fcm_sender_id in XMPP and XMPP[fcm_sender_id].is_connected() and sent_messages[fcm_sender_id]<=max_message_limit:
            print("sending count "+str(sent_messages[fcm_sender_id]))
            message_senders[message['message_id']] = fcm_sender_id
            try:
                XMPP[fcm_sender_id].fcm_send(json.dumps(message))
                today = '{0:%d-%m-%Y}'.format(datetime.datetime.now())
                look_for = today + '_status_' + message['message_id']
                op = {'online_notification_sent_at': int(time.time()), 'message_id': message['message_id']}
                r.publish("reports", json.dumps({'id': look_for, 'data': op}))
                sent_messages[fcm_sender_id] += 1
            except Exception as e:
                print(e)
                r.rpush("all_messages", json.dumps(msg))
    else:
        print("no more messages")
        break








