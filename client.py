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
sent_messages = 0
q = queue.Queue()
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
            sent_messages -= 1
            r.set(look_for,
                  json.dumps({'online_notification_sent_at': int(time.time()), 'message_id': obj['message_id']}))
            if 'from' in obj:
                ack = {'to': obj['from'], 'message_id': obj['message_id'], 'message_type': 'ack'}
                XMPP[message_senders[obj['message_id']]].fcm_send(json.dumps(ack))
        elif obj['message_type'] == 'nack':
            sent_messages -= 1
            op = {'online_notification_sent_at': int(time.time()), 'message_id': obj['message_id'],
                  'error': obj['error']}
            if obj['error'] in failure_reasons:
                op['failure_reason'] = failure_reasons[obj['error']]
            else:
                op['failure_reason'] = 3
            r.set(look_for,
                  json.dumps(op))
        elif obj['message_type'] == 'receipt':
            look_for = today + '_message_' + obj['message_id'][4:]
            r.set(look_for,
                  json.dumps({'notification_delivered_at': int(time.time()), 'message_id': obj['message_id'][4:]}))

    def start(self):
        self.connect(address=('fcm-xmpp.googleapis.com', 5235), use_ssl=True, disable_starttls=False)

    def fcm_send(self, payload):
        self.send_raw('<message><gcm xmlns="google:mobile:data">{0}</gcm></message>'.format(payload))

    def reset_future(self):
        "Reset the future in case of disconnection"
        self.connected_future = asyncio.Future()
async def reconnect(request):
    global XMPP
    for fcm_sender_id in app_keys:
        if not XMPP[fcm_sender_id].is_connected():
            XMPP[fcm_sender_id] = FCM(fcm_sender_id, app_keys[fcm_sender_id])
            # XMPP= FCM(os.environ['FCM_SENDER_ID'], os.environ['FCM_SERVER_KEY'])
            XMPP[fcm_sender_id].start()
            # XMPP.connect()
            XMPP[fcm_sender_id].reset_future()
    return web.Response(text="done")
async def restart_jobs(request):
    global sent_messages, XMPP
    count = 0
    while True:
        count += 1
        print("counting "+str(count))
        raw_msg = r.rpop("all_messages")
        if raw_msg:
            msg = json.loads(raw_msg.decode('utf-8'))
            fcm_sender_id = msg['id']
            message=msg['message']
            if XMPP[fcm_sender_id].is_connected() and sent_messages<=10000:
                print("sending count "+str(sent_messages))
                message_senders[message['message_id']] = fcm_sender_id
                XMPP[fcm_sender_id].fcm_send(json.dumps(message))
                sent_messages += 1
            else:
                if not XMPP[fcm_sender_id].is_connected():
                    print("not connected")
                else:
                    print("more than 100")
                r.rpush("all_messages",json.dumps(msg))
                break
        else:
            print("no more messages")
            break
    return web.Response(text="done")

async def handle(request):
    global sent_messages,XMPP
    "Handle the HTTP request and block until the vcard is fetched"
    err_404 = web.Response(status=404, text='Not found')
    body = await  request.json()
    #  for message in body:
    #     print(message['notification'])

    fcm_sender_id = request.match_info.get('fcm_sender_id', "0")


    for message in body:
        if XMPP[fcm_sender_id].is_connected() and sent_messages<=10000:
            print("sending count " + str(sent_messages))
            message_senders[message['message_id']] = fcm_sender_id
            XMPP[fcm_sender_id].fcm_send(json.dumps(message))
            sent_messages += 1
        else:
            r.rpush("all_messages",json.dumps({'id':fcm_sender_id,'message':message}))


    return web.Response(text="done")


async def init(loop, host: str, port: str):
    "Initialize the HTTP server"
    app = web.Application(loop=loop)

    app.router.add_route('POST', '/{fcm_sender_id}', handle)
    app.router.add_route('GET', '/reconnect', reconnect)
    app.router.add_route('GET', '/finish', restart_jobs)
    srv = await loop.create_server(app.make_handler(), host, port)
    log.info("Server started at http://%s:%s", host, port)
    return srv


def main(namespace):
    "Start the xmpp client and delegate the main loop to asyncio"
    response = requests.get(os.environ['APP_URL'])
    data = response.json()
    loop = asyncio.get_event_loop()
    global XMPP
    loop.run_until_complete(init(loop, namespace.host, namespace.port))

    for x in data:
        app_keys[x['app_id']] = x['app_key']
        XMPP[x['app_id']] = FCM(x['app_id'], x['app_key'])
        # XMPP= FCM(os.environ['FCM_SENDER_ID'], os.environ['FCM_SERVER_KEY'])
        XMPP[x['app_id']].start()
        # XMPP.connect()
        XMPP[x['app_id']].reset_future()
    for x in data:
        loop.run_until_complete(XMPP[x['app_id']].connected_future)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        import sys


def parse_args():
    "Parse the command-line arguments"
    from argparse import ArgumentParser
    parser = ArgumentParser()

    parser.add_argument('--host', dest='host', default=HOST,
                        help='Host on which the HTTP server will listen')
    parser.add_argument('--port', dest='port', default=PORT,
                        help='Port on which the HTTP server will listen')

    return parser.parse_args()


HOST = '0.0.0.0'
PORT = 8768

if __name__ == "__main__":
    print(parse_args())
    main(parse_args())
