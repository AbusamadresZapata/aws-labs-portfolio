import os
import sys

os.environ.setdefault('BUCKET_PROCESSED',       'test-processed-bucket')
os.environ.setdefault('SNS_TOPIC_ARN',          'arn:aws:sns:us-east-1:123456789012:test-topic')
os.environ.setdefault('AWS_ACCESS_KEY_ID',      'testing')
os.environ.setdefault('AWS_SECRET_ACCESS_KEY',  'testing')
os.environ.setdefault('AWS_DEFAULT_REGION',     'us-east-1')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))
