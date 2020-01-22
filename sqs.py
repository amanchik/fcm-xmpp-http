import boto3
import json
import os
# Create SQS client
sqs = boto3.client('sqs', aws_access_key_id=os.environ['AWS_ID'],
                      aws_secret_access_key=os.environ['AWS_KEY'],
                      region_name='ap-south-1')

queue_url = 'https://sqs.ap-south-1.amazonaws.com/706557323832/reports'

# Send message to SQS queue
response = sqs.send_message(
    QueueUrl=queue_url,
    DelaySeconds=10,
    MessageAttributes={
        'Type':{
            'DataType': 'String',
            'StringValue': 'Receipt'
        }
    },
    MessageBody=json.dumps({
        'id' : 123,
        'data' : {
            'online_notification_sent_at':3232
        }
    })
)

print(response['MessageId'])