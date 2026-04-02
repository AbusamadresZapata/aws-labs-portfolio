import boto3
import json
import os
from decimal import Decimal
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table    = dynamodb.Table('invoices')

FRONTEND_URL = os.environ['https://main.d11vt37abx4lx9.amplifyapp.com/']


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def lambda_handler(event, context):
    # user_id siempre del JWT — nunca de un parámetro manipulable
    user_id = event['requestContext']['authorizer']['claims']['sub']

    params = event.get('queryStringParameters') or {}
    limit  = min(int(params.get('limit', 50)), 100)

    try:
        response = table.query(
            KeyConditionExpression=Key('user_id').eq(user_id),
            ScanIndexForward=False,   # más recientes primero
            Limit=limit,
        )
        items = response['Items']

        # Quitar raw_text del listado (solo para vista de detalle)
        for item in items:
            item.pop('raw_text', None)

        return _r(200, {'invoices': items, 'count': len(items)})

    except Exception as e:
        print(f"ERROR DynamoDB: {e}")
        return _r(500, {'error': 'Error al obtener recibos'})


def _r(code, body):
    return {
        'statusCode': code,
        'headers': {
            'Access-Control-Allow-Origin': FRONTEND_URL,
            'Access-Control-Allow-Credentials': 'true',
            'Content-Type': 'application/json',
        },
        'body': json.dumps(body, cls=DecimalEncoder)
    }