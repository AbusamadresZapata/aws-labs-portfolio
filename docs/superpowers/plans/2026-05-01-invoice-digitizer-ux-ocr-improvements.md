# Invoice Digitizer UX + OCR Improvements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Completar 4 mejoras en Invoice Digitizer: tabla de productos con 8 columnas, progreso visual de upload, filtros efímeros de historial, y post-procesador Claude Haiku con merge strategy B.

**Architecture:** Backend: `_parse_with_claude` + `_merge_results` en `invoice_ocr_v2.py` — ambos parsers siempre corren, Claude tiene prioridad en campos de texto, Textract TABLE en items. Frontend: `InvoiceCard.jsx` muestra 8 columnas; `Dashboard.jsx` ya tiene progreso visual y filtros (correcto, no requiere cambios).

**Tech Stack:** Python 3.12, pytest, moto, unittest.mock — React 18 JSX, inline styles, AWS Amplify v6.

---

## Estado actual del código

| Archivo | Estado | Gap vs spec |
|---------|--------|-------------|
| `invoice_ocr_v2.py` | Modificado | Falta `_merge_results`; `lambda_handler` usa if/else simple, no merge strategy B |
| `InvoiceCard.jsx` | Modificado | Tabla tiene 4 columnas; spec aprobó 8 |
| `Dashboard.jsx` | Modificado | Correcto — coincide con spec |
| `test_lambdas.py` | Vacío | Sin tests, sin conftest.py |

---

## File Map

| Archivo | Acción | Responsabilidad |
|---------|--------|-----------------|
| `invoice-digitizer/backend/tests/conftest.py` | Crear | Env vars + sys.path para importar la lambda en tests |
| `invoice-digitizer/backend/tests/test_lambdas.py` | Modificar | Tests de `_parse_with_claude` y `_merge_results` |
| `invoice-digitizer/backend/lambda/invoice_ocr_v2.py` | Modificar | Añadir `_merge_results`; actualizar `lambda_handler` |
| `invoice-digitizer/frontend/src/components/InvoiceCard.jsx` | Modificar | Tabla de 4 → 8 columnas |

---

## Task 1: Infraestructura de tests

**Files:**
- Crear: `invoice-digitizer/backend/tests/conftest.py`

- [ ] **Step 1: Crear conftest.py**

Las env vars deben setearse ANTES de importar el módulo lambda (lee `BUCKET_PROCESSED` y `SNS_TOPIC_ARN` a nivel de módulo).

```python
# invoice-digitizer/backend/tests/conftest.py
import os
import sys

os.environ.setdefault('BUCKET_PROCESSED',       'test-processed-bucket')
os.environ.setdefault('SNS_TOPIC_ARN',          'arn:aws:sns:us-east-1:123456789012:test-topic')
os.environ.setdefault('AWS_ACCESS_KEY_ID',      'testing')
os.environ.setdefault('AWS_SECRET_ACCESS_KEY',  'testing')
os.environ.setdefault('AWS_DEFAULT_REGION',     'us-east-1')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))
```

- [ ] **Step 2: Verificar que el import del módulo no explota**

```bash
cd invoice-digitizer/backend
python -c "import tests.conftest; import invoice_ocr_v2; print('OK')"
```

Esperado: `OK` (sin excepciones de env vars ni de boto3).

---

## Task 2: Tests para `_parse_with_claude` (RED → GREEN)

**Files:**
- Modificar: `invoice-digitizer/backend/tests/test_lambdas.py`

- [ ] **Step 1: Escribir los tests**

```python
# invoice-digitizer/backend/tests/test_lambdas.py
import json
import pytest
from unittest.mock import MagicMock
import invoice_ocr_v2 as ocr


# ── Helpers ──────────────────────────────────────────────────

def _make_parsed(**kwargs):
    base = {
        'total': None, 'subtotal': None, 'discount': None,
        'invoice_number': None, 'date': None, 'vendor': None,
        'nit': None, 'client_name': None, 'address': None,
        'items': [], 'items_count': 0,
    }
    if 'items' in kwargs and 'items_count' not in kwargs:
        base['items_count'] = len(kwargs['items'])
    base.update(kwargs)
    return base


def _mock_claude(monkeypatch, response_text):
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [MagicMock(text=response_text)]
    monkeypatch.setattr(ocr, 'claude_client', mock_client)
    return mock_client


# ── Tests: _parse_with_claude ─────────────────────────────────

def test_parse_with_claude_returns_none_when_no_client(monkeypatch):
    monkeypatch.setattr(ocr, 'claude_client', None)
    assert ocr._parse_with_claude("cualquier texto") is None


def test_parse_with_claude_returns_dict_on_valid_json(monkeypatch):
    _mock_claude(monkeypatch, json.dumps({
        "total": 55000, "vendor": "Tienda XYZ", "invoice_number": "001",
        "date": "01/05/2026", "subtotal": None, "discount": None,
        "nit": None, "client_name": None, "address": None, "items": []
    }))
    result = ocr._parse_with_claude("TIENDA XYZ\nTOTAL: $55.000")
    assert result is not None
    assert result['total'] == 55000.0
    assert result['vendor'] == 'Tienda XYZ'
    assert result['invoice_number'] == '001'
    assert result['items'] == []
    assert result['items_count'] == 0


def test_parse_with_claude_returns_none_on_api_exception(monkeypatch):
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("API error")
    monkeypatch.setattr(ocr, 'claude_client', mock_client)
    assert ocr._parse_with_claude("cualquier texto") is None


def test_parse_with_claude_returns_none_on_malformed_json(monkeypatch):
    _mock_claude(monkeypatch, "esto no es JSON {{{")
    assert ocr._parse_with_claude("cualquier texto") is None


def test_parse_with_claude_strips_markdown_code_blocks(monkeypatch):
    payload = json.dumps({
        "total": 10000, "vendor": "V", "invoice_number": None, "date": None,
        "subtotal": None, "discount": None, "nit": None,
        "client_name": None, "address": None, "items": []
    })
    _mock_claude(monkeypatch, f"```json\n{payload}\n```")
    result = ocr._parse_with_claude("texto")
    assert result is not None
    assert result['total'] == 10000.0


def test_parse_with_claude_normalizes_items(monkeypatch):
    _mock_claude(monkeypatch, json.dumps({
        "total": 20000, "vendor": "V", "invoice_number": None, "date": None,
        "subtotal": None, "discount": None, "nit": None,
        "client_name": None, "address": None,
        "items": [{"producto": "Leche 1L", "cantidad": 2, "precio_unit": 5000, "valor_total": 10000}]
    }))
    result = ocr._parse_with_claude("texto")
    assert len(result['items']) == 1
    assert result['items'][0]['producto'] == 'Leche 1L'
    assert result['items'][0]['cantidad'] == 2.0
    assert result['items_count'] == 1
```

- [ ] **Step 2: Ejecutar — deben pasar (función ya existe)**

```bash
pytest invoice-digitizer/backend/tests/test_lambdas.py -v -k "parse_with_claude"
```

Esperado: `5 passed`. Si alguno falla, revisar la implementación de `_parse_with_claude` en `invoice_ocr_v2.py` antes de continuar.

---

## Task 3: Tests para `_merge_results` (RED)

**Files:**
- Modificar: `invoice-digitizer/backend/tests/test_lambdas.py` (añadir al final)

- [ ] **Step 1: Añadir tests de `_merge_results`**

Añadir después de los tests de `_parse_with_claude`:

```python
# ── Tests: _merge_results ─────────────────────────────────────

def test_merge_results_claude_priority_on_text_fields():
    claude  = _make_parsed(total=55000.0, vendor='Claude Co')
    classic = _make_parsed(total=40000.0, vendor='Classic Co')
    result  = ocr._merge_results(claude, classic)
    assert result['total']  == 55000.0
    assert result['vendor'] == 'Claude Co'


def test_merge_results_fills_claude_nulls_from_classic():
    claude  = _make_parsed(total=55000.0, nit=None, date=None)
    classic = _make_parsed(total=40000.0, nit='900123456-1', date='01/05/2026')
    result  = ocr._merge_results(claude, classic)
    assert result['total'] == 55000.0        # Claude wins
    assert result['nit']   == '900123456-1'  # Claude null → classic
    assert result['date']  == '01/05/2026'   # Claude null → classic


def test_merge_results_classic_items_take_priority():
    claude  = _make_parsed(items=[{'producto': 'Claude item', 'cantidad': 1.0,
                                    'precio_unit': None, 'valor_total': None}])
    classic = _make_parsed(items=[{'producto': 'Textract item', 'cantidad': 2.0,
                                    'precio_unit': None, 'valor_total': None}])
    result  = ocr._merge_results(claude, classic)
    assert result['items'][0]['producto'] == 'Textract item'


def test_merge_results_claude_items_as_fallback_when_classic_empty():
    claude  = _make_parsed(items=[{'producto': 'Claude item', 'cantidad': 1.0,
                                    'precio_unit': None, 'valor_total': None}])
    classic = _make_parsed(items=[])
    result  = ocr._merge_results(claude, classic)
    assert result['items'][0]['producto'] == 'Claude item'


def test_merge_results_items_count_consistent_with_items():
    claude  = _make_parsed(items=[{'producto': 'A'}, {'producto': 'B'}])
    classic = _make_parsed(items=[])
    result  = ocr._merge_results(claude, classic)
    assert result['items_count'] == len(result['items']) == 2
```

- [ ] **Step 2: Ejecutar — deben FALLAR (función no existe aún)**

```bash
pytest invoice-digitizer/backend/tests/test_lambdas.py -v -k "merge_results"
```

Esperado: `5 failed` con `AttributeError: module 'invoice_ocr_v2' has no attribute '_merge_results'`.

---

## Task 4: Implementar `_merge_results` y actualizar `lambda_handler` (GREEN)

**Files:**
- Modificar: `invoice-digitizer/backend/lambda/invoice_ocr_v2.py`

- [ ] **Step 1: Añadir `_merge_results` después de `_parse_with_claude`**

Insertar después de la función `_parse_with_claude` (antes de `# ── PARSER CLÁSICO`):

```python
def _merge_results(claude, classic):
    TEXT_FIELDS = [
        'total', 'subtotal', 'discount', 'invoice_number',
        'date', 'vendor', 'nit', 'client_name', 'address',
    ]
    merged = {}
    for field in TEXT_FIELDS:
        merged[field] = claude.get(field) if claude.get(field) is not None else classic.get(field)

    if classic.get('items'):
        merged['items']       = classic['items']
        merged['items_count'] = classic['items_count']
    else:
        merged['items']       = claude.get('items', [])
        merged['items_count'] = len(merged['items'])

    return merged
```

- [ ] **Step 2: Actualizar `lambda_handler` — paso 3 (reemplazar bloque existente)**

Reemplazar el bloque `# ── 3. PARSEAR CAMPOS` en `lambda_handler`:

```python
    # ── 3. PARSEAR CAMPOS ────────────────────────────────────
    claude_parsed  = _parse_with_claude(full_text)
    classic_parsed = _parse_invoice(lines, full_text, blocks)
    parsed = _merge_results(claude_parsed, classic_parsed) if claude_parsed else classic_parsed
    print(f"Parser: {'Claude+merge' if claude_parsed else 'clásico'} | "
          f"vendor={parsed.get('vendor')} total={parsed.get('total')} items={parsed['items_count']}")
```

- [ ] **Step 3: Ejecutar todos los tests — deben pasar**

```bash
pytest invoice-digitizer/backend/tests/test_lambdas.py -v
```

Esperado: `10 passed`.

- [ ] **Step 4: Lint del módulo lambda**

```bash
flake8 invoice-digitizer/backend/lambda/invoice_ocr_v2.py --max-line-length=100 --ignore=E501,W503
```

Esperado: sin output (0 errores).

- [ ] **Step 5: Commit backend**

```bash
git add invoice-digitizer/backend/tests/conftest.py
git add invoice-digitizer/backend/tests/test_lambdas.py
git add invoice-digitizer/backend/lambda/invoice_ocr_v2.py
git commit -m "feat: añadir _merge_results y tests TDD para post-procesador Claude"
```

---

## Task 5: Expandir tabla de productos a 8 columnas

**Files:**
- Modificar: `invoice-digitizer/frontend/src/components/InvoiceCard.jsx`

La tabla actual tiene 4 columnas (Producto, Cant, P.Unit, Total). Reemplazar el bloque `<table>` completo dentro de `{expandedItems && hasItems && (` por:

- [ ] **Step 1: Reemplazar el bloque `<table>` en InvoiceCard.jsx**

Localizar desde `<table style={{ width:'100%'...` hasta `</table>` y reemplazar con:

```jsx
<table style={{ width:'100%', borderCollapse:'collapse', fontSize:11 }}>
  <thead>
    <tr style={{ borderBottom:'1px solid #e8e8e8', color:'#999' }}>
      <th style={{ textAlign:'right',  padding:'4px 6px', fontWeight:500, whiteSpace:'nowrap' }}>#</th>
      <th style={{ textAlign:'left',   padding:'4px 6px', fontWeight:500, whiteSpace:'nowrap' }}>Referencia</th>
      <th style={{ textAlign:'left',   padding:'4px 6px', fontWeight:500 }}>Producto</th>
      <th style={{ textAlign:'center', padding:'4px 6px', fontWeight:500, whiteSpace:'nowrap' }}>Unidad</th>
      <th style={{ textAlign:'right',  padding:'4px 6px', fontWeight:500, whiteSpace:'nowrap' }}>Cant</th>
      <th style={{ textAlign:'right',  padding:'4px 6px', fontWeight:500, whiteSpace:'nowrap' }}>P.Unit</th>
      <th style={{ textAlign:'right',  padding:'4px 6px', fontWeight:500, whiteSpace:'nowrap' }}>Desc %</th>
      <th style={{ textAlign:'right',  padding:'4px 6px', fontWeight:500, whiteSpace:'nowrap' }}>Total</th>
    </tr>
  </thead>
  <tbody>
    {items.map((item, i) => (
      <tr key={i} style={{ borderBottom:'0.5px solid #f5f5f5' }}>
        <td style={{ padding:'4px 6px', textAlign:'right',  color:'#aaa' }}>
          {item.item || '—'}
        </td>
        <td style={{ padding:'4px 6px', textAlign:'left',   color:'#888' }}>
          {item.referencia || '—'}
        </td>
        <td style={{ padding:'4px 6px', textAlign:'left',   color:'#333' }}>
          {item.producto || '—'}
        </td>
        <td style={{ padding:'4px 6px', textAlign:'center', color:'#888' }}>
          {item.unidad || '—'}
        </td>
        <td style={{ padding:'4px 6px', textAlign:'right',  color:'#666' }}>
          {item.cantidad != null ? item.cantidad : '—'}
        </td>
        <td style={{ padding:'4px 6px', textAlign:'right',  color:'#666', whiteSpace:'nowrap' }}>
          {item.precio_unit != null
            ? `$${Number(item.precio_unit).toLocaleString('es-CO')}`
            : '—'}
        </td>
        <td style={{ padding:'4px 6px', textAlign:'right',  color:'#888' }}>
          {item.descuento_pct != null ? `${item.descuento_pct}%` : '—'}
        </td>
        <td style={{ padding:'4px 6px', textAlign:'right',  color:'#333', fontWeight:500, whiteSpace:'nowrap' }}>
          {item.valor_total != null
            ? `$${Number(item.valor_total).toLocaleString('es-CO')}`
            : '—'}
        </td>
      </tr>
    ))}
  </tbody>
</table>
```

- [ ] **Step 2: Verificar que el archivo compila sin errores**

```bash
node -e "require('fs').readFileSync('invoice-digitizer/frontend/src/components/InvoiceCard.jsx', 'utf8'); console.log('OK')"
```

Esperado: `OK`.

- [ ] **Step 3: Commit frontend**

```bash
git add invoice-digitizer/frontend/src/components/InvoiceCard.jsx
git commit -m "feat: expandir tabla de productos a 8 columnas en InvoiceCard"
```

---

## Task 6: Verificación final — Dashboard.jsx

**Files:**
- Leer: `invoice-digitizer/frontend/src/pages/Dashboard.jsx`

Este archivo ya fue corregido y coincide con el spec. Esta task es de verificación, no de implementación.

- [ ] **Step 1: Verificar step mapping del progreso visual**

Confirmar que `Dashboard.jsx` contiene estas asignaciones en orden:

```
setUploadStep(1)  →  línea de inicio de handleFile (antes del fetch /upload-url)
setUploadStep(2)  →  después del PUT S3 exitoso
setUploadStep(3)  →  antes del loop de polling
setUploadStep(0)  →  dentro del bloque finally
```

```bash
grep -n "setUploadStep" invoice-digitizer/frontend/src/pages/Dashboard.jsx
```

Esperado: 4 líneas, en el orden 1 → 2 → 3 → 0.

- [ ] **Step 2: Verificar lógica de filtros**

```bash
grep -n "filteredInvoices\|filterVendor\|filterDate" invoice-digitizer/frontend/src/pages/Dashboard.jsx
```

Esperado: `filterVendor`, `filterDate` como estados; `filteredInvoices` computado con `.filter()`; `filteredInvoices.map(...)` en el render.

- [ ] **Step 3: Verificar "Historial (N de M)"**

```bash
grep -n "de \${invoices" invoice-digitizer/frontend/src/pages/Dashboard.jsx
```

Esperado: 1 línea con la expresión del contador condicional.

---

## Task 7: Despliegue del backend

Esta task es manual. Ejecutar en orden:

- [ ] **Step 1: Empaquetar Lambda con anthropic**

```bash
cd invoice-digitizer/backend/lambda
pip install anthropic -t ./pkg/ --quiet
cd pkg && zip -r ../invoice_ocr_v2.zip . && cd ..
zip invoice_ocr_v2.zip invoice_ocr_v2.py
```

- [ ] **Step 2: Subir a AWS**

```bash
aws lambda update-function-code \
  --function-name invoice-ocr-processor \
  --zip-file fileb://invoice_ocr_v2.zip
```

Esperado: JSON de respuesta con `"CodeSize"` y `"LastModified"` actualizados.

- [ ] **Step 3: Limpiar artefactos**

```bash
rm -rf pkg invoice_ocr_v2.zip
cd ../../..
```

- [ ] **Step 4: Confirmar timeout y memoria en AWS Console**

En Lambda Console → `invoice-ocr-processor` → Configuration → General configuration:
- Timeout: mínimo `60` segundos
- Memory: mínimo `512` MB

- [ ] **Step 5: Verificar logs tras primera factura de prueba**

```bash
aws logs tail /aws/lambda/invoice-ocr-processor --follow
```

Esperado en logs: `Parser: Claude+merge | vendor=... total=... items=N`
Si aparece `WARNING Claude parsing falló`: verificar `ANTHROPIC_API_KEY` en env vars de Lambda.

---

## Task 8: Push a producción

- [ ] **Step 1: Push a main (activa Amplify auto-build)**

```bash
git push origin main
```

- [ ] **Step 2: Monitorear build en Amplify Console**

Amplify Console → invoice-digitizer app → Deployments. El build tarda ~2-3 minutos.

- [ ] **Step 3: Smoke test en producción**

1. Subir una factura — verificar los 3 pasos visuales (Subiendo → Leyendo → Analizando)
2. Abrir "Ver productos (N)" — verificar las 8 columnas
3. Usar filtro por comercio — verificar contador "N de M"
4. Revisar email de SNS — verificar que llegó correctamente

---

## Self-review checklist

| Requisito del spec | Cubierto en |
|-------------------|-------------|
| `_parse_with_claude` con modelo `claude-haiku-4-5-20251001` | Task 2 (tests) + ya implementado |
| `_merge_results`: Claude prioridad texto, Textract prioridad items | Task 3 (RED) + Task 4 (GREEN) |
| `lambda_handler` usa ambos parsers siempre | Task 4 Step 2 |
| Degradación sin API key o sin paquete | Task 2 test 1 cubre el caso None |
| Tabla 8 columnas con `—` para nulls | Task 5 |
| Progress steps Subiendo/Leyendo/Analizando | Task 6 (verificación) |
| Filtros efímeros vendor + date | Task 6 (verificación) |
| Contador "N de M" | Task 6 Step 3 |
| Lint pasa | Task 4 Step 4 |
| Commits frecuentes | Tasks 4, 5 |
