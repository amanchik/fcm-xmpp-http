from slixmpp import ClientXMPP
from slixmpp.xmlstream.handler import Callback
from slixmpp.xmlstream.matcher import StanzaPath
from bs4 import BeautifulSoup
import os
import json
import logging
import sys
from threading import Thread

logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)
log = logging.getLogger(__name__)
import requests
import datetime
import time
import os
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
        self.draining = False
        self.sender_id = sender_id
        self.server_key = server_key
        self.sent_count = 0
        ClientXMPP.__init__(self, sender_id + '@fcm.googleapis.com', server_key)
        self.default_port = 5235
      #  self.connected_future = asyncio.Future()
        self.add_event_handler("session_start", self.session_start)
        self.add_event_handler("message", self.message)
        self.register_handler(
            Callback('FCM Message', StanzaPath('message'), self.fcm_message)
        )

    def session_start(self, event):
        global all_messages
        self.sessionstarted = True
        print("start callback")
        sys.stdout.flush()
        self.send_presence()
        self.get_roster()





    def message(self, msg):
        print("got message")
        if msg['type'] in ('chat', 'normal'):
            msg.reply("Thanks for sending\n%(body)s" % msg).send()

    def fcm_message(self, data):
        global sent_messages
       # print(data)
        y = BeautifulSoup(str(data), features='html.parser')
     #   print(y.message.gcm.text)
        obj = json.loads(y.message.gcm.text)
      #  print(obj)

      #  print(obj)
        today = '{0:%d-%m-%Y}'.format(datetime.datetime.now())
        look_for = today + '_status_' + obj['message_id']
        if obj['message_type'] == 'ack':
            print("got ack")
            sys.stdout.flush()
            self.sent_count -= 1
            op = {'online_notification_sent_at': int(time.time()), 'message_id': obj['message_id']}
            r.publish("reports",json.dumps({'id':look_for,'data':op}))
            r.set(look_for,
                  json.dumps(op))
            if 'from' in obj:
                ack = {'to': obj['from'], 'message_id': obj['message_id'], 'message_type': 'ack'}
                self.fcm_send(json.dumps(ack))
        elif obj['message_type'] == 'nack':
            print("got nack")
            sys.stdout.flush()
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
            print("got receipt")
            sys.stdout.flush()
            look_for = today + '_message_' + obj['message_id'][4:]
            op = {'notification_delivered_at': int(time.time()), 'message_id': obj['message_id'][4:]}
            r.publish("reports", json.dumps({'id': look_for, 'data': op}))
            r.set(look_for,
                  json.dumps(op))
        elif obj['message_type'] == 'control':
            print("connection draining "+obj['control_type'])
            sys.stdout.flush()
            self.draining = True


    def start(self):
        self.connect(address=('fcm-xmpp.googleapis.com', 5235), use_ssl=True, disable_starttls=False)

    def fcm_send(self, payload):
        self.send_raw('<message><gcm xmlns="google:mobile:data">{0}</gcm></message>'.format(payload))

 #   def reset_future(self):
        "Reset the future in case of disconnection"
  #      self.connected_future = asyncio.Future()
conn = FCM(sys.argv[1],sys.argv[2])
conn.start()
#conn.reset_future()

def send_messages():
    global conn
    start = time.time()
    first_time = True
    while not conn.sessionstarted:
        if first_time:
            print("session not started to sleeping")
            sys.stdout.flush()
            time.sleep(1)
            first_time = False
            continue
        if time.time() - start >= 10:
            print("10 seconds is too much to start the session so end")
            sys.stdout.flush()
            kill_me()
    count = 0
    start = time.time()
    failed = False
    while True:
        count += 1
        if conn.draining:
            time.sleep(10)
        if not conn.is_connected():
            print("not connected so die")
            sys.stdout.flush()
            kill_me()

        while conn.sent_count > 90:
           time.sleep(1)
           if time.time() - start > 900:
               print("900 seconds so exit")
               sys.stdout.flush()
               kill_me()


        raw_msg = r.rpop(conn.sender_id)
        if raw_msg:
            msg = json.loads(raw_msg.decode('utf-8'))
            message = msg['message']
            try:
                #    print("sending message with id "+message['message_id'])
           #     print(message)
                if conn.is_connected():
                    conn.fcm_send(json.dumps(message))
                else:
                    print("not connected so die")
                    r.rpush(conn.sender_id, json.dumps(msg))
                    kill_me()
                #     today = '{0:%d-%m-%Y}'.format(datetime.datetime.now())
                #      look_for = today + '_status_' + message['message_id']
                #       op = {'online_notification_sent_at': int(time.time()), 'message_id': message['message_id']}
                #        r.publish("reports", json.dumps({'id': look_for, 'data': op}))
                conn.sent_count += 1
            except Exception as e:
                print(e)
                r.rpush(conn.sender_id, json.dumps(msg))
                failed = True
            if failed:
                print("failed so exit")
                sys.stdout.flush()
                kill_me()
        else:
            print("no more messages " + str(conn.sent_count))
            sys.stdout.flush()
            if conn.sent_count == 0:
                kill_me()
            else:
                time.sleep(2)
def kill_me():
    os._exit(0)
#loop = asyncio.get_event_loop()


thread1 = Thread( target=send_messages )
thread1.start()
conn.process(forever=True)
#loop.run_until_complete(conn.connected_future)
#try:
 #   loop.run_forever()
#except KeyboardInterrupt:
  #  import sys







