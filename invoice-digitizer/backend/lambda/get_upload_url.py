import boto3
import json
import uuid
import os
from datetime import datetime

s3 = boto3.client('s3', region_name='us-east-1')

BUCKET_RAW     = os.environ['BUCKET_RAW']
FRONTEND_URL   = os.environ['FRONTEND_URL']
EXPIRY_SECONDS = 300


def lambda_handler(event, context):
    claims    = event['requestContext']['authorizer']['claims']
    user_id   = claims['sub']
    user_email = claims.get('email', 'unknown')

    try:
        body         = json.loads(event.get('body') or '{}')
        content_type = body.get('content_type', 'image/jpeg')
    except Exception:
        content_type = 'image/jpeg'

    allowed = ['image/jpeg', 'image/jpg', 'image/png', 'image/heic', 'image/webp']
    if content_type not in allowed:
        return _r(400, {'error': f'Tipo no permitido: {content_type}'})

    invoice_id = str(uuid.uuid4())
    timestamp  = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    ext        = content_type.split('/')[-1].replace('jpeg', 'jpg')
    s3_key     = f"uploads/{user_id}/{invoice_id}_{timestamp}.{ext}"

    try:
        url = s3.generate_presigned_url(
            'put_object',
            Params={'Bucket': BUCKET_RAW, 'Key': s3_key, 'ContentType': content_type},
            ExpiresIn=EXPIRY_SECONDS
        )
    except Exception as e:
        print(f"ERROR presigned URL: {e}")
        return _r(500, {'error': 'No se pudo generar URL'})

    print(f"URL generada: user={user_email} invoice={invoice_id}")
    return _r(200, {'upload_url': url, 'invoice_id': invoice_id, 's3_key': s3_key})


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