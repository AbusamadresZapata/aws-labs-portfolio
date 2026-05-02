import boto3
import json
import uuid
import os
from datetime import datetime

# Configuración del cliente S3
s3 = boto3.client('s3', region_name='us-east-1')

# AQUÍ ESTÁ EL CAMBIO: Buscamos las llaves, no los valores
BUCKET_RAW     = os.environ.get('BUCKET_RAW')
FRONTEND_URL   = os.environ.get('FRONTEND_URL')
EXPIRY_SECONDS = 300


def lambda_handler(event, context):
    # Verificación de claims (Cognito Authorizer)
    try:
        claims    = event['requestContext']['authorizer']['claims']
        user_id   = claims['sub']
        user_email = claims.get('email', 'unknown')
    except KeyError:
        return _r(401, {'error': 'No autorizado o falta token'})

    # Obtener tipo de contenido del body (enviado desde React)
    try:
        body         = json.loads(event.get('body') or '{}')
        content_type = body.get('content_type', 'image/jpeg')
    except Exception:
        content_type = 'image/jpeg'

    # Validación de formatos
    allowed = ['image/jpeg', 'image/jpg', 'image/png', 'image/heic', 'image/webp']
    if content_type not in allowed:
        return _r(400, {'error': f'Tipo no permitido: {content_type}'})

    # Generación de ruta única
    invoice_id = str(uuid.uuid4())
    timestamp  = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    ext        = content_type.split('/')[-1].replace('jpeg', 'jpg')
    s3_key     = f"uploads/{user_id}/{invoice_id}_{timestamp}.{ext}"

    try:
        # Generar la URL firmada para que el Frontend suba el archivo
        url = s3.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET_RAW,
                'Key': s3_key,
                'ContentType': content_type
            },
            ExpiresIn=EXPIRY_SECONDS
        )
    except Exception as e:
        print(f"ERROR presigned URL: {e}")
        return _r(500, {'error': 'No se pudo generar URL'})

    print(f"URL generada: user={user_email} invoice={invoice_id}")
    return _r(200, {
        'upload_url': url,
        'invoice_id': invoice_id,
        's3_key': s3_key
    })


def _r(code, body):
    return {
        'statusCode': code,
        'headers': {
            'Access-Control-Allow-Origin': FRONTEND_URL,
            'Access-Control-Allow-Credentials': 'true',
            'Content-Type': 'application/json'
        },
        'body': json.dumps(body)
    }
