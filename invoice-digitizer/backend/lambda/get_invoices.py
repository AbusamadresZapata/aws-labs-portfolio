import boto3
import json
import os
from decimal import Decimal
from boto3.dynamodb.conditions import Key

# Inicialización de recursos
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table    = dynamodb.Table('invoices')

# Buscamos la LLAVE 'FRONTEND_URL' en las variables de entorno
FRONTEND_URL = os.environ.get('FRONTEND_URL')


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def lambda_handler(event, context):
    try:
        # Extraer user_id del token de Cognito
        user_id = event['requestContext']['authorizer']['claims']['sub']
    except KeyError:
        return _r(401, {'error': 'No autorizado'})

    params = event.get('queryStringParameters') or {}
    limit  = min(int(params.get('limit', 50)), 100)

    try:
        # CONSULTA: user_id es tu Partition Key
        response = table.query(
            KeyConditionExpression=Key('user_id').eq(user_id),
            # NOTA: Al ser 'invoice_id' la Sort Key,
            # el ordenamiento será por ID, no necesariamente por fecha.
            ScanIndexForward=False,
            Limit=limit,
        )
        items = response['Items']

        # Limpieza de datos pesados
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
