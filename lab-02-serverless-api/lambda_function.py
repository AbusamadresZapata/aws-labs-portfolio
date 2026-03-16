import json
import boto3

# Inicializamos el cliente de DynamoDB
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('CloudResumes') # <--- ASEGÚRATE QUE SEA EL NOMBRE DE TU TABLA

def lambda_handler(event, context):
    # 1. Actualizamos el contador en DynamoDB
    response = table.update_item(
        Key={'id': 'visitors'},
        UpdateExpression='ADD visits :inc',
        ExpressionAttributeValues={':inc': 1},
        ReturnValues='UPDATED_NEW'
    )
    
    # 2. Obtenemos el nuevo valor
    count = response['Attributes']['visits']
    
    # 3. Retornamos la respuesta para API Gateway
    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Content-Type': 'application/json'
        },
        'body': json.dumps({'count': int(count)})
    }
