import boto3
import os

SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']


def lambda_handler(event, context):
    sns = boto3.client('sns', region_name='us-east-1')
    if event.get('triggerSource') != 'PostConfirmation_ConfirmSignUp':
        return event

    email = event.get('request', {}).get('userAttributes', {}).get('email', '')
    if not email:
        print('WARNING: PostConfirmation event missing email — skipping SNS subscribe')
        return event

    try:
        sns.subscribe(TopicArn=SNS_TOPIC_ARN, Protocol='email', Endpoint=email)
        print(f'INFO: SNS subscribe queued for {email}')
    except Exception as e:
        print(f'ERROR: sns.subscribe failed for {email}: {e}')

    return event
