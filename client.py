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


import asyncio
from aiohttp import web

XMPP = {}



class FCM(ClientXMPP):

    def __init__(self, sender_id, server_key):
        print(sender_id)
        print(server_key)
        ClientXMPP.__init__(self, sender_id+'@fcm.googleapis.com', server_key)
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
        print(data)
        y = BeautifulSoup(str(data),features='html.parser')
        print(y.message.gcm.text)
        obj = json.loads(y.message.gcm.text)
        print(obj['message_type'])

    def start(self):
        self.connect(address=('fcm-xmpp.googleapis.com',5235),use_ssl=True,disable_starttls=False)
    def fcm_send(self,payload):
        self.send_raw('<message><gcm xmlns="google:mobile:data">{0}</gcm></message>'.format(payload))


    def reset_future(self):
        "Reset the future in case of disconnection"
        self.connected_future = asyncio.Future()


async def handle(request):
    "Handle the HTTP request and block until the vcard is fetched"
    err_404 = web.Response(status=404, text='Not found')
    body = await  request.json()
    print(body['notification'])


   
    try:
        XMPP['83403511783'].fcm_send(json.dumps(body))
    except Exception as e:
        print(e)
        log.warning("Failed to fetch vcard for")
        return err_404


    return web.Response(text="yes")

async def init(loop, host: str, port: str):
    "Initialize the HTTP server"
    app = web.Application(loop=loop)
    app.router.add_route('POST', '/', handle)
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

    for x  in data:
        XMPP[x['app_id']] = FCM(x['app_id'],x['app_key'])
    # XMPP= FCM(os.environ['FCM_SENDER_ID'], os.environ['FCM_SERVER_KEY'])
        XMPP[x['app_id']].start()
    #XMPP.connect()
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

HOST = '127.0.0.1'
PORT = 8768


if __name__ == "__main__":
    print(parse_args())
    main(parse_args())
