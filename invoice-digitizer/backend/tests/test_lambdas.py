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
