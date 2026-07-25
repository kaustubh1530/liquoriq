"""tests/test_customer_parser.py — customer parsing, dedup, empty, isolation key (Phase 19)"""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from app.services.parsers.customer_parser import dedup_key, parse_customers


def _write_csv(tmp_path: Path, rows: list[dict]) -> str:
    p = tmp_path / "customers.csv"
    pd.DataFrame(rows).to_csv(p, index=False)
    return str(p)


# ── Identity / isolation key ──────────────────────────────────────────────────

def test_dedup_key_prefers_email_then_phone_then_name():
    assert dedup_key("Jane", "JANE@x.com", "555-1234") == "jane@x.com"
    assert dedup_key("Jane", None, "(555) 123-4567") == "p:5551234567"
    assert dedup_key("Jane Doe", None, None) == "n:jane doe"
    assert dedup_key(None, None, None) is None


# ── Summary report ────────────────────────────────────────────────────────────

def test_parse_summary_report(tmp_path):
    path = _write_csv(tmp_path, [
        {"Customer": "Alice", "Email": "alice@x.com", "Total Spent": "1,200.50", "Visits": "14", "Last Visit": "2026-07-20"},
        {"Customer": "Bob", "Email": "bob@x.com", "Total Spent": "$80", "Visits": "1", "Last Visit": "2026-01-05"},
    ])
    out = {c["dedup_key"]: c for c in parse_customers(path)}
    assert out["alice@x.com"]["total_spent"] == 1200.5
    assert out["alice@x.com"]["purchase_count"] == 14
    assert out["alice@x.com"]["last_purchase_date"] == date(2026, 7, 20)
    assert out["bob@x.com"]["total_spent"] == 80.0


def test_duplicate_customers_are_merged(tmp_path):
    # Same email across two rows → one customer, spend + visits summed, latest date
    path = _write_csv(tmp_path, [
        {"Customer": "Alice", "Email": "alice@x.com", "Total Spent": "100", "Visits": "2", "Last Visit": "2026-06-01"},
        {"Customer": "Alice", "Email": "ALICE@x.com", "Total Spent": "50", "Visits": "1", "Last Visit": "2026-07-10"},
    ])
    out = parse_customers(path)
    assert len(out) == 1
    a = out[0]
    assert a["total_spent"] == 150.0
    assert a["purchase_count"] == 3
    assert a["last_purchase_date"] == date(2026, 7, 10)


def test_transaction_report_aggregates_by_customer(tmp_path):
    # No total/visits columns → transactional; rows aggregate per customer
    path = _write_csv(tmp_path, [
        {"Customer": "Carol", "Phone": "555-0001", "Amount": "20", "Date": "2026-07-01", "Product": "Wine"},
        {"Customer": "Carol", "Phone": "555-0001", "Amount": "35", "Date": "2026-07-15", "Product": "Whiskey"},
    ])
    out = parse_customers(path)
    assert len(out) == 1
    c = out[0]
    assert c["total_spent"] == 55.0
    assert c["purchase_count"] == 2
    assert c["last_purchase_date"] == date(2026, 7, 15)
    assert len(c["transactions"]) == 2


def test_opt_in_parsing(tmp_path):
    path = _write_csv(tmp_path, [
        {"Customer": "Dave", "Email": "dave@x.com", "Total": "10", "SMS Opt In": "Yes", "Email Opt In": "no"},
    ])
    d = parse_customers(path)[0]
    assert d["sms_opt_in"] is True
    assert d["email_opt_in"] is False


def test_rows_without_identity_are_skipped(tmp_path):
    path = _write_csv(tmp_path, [
        {"Customer": "", "Email": "", "Total": "10"},
        {"Customer": "Eve", "Email": "eve@x.com", "Total": "40"},
    ])
    out = parse_customers(path)
    assert len(out) == 1
    assert out[0]["dedup_key"] == "eve@x.com"


def test_empty_file_raises(tmp_path):
    p = tmp_path / "empty.csv"
    pd.DataFrame([], columns=["Customer", "Total"]).to_csv(p, index=False)
    with pytest.raises(ValueError):
        parse_customers(str(p))


def test_no_identity_column_raises(tmp_path):
    path = _write_csv(tmp_path, [{"Total": "10", "Visits": "1"}])
    with pytest.raises(ValueError):
        parse_customers(path)
