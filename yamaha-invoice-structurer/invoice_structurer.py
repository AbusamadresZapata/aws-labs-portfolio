#!/usr/bin/env python3
"""
invoice_structurer.py — Skill local: PDF Incolmotos Yamaha → CSV estructurado.

Flujo: PDF local → Textract async (texto completo) → Claude sonnet → validación → CSV

Uso:
    python invoice_structurer.py <pdf> --bucket <s3-bucket> [--out salida.csv]

Variables de entorno:
    ANTHROPIC_API_KEY         clave de la API de Anthropic
    AWS_DEFAULT_REGION        default: us-east-1
    AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY  (o perfil AWS configurado)
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime
from io import StringIO

import boto3

REGION   = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
s3       = boto3.client('s3', region_name=REGION)
textract = boto3.client('textract', region_name=REGION)
bedrock  = boto3.client('bedrock-runtime', region_name=REGION)

MODEL = 'us.anthropic.claude-sonnet-4-6'

HEADERS = [
    'Factura', 'Fecha', 'Pedido No', 'Referencia', 'Producto',
    'Cantidad', 'Precio Unit.', 'Descuento', 'Valor Total',
    'Archivo', 'Fecha Proceso',
]

# Patrón de referencia de repuesto: alfanumérico, 6-16 chars, con dígitos
REF_PATTERN = re.compile(r'^[A-Z0-9 ]{6,16}$')


# ── 1. OCR ───────────────────────────────────────────────────────────────────

def pdf_to_text(pdf_path: str, bucket: str) -> str:
    """Sube PDF a S3, ejecuta Textract async, devuelve texto de todas las páginas."""
    key = f"tmp/structurer/{uuid.uuid4().hex}/{os.path.basename(pdf_path)}"

    print(f"[1/4] Subiendo '{os.path.basename(pdf_path)}' → s3://{bucket}/{key}")
    with open(pdf_path, 'rb') as f:
        s3.upload_fileobj(f, bucket, key)

    print("[2/4] Iniciando Textract (detección de texto, multi-página)...")
    resp   = textract.start_document_text_detection(
        DocumentLocation={'S3Object': {'Bucket': bucket, 'Name': key}}
    )
    job_id = resp['JobId']

    while True:
        result = textract.get_document_text_detection(JobId=job_id)
        status = result['JobStatus']
        if status == 'SUCCEEDED':
            break
        if status == 'FAILED':
            raise RuntimeError(f"Textract FAILED: {result.get('StatusMessage')}")
        print(f"    Estado: {status} — esperando 5 s...")
        time.sleep(5)

    lines = []
    while True:
        lines.extend(
            b['Text'] for b in result.get('Blocks', []) if b['BlockType'] == 'LINE'
        )
        next_token = result.get('NextToken')
        if not next_token:
            break
        result = textract.get_document_text_detection(JobId=job_id, NextToken=next_token)

    s3.delete_object(Bucket=bucket, Key=key)

    full_text = '\n'.join(lines)
    print(f"    OCR listo: {len(lines)} líneas / {len(full_text)} caracteres")
    return full_text


# ── 2. CLAUDE ────────────────────────────────────────────────────────────────

_PROMPT = """\
Eres un experto en facturas electrónicas de Incolmotos Yamaha Colombia.
Extrae los datos de la factura del texto OCR que aparece al final.

REGLA 1 — Número de factura:
El número real está en el encabezado como "FACTURA ELECTRÓNICA DE VENTA No. CPFE-XXXXXX".
La resolución de facturación ("del CPFE-600001 al CPFE-1300000") NO es el número.
Ejemplo: "No. CPFE-706253" → numero_factura = "CPFE-706253"

REGLA 2 — Agrupación por pedido:
Líneas "Pedido No. PVXXXXXXXX REMV+XXXXXXXX:" son encabezados de grupo.
Los productos que siguen pertenecen a ese pedido hasta que aparezca otro encabezado.
Si no hay encabezados de pedido, usa numero_pedido: null.

REGLA 3 — Alineación referencia-producto (CRÍTICA):
"Referencia" = código de pieza alfanumérico (ej: 4STE81110000, B6HF74840000).
"Producto" = descripción textual (ej: PEDAL CAMBIOS T110E T110ED).
La referencia SIEMPRE tiene dígitos y letras mezclados, ≤16 caracteres.
La descripción SIEMPRE es una frase legible. NUNCA las intercambies.

REGLA 4 — Valor Total faltante:
Si valor_total es 0 o está ausente, calcula: cantidad × precio_unit × (1 − descuento).
Convierte formato colombiano: "1.120.000,00" → 1120000.0, "125,300.00" → 125300.0

REGLA 5 — Descuento decimal:
Siempre devuelve el descuento como fracción decimal.
"5.00" → 0.05  |  "0.00" o vacío → 0.0

REGLA 6 — Completitud total:
Extrae CADA producto como objeto separado.
Si hay 63 productos, el array debe tener 63 objetos. NO resumir.

REGLA 7 — Ignorar páginas de cupones de pago:
Las páginas con "TOTAL EFECTIVO", "BANCO", "CUPÓN DE PAGO" no contienen productos.

Responde ÚNICAMENTE con JSON válido sin markdown ni texto adicional:

{
  "numero_factura": "CPFE-XXXXXX",
  "fecha": "YYYY-MM-DD HH:MM:SS",
  "total_factura": 6541355.00,
  "pedidos": [
    {
      "numero_pedido": "PV03602772",
      "productos": [
        {
          "referencia": "4STE81110000",
          "producto": "PEDAL CAMBIOS T110E T110ED",
          "cantidad": 1.0,
          "precio_unit": 125300.0,
          "descuento": 0.05,
          "valor_total": 119035.0
        }
      ]
    }
  ]
}

TEXTO OCR:
{full_text}"""


def extract_with_claude(full_text: str) -> dict:
    print(f"[3/4] Enviando a Bedrock {MODEL} ({len(full_text)} chars)...")

    resp = bedrock.converse(
        modelId=MODEL,
        messages=[{'role': 'user', 'content': [{'text': _PROMPT.replace('{full_text}', full_text)}]}],
        inferenceConfig={'maxTokens': 16000},
    )
    raw = resp['output']['message']['content'][0]['text'].strip()
    raw = re.sub(r'^```\w*\n?', '', raw)
    raw = re.sub(r'\n?```$', '', raw).strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"    WARNING: JSON inválido ({e}) — intentando reparar...")
        return _repair_json(raw)


def _repair_json(text: str) -> dict:
    last = text.rfind('}')
    if last > 0:
        text = text[:last + 1]
    text += ']' * (text.count('[') - text.count(']'))
    text += '}' * (text.count('{') - text.count('}'))
    return json.loads(text)


# ── 3. VALIDACIÓN ────────────────────────────────────────────────────────────

def validate_and_fix(data: dict) -> dict:
    # Bug 1: número de factura mal extraído
    num = str(data.get('numero_factura', ''))
    if not re.match(r'^CPFE-\d+$', num):
        candidates = re.findall(r'CPFE-\d+', num)
        if candidates:
            fixed = candidates[-1]
            print(f"    FIX numero_factura: '{num}' → '{fixed}'")
            data['numero_factura'] = fixed

    total_factura   = float(data.get('total_factura') or 0)
    total_calculado = 0.0

    for pedido in data.get('pedidos', []):
        for prod in pedido.get('productos', []):

            # Bug 4: descuento > 1 → convertir a decimal
            d = float(prod.get('descuento') or 0)
            if d > 1:
                prod['descuento'] = round(d / 100, 4)
                d = prod['descuento']

            # Bug 2: valor_total = 0 → recalcular
            vt   = float(prod.get('valor_total') or 0)
            cant = float(prod.get('cantidad') or 0)
            pu   = float(prod.get('precio_unit') or 0)
            if vt == 0 and cant > 0 and pu > 0:
                vt = round(cant * pu * (1 - d), 2)
                prod['valor_total'] = vt
                print(f"    FIX valor_total '{prod.get('referencia')}': → {vt:,.2f}")

            # Bug 3: referencia y producto intercambiados
            ref  = str(prod.get('referencia', '') or '')
            desc = str(prod.get('producto', '') or '')
            ref_looks_like_code  = bool(REF_PATTERN.match(ref.replace(' ', ''))) and any(c.isdigit() for c in ref)
            desc_looks_like_code = bool(REF_PATTERN.match(desc.replace(' ', ''))) and any(c.isdigit() for c in desc)
            if not ref_looks_like_code and desc_looks_like_code:
                prod['referencia'], prod['producto'] = desc, ref
                print(f"    FIX swap ref/prod: '{ref}' ↔ '{desc}'")

            total_calculado += float(prod.get('valor_total') or 0)

    # Cross-check de totales
    if total_factura > 0:
        diff = abs(total_calculado - total_factura)
        pct  = diff / total_factura * 100
        status = "OK" if pct <= 1 else "WARNING"
        print(
            f"    {status} totales: calculado={total_calculado:,.0f} "
            f"vs factura={total_factura:,.0f} (diff={pct:.2f}%)"
        )

    return data


# ── 4. CSV ───────────────────────────────────────────────────────────────────

def build_csv_rows(data: dict, filename: str) -> list:
    rows          = []
    fecha_proceso = datetime.now().strftime('%d/%m/%Y %H:%M')
    is_first_file = True

    for pedido in data.get('pedidos', []):
        num_pedido      = pedido.get('numero_pedido') or ''
        is_first_pedido = True

        for prod in pedido.get('productos', []):
            cant = float(prod.get('cantidad') or 0)
            pu   = float(prod.get('precio_unit') or 0)
            dc   = float(prod.get('descuento') or 0)
            vt   = float(prod.get('valor_total') or 0)

            row = [
                data.get('numero_factura', '') if is_first_file else '',
                data.get('fecha', '')          if is_first_file else '',
                num_pedido                     if is_first_pedido else '',
                prod.get('referencia', ''),
                prod.get('producto', ''),
                f"{cant:.2f}",
                f"${pu:,.0f}",
                f"{dc:.2f}",
                f"${vt:,.0f}",
                filename      if is_first_file else '',
                fecha_proceso if is_first_file else '',
            ]
            rows.append(row)
            is_first_file   = False
            is_first_pedido = False

    return rows


def write_csv(rows: list, output_path: str | None) -> None:
    n_pedidos  = sum(1 for r in rows if r[2])
    n_products = len(rows)

    if output_path:
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(HEADERS)
            w.writerows(rows)
        print(f"\n[4/4] CSV → {output_path}  ({n_pedidos} pedidos, {n_products} productos)")
    else:
        buf = StringIO()
        w   = csv.writer(buf)
        w.writerow(HEADERS)
        w.writerows(rows)
        print(f"\n[4/4] CSV ({n_pedidos} pedidos, {n_products} productos):\n")
        print(buf.getvalue())


# ── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Skill local: factura Incolmotos Yamaha → CSV estructurado'
    )
    parser.add_argument('pdf',          help='Ruta al PDF (o nombre de archivo para el CSV)')
    parser.add_argument('--bucket',     default=None,  help='Bucket S3 para Textract')
    parser.add_argument('--from-ocr',   default=None,  help='Usar texto OCR ya extraído (saltar Textract)')
    parser.add_argument('--out',        default=None,  help='Archivo CSV de salida (default: stdout)')
    args = parser.parse_args()

    if args.from_ocr:
        if not os.path.exists(args.from_ocr):
            sys.exit(f"ERROR: archivo OCR no encontrado: {args.from_ocr}")
        with open(args.from_ocr, encoding='utf-8') as f:
            full_text = f.read()
        print(f"[OCR] Usando texto guardado: {len(full_text.splitlines())} líneas")
    else:
        if not args.bucket:
            sys.exit("ERROR: --bucket es requerido cuando no se usa --from-ocr")
        if not os.path.exists(args.pdf):
            sys.exit(f"ERROR: archivo no encontrado: {args.pdf}")
        full_text = pdf_to_text(args.pdf, args.bucket)
    data      = extract_with_claude(full_text)

    print("\n[3b/4] Validando y corrigiendo...")
    data = validate_and_fix(data)

    n_pedidos  = len(data.get('pedidos', []))
    n_products = sum(len(p['productos']) for p in data.get('pedidos', []))
    print(f"    Factura: {data.get('numero_factura')} | pedidos: {n_pedidos} | productos: {n_products}")

    rows = build_csv_rows(data, os.path.basename(args.pdf))
    write_csv(rows, args.out)


if __name__ == '__main__':
    main()
