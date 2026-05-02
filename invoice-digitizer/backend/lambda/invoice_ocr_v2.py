import boto3
import json
import os
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

try:
    import anthropic as _anthropic
    _anthropic_key = os.environ.get('ANTHROPIC_API_KEY')
    claude_client  = _anthropic.Anthropic(api_key=_anthropic_key) if _anthropic_key else None
except ImportError:
    claude_client = None

s3       = boto3.client('s3')
textract = boto3.client('textract', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
sns      = boto3.client('sns', region_name='us-east-1')

table            = dynamodb.Table('invoices')
BUCKET_PROCESSED = os.environ['BUCKET_PROCESSED']
SNS_TOPIC_ARN    = os.environ['SNS_TOPIC_ARN']


def lambda_handler(event, _context):
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
    claude_parsed  = _parse_with_claude(full_text)
    classic_parsed = _parse_invoice(lines, full_text, blocks)
    parsed = _merge_results(claude_parsed, classic_parsed) if claude_parsed else classic_parsed
    print(f"Parser: {'Claude+merge' if claude_parsed else 'clásico'} | "
          f"vendor={parsed.get('vendor')} total={parsed.get('total')} items={parsed['items_count']}")

    # ── 4. DYNAMODB ──────────────────────────────────────────
    table.put_item(Item={
        'user_id':        user_id,
        'invoice_id':     invoice_id,
        'processed_at':   datetime.utcnow().isoformat(),
        'status':         'completed',
        'total':          _dec(parsed['total']),
        'subtotal':       _dec(parsed.get('subtotal')),
        'discount':       _dec(parsed.get('discount')),
        'invoice_number': parsed['invoice_number'] or 'N/A',
        'date':           parsed['date'] or 'N/A',
        'vendor':         parsed['vendor'] or 'N/A',
        'nit':            parsed.get('nit') or 'N/A',
        'client_name':    parsed.get('client_name') or 'N/A',
        'address':        parsed.get('address') or 'N/A',
        'items_count':    parsed['items_count'],
        'items_json':     json.dumps(parsed.get('items', [])),
        'raw_text':       full_text[:2000],
        'confidence':     _dec(confidence),
        's3_key':         s3_key,
    })

    # ── 5. EMAIL ─────────────────────────────────────────────
    _notify(parsed, confidence)

    return {'statusCode': 200, 'invoice_id': invoice_id}


# ── CLAUDE PARSER ─────────────────────────────────────────────

def _parse_with_claude(full_text):
    if claude_client is None:
        return None

    prompt = (
        "Eres un extractor de datos de facturas y recibos colombianos.\n"
        "Del siguiente texto extraído por OCR, extrae los campos en formato JSON.\n\n"
        "Reglas:\n"
        "- total, subtotal, discount: número sin símbolo de moneda. "
        "Formato colombiano '1.234.567,89' → 1234567.89. null si no está.\n"
        "- invoice_number: número del recibo o factura (null si no está)\n"
        "- date: fecha en formato DD/MM/YYYY (null si no está)\n"
        "- vendor: nombre del comercio o empresa emisora (null si no está)\n"
        "- nit: NIT/RUC del vendedor, solo dígitos y guion (null si no está)\n"
        "- client_name: nombre del comprador (null si no está)\n"
        "- address: dirección del comercio (null si no está)\n"
        "- items: lista [{producto, cantidad, precio_unit, valor_total}] o [] si no hay tabla\n\n"
        "Responde ÚNICAMENTE con el JSON válido, sin texto adicional ni bloques markdown.\n\n"
        f"TEXTO:\n{full_text[:4000]}"
    )

    try:
        msg = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = msg.content[0].text.strip()
        if raw.startswith('```'):
            raw = re.sub(r'^```\w*\n?', '', raw)
            raw = re.sub(r'\n?```$', '', raw.strip())

        data = json.loads(raw)

        items = []
        for idx, it in enumerate(data.get('items') or [], start=1):
            producto = str(it.get('producto') or '').strip()
            if not producto:
                continue
            items.append({
                'item':          str(idx),
                'referencia':    '',
                'producto':      producto,
                'unidad':        '',
                'cantidad':      _num(str(it['cantidad'])) if it.get('cantidad') is not None else None,
                'precio_unit':   _num(str(it['precio_unit'])) if it.get('precio_unit') is not None else None,
                'descuento_pct': None,
                'valor_total':   _num(str(it['valor_total'])) if it.get('valor_total') is not None else None,
            })

        return {
            'total':          _num(str(data['total'])) if data.get('total') is not None else None,
            'subtotal':       _num(str(data['subtotal'])) if data.get('subtotal') is not None else None,
            'discount':       _num(str(data['discount'])) if data.get('discount') is not None else None,
            'invoice_number': str(data['invoice_number']).strip() if data.get('invoice_number') else None,
            'date':           str(data['date']).strip() if data.get('date') else None,
            'vendor':         str(data['vendor']).strip() if data.get('vendor') else None,
            'nit':            str(data['nit']).strip() if data.get('nit') else None,
            'client_name':    str(data['client_name']).strip() if data.get('client_name') else None,
            'address':        str(data['address']).strip() if data.get('address') else None,
            'items':          items,
            'items_count':    len(items),
        }

    except Exception as e:
        print(f"WARNING Claude parsing falló, usando parser clásico: {e}")
        return None


def _merge_results(claude, classic):
    TEXT_FIELDS = [
        'total', 'subtotal', 'discount', 'invoice_number',
        'date', 'vendor', 'nit', 'client_name', 'address',
    ]
    merged = {}
    for field in TEXT_FIELDS:
        merged[field] = claude.get(field) if claude.get(field) is not None else classic.get(field)

    if classic.get('items'):
        merged['items'] = classic['items']
        merged['items_count'] = classic['items_count']
    else:
        merged['items'] = claude.get('items', [])
        merged['items_count'] = len(merged['items'])

    return merged


# ── PARSER CLÁSICO (fallback) ──────────────────────────────────

def _parse_invoice(lines, full_text, blocks):
    result = {
        'total':          None,
        'subtotal':       None,
        'discount':       None,
        'invoice_number': None,
        'date':           None,
        'vendor':         None,
        'nit':            None,
        'client_name':    None,
        'address':        None,
        'items_count':    0,
        'items':          [],
    }

    # Estrategia 1: pares clave:valor de Textract FORMS (más preciso)
    kv = _extract_kv(blocks)
    for k, v in kv.items():
        kl = k.lower().strip()
        if any(x in kl for x in ['total a pagar', 'gran total', 'a pagar', 'valor total']):
            result['total'] = result['total'] or _num(v)
        elif 'total' in kl and result['total'] is None:
            result['total'] = _num(v)
        if 'subtotal' in kl:
            result['subtotal'] = result['subtotal'] or _num(v)
        if any(x in kl for x in ['descuento', 'discount']):
            result['discount'] = result['discount'] or _num(v)
        if any(x in kl for x in ['factura', 'recibo', 'ticket', 'folio', 'no.', 'número', 'invoice']):
            result['invoice_number'] = result['invoice_number'] or v.strip()
        if any(x in kl for x in ['fecha', 'date', 'emision', 'hora']):
            result['date'] = result['date'] or v.strip()
        if any(x in kl for x in ['nit', 'ruc', 'rif']):
            result['nit'] = result['nit'] or v.strip()

    # Estrategia 2: regex sobre texto plano (fallback)
    if result['total'] is None:
        result['total'] = _regex_total(full_text)
    if result['invoice_number'] is None:
        result['invoice_number'] = _regex_invoice_num(full_text)
    if result['date'] is None:
        result['date'] = _regex_date(full_text)
    if result['nit'] is None:
        result['nit'] = _regex_nit(full_text)

    # Vendedor: primera línea de texto significativa
    for line in lines[:6]:
        s = line.strip()
        if len(s) > 5 and not re.match(r'^[\d\s\$\.\,\-\/\:NIT]+$', s):
            result['vendor'] = s
            break

    # Cliente: busca patrón después de "Señores:" o "Cliente:"
    cliente_match = re.search(
        r'(?:Señores?|Cliente|Comprador)[:\s]+([A-Z][A-Z\s]{4,50})',
        full_text
    )
    if cliente_match:
        result['client_name'] = cliente_match.group(1).strip()

    # Dirección
    dir_match = re.search(
        r'(?:Dirección|Direccion|Calle|Carrera|Avenida|Cra\.?|Cl\.?)[:\s]+([^\n]{5,60})',
        full_text, re.IGNORECASE
    )
    if dir_match:
        result['address'] = dir_match.group(1).strip()

    # Extraer tabla de productos desde bloques TABLE de Textract
    result['items'] = _extract_table_items(blocks)

    if result['items']:
        result['items_count'] = len(result['items'])
    else:
        result['items_count'] = sum(
            1 for line in lines
            if re.match(r'^\d[\d,.]?\s+.{3,}.+\$?[\d\.,]+$', line.strip())
        )

    return result


def _extract_table_items(blocks):
    """
    Extrae filas de la tabla de productos usando los bloques TABLE de Textract.
    Devuelve lista de dicts con los campos de cada línea de producto.
    """
    items = []
    block_map = {b['Id']: b for b in blocks}

    for block in blocks:
        if block['BlockType'] != 'TABLE':
            continue

        # Recolectar todas las celdas organizadas por (fila, columna)
        cells = {}
        for rel in block.get('Relationships', []):
            if rel['Type'] != 'CHILD':
                continue
            for cell_id in rel['Ids']:
                cell = block_map.get(cell_id)
                if not cell or cell['BlockType'] != 'CELL':
                    continue
                row = cell['RowIndex']
                col = cell['ColumnIndex']
                cells.setdefault(row, {})[col] = _cell_text(cell, block_map)

        if not cells:
            continue

        # Detectar si es tabla de productos por el encabezado (fila 1)
        header_row = cells.get(1, {})
        header_text = ' '.join(header_row.values()).lower()
        is_product_table = any(
            k in header_text
            for k in ['producto', 'descripci', 'referencia', 'item', 'articulo', 'detalle']
        )
        if not is_product_table:
            continue

        # Mapear columnas por texto del encabezado
        col_map = {}
        for col_idx, col_text in header_row.items():
            ct = col_text.lower().strip()
            if ct in ('#', 'item', 'it'):
                col_map['item'] = col_idx
            elif any(x in ct for x in ['referencia', 'ref', 'codigo', 'código']):
                col_map['referencia'] = col_idx
            elif any(x in ct for x in ['producto', 'descripci', 'articulo', 'detalle', 'nombre']):
                col_map['producto'] = col_idx
            elif any(x in ct for x in ['und', 'unidad', 'um']):
                col_map['unidad'] = col_idx
            elif any(x in ct for x in ['cantidad', 'cant', 'qty']):
                col_map['cantidad'] = col_idx
            elif any(x in ct for x in ['precio unit', 'valor unit', 'p. unit', 'unit']):
                col_map['precio_unit'] = col_idx
            elif 'desc' in ct and ('%' in ct or 'cuento' in ct):
                col_map['descuento'] = col_idx
            elif any(x in ct for x in ['valor total', 'total', 'importe', 'subtotal']):
                col_map['valor_total'] = col_idx

        if 'producto' not in col_map:
            continue

        # Extraer filas de datos (fila 1 = encabezado, se salta)
        for row_idx in sorted(cells.keys()):
            if row_idx == 1:
                continue
            row = cells[row_idx]

            producto = row.get(col_map['producto'], '').strip()
            if not producto or len(producto) < 3:
                continue

            # Saltar filas de resumen financiero
            if any(x in producto.lower() for x in
                   ['total', 'subtotal', 'iva', 'descuento', 'son:', 'pronto pago',
                    'impuest', 'retenci']):
                continue

            item = {
                'item':          row.get(col_map.get('item', 0), str(row_idx - 1)).strip(),
                'referencia':    row.get(col_map.get('referencia', 0), '').strip(),
                'producto':      producto,
                'unidad':        row.get(col_map.get('unidad', 0), '').strip(),
                'cantidad':      _num(row.get(col_map.get('cantidad', 0), '')),
                'precio_unit':   _num(row.get(col_map.get('precio_unit', 0), '')),
                'descuento_pct': _num(row.get(col_map.get('descuento', 0), '')),
                'valor_total':   _num(row.get(col_map.get('valor_total', 0), '')),
            }
            items.append(item)

    return items


def _cell_text(cell, block_map):
    """Extrae el texto de una celda concatenando sus WORDs."""
    words = []
    for rel in cell.get('Relationships', []):
        if rel['Type'] == 'CHILD':
            for word_id in rel['Ids']:
                word = block_map.get(word_id)
                if word and word['BlockType'] == 'WORD':
                    words.append(word.get('Text', ''))
    return ' '.join(words)


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


# ── REGEX FALLBACKS ──────────────────────────────────────────

def _regex_total(text):
    patterns = [
        r'(?:TOTAL A PAGAR|GRAN TOTAL|A PAGAR|VALOR TOTAL|TOTAL)[:\s\*]+\$?\s*([\d\.,]+)',
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


def _regex_nit(text):
    m = re.search(r'NIT[:\s]*(\d[\d\.\-]{5,15})', text, re.IGNORECASE)
    return m.group(1).strip() if m else None


# ── UTILIDADES ────────────────────────────────────────────────

def _num(text):
    if not text:
        return None
    clean = re.sub(r'[$€£\s%]', '', str(text))
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
            'user_id':        user_id,
            'invoice_id':     invoice_id,
            'processed_at':   datetime.utcnow().isoformat(),
            'status':         'error',
            'error':          msg,
            's3_key':         s3_key,
            'total':          Decimal('0'),
            'invoice_number': 'ERROR',
            'date':           'N/A',
            'vendor':         'N/A',
            'items_count':    0,
            'confidence':     Decimal('0'),
        })
    except Exception as e:
        print(f"ERROR guardando error en DynamoDB: {e}")


def _notify(parsed, confidence):
    total_fmt    = f"${parsed['total']:,.0f} COP" if parsed['total'] else 'No detectado'
    subtotal_fmt = f"${parsed['subtotal']:,.0f} COP" if parsed.get('subtotal') else '-'
    discount_fmt = f"${parsed['discount']:,.0f} COP" if parsed.get('discount') else '-'

    items = parsed.get('items', [])
    if items:
        header = f"{'#':<4} {'Producto':<45} {'Cant':<5} {'Total'}\n{'─' * 68}"
        lines  = []
        for it in items[:30]:
            qty   = f"{it['cantidad']:.0f}" if it['cantidad'] else '?'
            price = f"${it['valor_total']:,.0f}" if it['valor_total'] else '-'
            desc  = (it['producto'] or '')[:45]
            lines.append(f"{it.get('item', ''):<4} {desc:<45} x{qty:<5} {price}")
        if len(items) > 30:
            lines.append(f"... y {len(items) - 30} productos más")
        items_block = header + '\n' + '\n'.join(lines)
    else:
        items_block = '  No se detectó tabla estructurada de productos.'

    mensaje = (
        f"FACTURA PROCESADA — Invoice Digitizer\n"
        f"{'=' * 60}\n\n"
        f"EMISOR\n"
        f"  Empresa  : {parsed.get('vendor') or 'No detectado'}\n"
        f"  NIT      : {parsed.get('nit') or 'No detectado'}\n"
        f"  Dirección: {parsed.get('address') or 'No detectada'}\n\n"
        f"FACTURA\n"
        f"  Número   : {parsed.get('invoice_number') or 'No detectado'}\n"
        f"  Fecha    : {parsed.get('date') or 'No detectada'}\n"
        f"  Cliente  : {parsed.get('client_name') or 'No detectado'}\n\n"
        f"FINANCIERO\n"
        f"  Subtotal : {subtotal_fmt}\n"
        f"  Descuento: {discount_fmt}\n"
        f"  Total    : {total_fmt}\n\n"
        f"PRODUCTOS ({len(items)} líneas detectadas)\n"
        f"{items_block}\n\n"
        f"{'─' * 60}\n"
        f"Confianza OCR : {confidence:.1f}%\n"
        f"Ingresa a la app para ver el JSON original completo."
    )

    try:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"Factura procesada: {parsed.get('invoice_number') or 'Sin número'} — {total_fmt}",
            Message=mensaje
        )
    except Exception as e:
        print(f"WARNING SNS: {e}")
