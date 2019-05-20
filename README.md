# fcm-xmpp-http
Assuming the url https://www.example.com/get/app/keys returns a json array of the format 
`[{"app_id":"fcm_sender_id_1","app_key":"fcm_server_key_1"},{"app_id":"fcm_sender_id_2","app_key":"fcm_server_key_2"}]
`

Run the following to get started.

`docker build -t fcm-trial .`

`export APP_URL=https://www.example.com/get/app/keys`

`export REDIS_HOST=127.0.0.1`

`docker stack deploy -c docker-compose.yml pushserver`

Then you can do a post request to start sending push notifications.

POST http://127.0.0.1:8768/fcm_sender_id
`[{ "notification": {"title": "sample title","body": "new message 2","sound":"default"},"to" : "fcm_device_token","message_id":"123458846_478299338","priority":"high","delivery_receipt_requested":true}]
`


Run following to check notification status.

For sent or failed status run.

`redis> GET 20-05-2019_status_123458846_478299338`

For delivery status run.

`redis> GET 20-05-2019_message_123458846_478299338`

