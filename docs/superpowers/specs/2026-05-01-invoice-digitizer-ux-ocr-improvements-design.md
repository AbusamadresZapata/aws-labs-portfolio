# Invoice Digitizer — UX + OCR Improvements Design

**Date:** 2026-05-01
**Status:** Approved
**Scope:** 3 files modified, 0 new files, 0 schema changes

---

## 1. Scope & Dependencies

Changes are isolated to 3 files. No API Gateway, DynamoDB schema, or get_invoices.py changes required.

```
invoice_ocr_v2.py  →  DynamoDB (same schema, items_json already exists)
                              ↓
              get_invoices.py (unchanged)
                              ↓
InvoiceCard.jsx  ←  invoice.items_json  (field already returned)
Dashboard.jsx    ←  invoice[]           (same array)
```

---

## 2. invoice_ocr_v2.py — Claude Post-Processor

### Merge Strategy
Both parsers always run. Claude has priority on text fields; null values fall back to the classic parser. For items, Textract TABLE blocks take priority; Claude items serve as fallback.

### New Functions

**`_parse_with_claude(full_text) → dict | None`**
- Returns `None` immediately if `claude_client is None` (no API key or package missing)
- Model: `claude-haiku-4-5-20251001`
- `max_tokens: 1024`
- Prompt in Spanish, instructs Colombian number format (`1.234.567,89` → `1234567.89`)
- Expected response: pure JSON without markdown
- Any exception → `return None` → fallback to classic parser

**`_merge_results(claude, classic) → dict`**
- Iterates text fields: uses Claude value if not `None`, else uses classic value
- Items: uses classic (Textract TABLE) if `len > 0`, else uses Claude items

### Lambda Handler Flow (step 3)
```python
claude_parsed  = _parse_with_claude(full_text)
classic_parsed = _parse_invoice(lines, full_text, blocks)  # always runs
parsed = _merge_results(claude_parsed, classic_parsed) if claude_parsed else classic_parsed
```

### Safe Module-Level Import
```python
try:
    import anthropic as _anthropic
    _anthropic_key = os.environ.get('ANTHROPIC_API_KEY')
    claude_client  = _anthropic.Anthropic(api_key=_anthropic_key) if _anthropic_key else None
except ImportError:
    claude_client = None
```

### Graceful Degradation
- No `ANTHROPIC_API_KEY` → `claude_client = None` → classic parser only (identical to today)
- `anthropic` package not bundled → `ImportError` caught → same result
- Claude API error → `except Exception` → `return None` → classic parser

### Deployment
```bash
cd invoice-digitizer/backend/lambda
pip install anthropic -t ./pkg/ --quiet
cd pkg && zip -r ../invoice_ocr_v2.zip . && cd ..
zip invoice_ocr_v2.zip invoice_ocr_v2.py
aws lambda update-function-code \
  --function-name invoice-ocr-processor \
  --zip-file fileb://invoice_ocr_v2.zip
rm -rf pkg invoice_ocr_v2.zip
```

Lambda env var required: `ANTHROPIC_API_KEY` (already configured).
Lambda timeout: minimum 60s. Memory: minimum 512MB.

---

## 3. InvoiceCard.jsx — Products Table

### New State
- `expandedItems: bool` — controls table visibility, independent of existing `expandedText`

### items_json Parsing
```javascript
let items = [];
try {
  const raw = invoice.items_json;
  items = raw ? (typeof raw === 'string' ? JSON.parse(raw) : raw) : [];
} catch { items = []; }
```

### Footer Bar Changes
- Add "Ver productos (N)" button alongside existing "Ver texto extraído"
- Only renders if `items.length > 0`
- Both buttons right-aligned via `marginLeft: 'auto'` flex container

### Table — 8 Columns
| # | Referencia | Producto | Unidad | Cant | P.Unit | Descuento | Total |

- `overflowX: 'auto'` wrapper for horizontal scroll on mobile
- Numeric columns right-aligned
- `null` values display as `—`
- Numbers formatted with `toLocaleString('es-CO')`

### Unchanged
Card header layout, `isError` logic, `confColor`, existing expanded text block.

---

## 4. Dashboard.jsx — Progress Steps + Filters

### New States
| State | Type | Default | Purpose |
|-------|------|---------|---------|
| `uploadStep` | number | 0 | Tracks upload pipeline stage |
| `filterVendor` | string | `''` | Ephemeral vendor filter |
| `filterDate` | string | `''` | Ephemeral date filter (ISO: YYYY-MM-DD) |

### Upload Step Mapping
```
setUploadStep(1)  →  on handleFile start (POST /upload-url + PUT S3)
setUploadStep(2)  →  after successful S3 PUT (starts 20s wait)
setUploadStep(3)  →  entering polling loop
setUploadStep(0)  →  in finally block (always, success or error)
```

### Progress Visual
3 circles connected by lines:
- Completed: green `#2e7d32` with `✓`
- Active: blue `#0066cc` with step number
- Pending: gray `#e0e0e0`
- Labels: `Subiendo · Leyendo · Analizando`
- `statusMsg` as descriptive text below the steps

### Filter Logic (client-side)
```javascript
const filteredInvoices = invoices.filter(inv => {
  if (filterVendor && !(inv.vendor || '').toLowerCase()
      .includes(filterVendor.toLowerCase())) return false;
  if (filterDate && inv.processed_at?.slice(0, 10) < filterDate) return false;
  return true;
});
```

### Filter UI
- Renders only when `invoices.length > 0`
- Text input: "Buscar por comercio..."
- Date input: `type="date"` (desde esta fecha)
- "Limpiar" button: appears only when a filter is active
- Counter: `Historial (N de M)` when filtering, `Historial (N)` without filter
- Empty state when `filteredInvoices.length === 0`: "Ningún recibo coincide con los filtros"

### Unchanged
`loadInvoices`, `getToken`, drag & drop, error handling, empty state for `invoices.length === 0`.

---

## 5. Error Handling Summary

| Scenario | Behavior |
|----------|----------|
| Claude API down | `except Exception` → `return None` → classic parser |
| `anthropic` not bundled | `ImportError` → `claude_client = None` → classic parser |
| `ANTHROPIC_API_KEY` missing | `claude_client = None` → classic parser |
| `items_json` malformed | `try/except` in JSX → `items = []` → no table shown |
| All filters active, no match | "Ningún recibo coincide con los filtros" message |
| Upload fails mid-flow | `finally` resets `uploadStep(0)` and `uploading(false)` |

---

## 6. Out of Scope

- Manual field correction by user (separate feature)
- Filter persistence between sessions (explicitly rejected: ephemeral)
- Lambda Layer for `anthropic` (explicitly rejected: Option A)
- New React components files (explicitly rejected: Option A)
- DynamoDB schema changes
- get_invoices.py changes
