from slixmpp import ClientXMPP
from slixmpp.xmlstream.handler import Callback
from slixmpp.xmlstream.matcher import StanzaPath
from bs4 import BeautifulSoup
import os
import json
import logging
import sys

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
all_messages = {}
failure_reasons = {'DEVICE_UNREGISTERED': 1, 'BAD_REGISTRATION': 2}
r = redis.Redis(host=os.environ['REDIS_HOST'], port=6379, db=0)
sent_messages = {}
q = queue.Queue()
max_message_limit = 100
class FCM(ClientXMPP):

    def __init__(self, sender_id, server_key):
        self.sender_id = sender_id
        self.server_key = server_key
        self.sent_count = 0
        ClientXMPP.__init__(self, sender_id + '@fcm.googleapis.com', server_key)
        self.default_port = 5235
        self.connected_future = asyncio.Future()
        self.add_event_handler("session_start", self.session_start)
        self.add_event_handler("message", self.message)
        self.register_handler(
            Callback('FCM Message', StanzaPath('message'), self.fcm_message)
        )

    def session_start(self, event):
        global all_messages
        print("start callback")
        self.send_presence()
        self.get_roster()

        count = 0
        while True:
            if self.sent_count > 100:
                print("sleeping for 5 seconds")
                time.sleep(5)
            count += 1
            raw_msg = r.rpop(self.sender_id)
            if raw_msg:
                msg = json.loads(raw_msg.decode('utf-8'))
                message = msg['message']
                try:
                    self.fcm_send(json.dumps(message))
                    today = '{0:%d-%m-%Y}'.format(datetime.datetime.now())
                    look_for = today + '_status_' + message['message_id']
                    op = {'online_notification_sent_at': int(time.time()), 'message_id': message['message_id']}
                    r.publish("reports", json.dumps({'id': look_for, 'data': op}))
                    self.sent_count += 1
                except Exception as e:
                    print(e)
                    r.rpush(self.sender_id, json.dumps(msg))
            else:
                print("no more messages")
                sys.exit(0)
            if count > 10000:
                print("1000 reached")
                sys.exit(0)



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
            self.sent_count -= 1
            op = {'online_notification_sent_at': int(time.time()), 'message_id': obj['message_id']}
            r.publish("reports",json.dumps({'id':look_for,'data':op}))
            r.set(look_for,
                  json.dumps(op))
            if 'from' in obj:
                ack = {'to': obj['from'], 'message_id': obj['message_id'], 'message_type': 'ack'}
                self.fcm_send(json.dumps(ack))
        elif obj['message_type'] == 'nack':
            self.sent_count -= 1
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

loop = asyncio.get_event_loop()

conn = FCM(sys.argv[1],sys.argv[2])
conn.start()
conn.reset_future()

loop.run_until_complete(conn.connected_future)









