import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

os.environ.setdefault('SNS_TOPIC_ARN',
                      'arn:aws:sns:us-east-1:123456789012:invoice-notifications')
os.environ.setdefault('AWS_ACCESS_KEY_ID', 'testing')
os.environ.setdefault('AWS_SECRET_ACCESS_KEY', 'testing')
os.environ.setdefault('AWS_DEFAULT_REGION', 'us-east-1')

import boto3
import pytest
from moto import mock_aws

from cognito_post_confirm import lambda_handler

TOPIC_ARN = os.environ['SNS_TOPIC_ARN']


def build_event(trigger_source='PostConfirmation_ConfirmSignUp',
                email='user@example.com'):
    return {
        'triggerSource': trigger_source,
        'request': {
            'userAttributes': {'email': email, 'sub': 'user-uuid-123'}
        }
    }


@mock_aws
def test_confirm_signup_subscribes_email():
    boto3.client('sns', region_name='us-east-1').create_topic(
        Name='invoice-notifications')

    event = build_event()
    result = lambda_handler(event, {})

    subs = boto3.client('sns', region_name='us-east-1') \
        .list_subscriptions_by_topic(TopicArn=TOPIC_ARN)['Subscriptions']

    assert result == event
    assert any(s['Endpoint'] == 'user@example.com' for s in subs)


@mock_aws
def test_forgot_password_does_not_subscribe():
    sns = boto3.client('sns', region_name='us-east-1')
    sns.create_topic(Name='invoice-notifications')

    event = build_event(trigger_source='PostConfirmation_ConfirmForgotPassword')
    result = lambda_handler(event, {})

    subs = sns.list_subscriptions_by_topic(TopicArn=TOPIC_ARN)['Subscriptions']

    assert result == event
    assert subs == []


@mock_aws
def test_missing_email_does_not_raise():
    boto3.client('sns', region_name='us-east-1').create_topic(
        Name='invoice-notifications')

    event = {
        'triggerSource': 'PostConfirmation_ConfirmSignUp',
        'request': {'userAttributes': {'sub': 'user-uuid-123'}}
    }
    result = lambda_handler(event, {})

    assert result == event


@mock_aws
def test_sns_failure_does_not_raise():
    # Topic deliberately not created → sns.subscribe raises an error
    event = build_event()
    result = lambda_handler(event, {})

    assert result == event
