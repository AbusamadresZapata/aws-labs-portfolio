import boto3
import json
import os
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

s3       = boto3.client('s3')
textract = boto3.client('textract', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
sns      = boto3.client('sns', region_name='us-east-1')

table            = dynamodb.Table('invoices')
BUCKET_PROCESSED = os.environ['BUCKET_PROCESSED']
SNS_TOPIC_ARN    = os.environ['SNS_TOPIC_ARN']


def lambda_handler(event, context):
    record    = event['Records'][0]
    bucket_in = record['s3']['bucket']['name']
    s3_key    = record['s3']['object']['key']

    print(f"Procesando: s3://{bucket_in}/{s3_key}")

    parts = s3_key.split('/')
    if len(parts) < 3:
        print(f"ERROR: path inesperado: {s3_key}")
        return {'statusCode': 400}

    user_id    = parts[1]
    invoice_id = parts[2].split('_')[0]

    # ── 1. TEXTRACT ──────────────────────────────────────────
    # FORMS detecta pares clave:valor ("TOTAL: $55.000")
    # TABLES detecta filas de productos con columnas alineadas
    try:
        response = textract.analyze_document(
            Document={'S3Object': {'Bucket': bucket_in, 'Name': s3_key}},
            FeatureTypes=['TABLES', 'FORMS']
        )
    except textract.exceptions.UnsupportedDocumentException:
        _save_error(user_id, invoice_id, s3_key, "Formato no soportado")
        return {'statusCode': 400}
    except Exception as e:
        print(f"ERROR Textract: {e}")
        _save_error(user_id, invoice_id, s3_key, str(e))
        return {'statusCode': 500}

    # ── 2. EXTRAER TEXTO ─────────────────────────────────────
    blocks     = response['Blocks']
    lines      = [b['Text'] for b in blocks if b['BlockType'] == 'LINE']
    full_text  = '\n'.join(lines)
    confidence = _calc_confidence(blocks)

    # Guardar JSON completo de Textract en S3 processed (auditoría)
    s3.put_object(
        Bucket=BUCKET_PROCESSED,
        Key=f"results/{user_id}/{invoice_id}.json",
        Body=json.dumps(response, default=str),
        ContentType='application/json'
    )

    # ── 3. PARSEAR CAMPOS ────────────────────────────────────
    parsed = _parse_invoice(lines, full_text, blocks)
    print(f"Parsed: {parsed}")

    # ── 4. DYNAMODB ──────────────────────────────────────────
    table.put_item(Item={
        'user_id':        user_id,
        'invoice_id':     invoice_id,
        'processed_at':   datetime.utcnow().isoformat(),
        'status':         'completed',
        'total':          _dec(parsed['total']),
        'invoice_number': parsed['invoice_number'] or 'N/A',
        'date':           parsed['date'] or 'N/A',
        'vendor':         parsed['vendor'] or 'N/A',
        'items_count':    parsed['items_count'],
        'raw_text':       full_text[:2000],
        'confidence':     _dec(confidence),
        's3_key':         s3_key,
    })

    # ── 5. EMAIL ─────────────────────────────────────────────
    _notify(parsed, confidence)

    return {'statusCode': 200, 'invoice_id': invoice_id}


# ── PARSER ───────────────────────────────────────────────────

def _parse_invoice(lines, full_text, blocks):
    result = {'total': None, 'invoice_number': None,
              'date': None, 'vendor': None, 'items_count': 0}

    # Estrategia 1: pares clave:valor de Textract FORMS (más preciso)
    kv = _extract_kv(blocks)
    for k, v in kv.items():
        kl = k.lower()
        if any(x in kl for x in ['total', 'a pagar', 'valor total', 'gran total']):
            result['total'] = result['total'] or _num(v)
        elif any(x in kl for x in ['factura', 'recibo', 'ticket', 'folio', 'no.']):
            result['invoice_number'] = result['invoice_number'] or v.strip()
        elif any(x in kl for x in ['fecha', 'date', 'emision']):
            result['date'] = result['date'] or v.strip()

    # Estrategia 2: regex sobre texto plano (fallback)
    if result['total'] is None:
        result['total'] = _regex_total(full_text)
    if result['invoice_number'] is None:
        result['invoice_number'] = _regex_invoice_num(full_text)
    if result['date'] is None:
        result['date'] = _regex_date(full_text)

    # Vendedor: primera línea de texto significativa
    for line in lines[:6]:
        s = line.strip()
        if len(s) > 3 and not re.match(r'^[\d\s\$\.\,\-\/\:]+$', s):
            result['vendor'] = s
            break

    # Contar productos: líneas con patrón "qty descripcion precio"
    result['items_count'] = sum(
        1 for l in lines if re.match(r'^\d[\d,.]?\s+.{3,}.+\$?[\d\.,]+$', l.strip())
    )

    return result


def _extract_kv(blocks):
    bmap = {b['Id']: b for b in blocks}
    kv   = {}
    for b in blocks:
        if b['BlockType'] == 'KEY_VALUE_SET' and 'KEY' in b.get('EntityTypes', []):
            key_txt = _get_text(b, bmap)
            for rel in b.get('Relationships', []):
                if rel['Type'] == 'VALUE':
                    for vid in rel['Ids']:
                        val_txt = _get_text(bmap.get(vid, {}), bmap)
                        if key_txt and val_txt:
                            kv[key_txt] = val_txt
    return kv


def _get_text(block, bmap):
    txt = ''
    for rel in block.get('Relationships', []):
        if rel['Type'] == 'CHILD':
            for cid in rel['Ids']:
                c = bmap.get(cid, {})
                if c.get('BlockType') == 'WORD':
                    txt += ' ' + c.get('Text', '')
    return txt.strip()


def _regex_total(text):
    patterns = [
        r'(?:TOTAL|GRAN TOTAL|A PAGAR|VALOR TOTAL)[:\s\*]+\$?\s*([\d\.,]+)',
        r'\$\s*([\d\.,]+)\s*$',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE | re.MULTILINE)
        if m:
            return _num(m.group(1))
    return None


def _regex_invoice_num(text):
    patterns = [
        r'(?:FACTURA|FAC|TICKET|RECIBO|BOLETA|FOLIO|No\.?|#)[:\s]*([A-Z0-9\-]{3,20})',
        r'(?:INVOICE|RECEIPT)\s*#?\s*([A-Z0-9\-]{3,20})',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _regex_date(text):
    patterns = [
        r'\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})\b',
        r'\b(\d{4}[/\-]\d{2}[/\-]\d{2})\b',
        r'\b(\d{1,2}\s+(?:ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)[a-z]*\.?\s+\d{2,4})\b',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def _num(text):
    if not text:
        return None
    clean = re.sub(r'[$€£\s]', '', str(text))
    # Formato colombiano: 1.234.567,89
    if re.match(r'^\d{1,3}(\.\d{3})+(,\d+)?$', clean):
        clean = clean.replace('.', '').replace(',', '.')
    else:
        clean = clean.replace(',', '')
    try:
        return float(clean)
    except ValueError:
        return None


def _calc_confidence(blocks):
    scores = [b['Confidence'] for b in blocks if 'Confidence' in b]
    return sum(scores) / len(scores) if scores else 0.0


def _dec(value):
    try:
        return Decimal(str(round(value, 2))) if value is not None else Decimal('0')
    except (InvalidOperation, TypeError):
        return Decimal('0')


def _save_error(user_id, invoice_id, s3_key, msg):
    try:
        table.put_item(Item={
            'user_id': user_id, 'invoice_id': invoice_id,
            'processed_at': datetime.utcnow().isoformat(),
            'status': 'error', 'error': msg, 's3_key': s3_key,
            'total': Decimal('0'), 'invoice_number': 'ERROR',
            'date': 'N/A', 'vendor': 'N/A',
            'items_count': 0, 'confidence': Decimal('0'),
        })
    except Exception as e:
        print(f"ERROR guardando error en DynamoDB: {e}")


def _notify(parsed, confidence):
    total_fmt = f"${parsed['total']:,.0f}" if parsed['total'] else 'No detectado'
    try:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"Recibo digitalizado: {parsed['invoice_number'] or 'Sin número'}",
            Message=(
                f"Tu recibo fue procesado exitosamente.\n\n"
                f"Número  : {parsed['invoice_number'] or 'No detectado'}\n"
                f"Fecha   : {parsed['date'] or 'No detectada'}\n"
                f"Comercio: {parsed['vendor'] or 'No detectado'}\n"
                f"Total   : {total_fmt}\n"
                f"Productos detectados: {parsed['items_count']}\n"
                f"Confianza OCR: {confidence:.1f}%\n\n"
                f"Ingresa a la app para ver el detalle completo."
            )
        )
    except Exception as e:
        print(f"WARNING SNS: {e}")  # no bloquea el flujo principal
