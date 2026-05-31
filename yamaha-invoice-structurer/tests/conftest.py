import os
import sys

os.environ.setdefault('AWS_ACCESS_KEY_ID',     'testing')
os.environ.setdefault('AWS_SECRET_ACCESS_KEY', 'testing')
os.environ.setdefault('AWS_DEFAULT_REGION',    'us-east-1')
os.environ.setdefault('ANTHROPIC_API_KEY',     'sk-ant-test-key')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
