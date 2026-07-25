"""
services/parsers/customer_parser.py — Customer report parser (Phase 19)

Provider-aware, tolerant parsing of POS customer exports (CSV/Excel). Handles
two common shapes and normalizes both to per-customer aggregate records:

  1. SUMMARY report — one row per customer with total spend, visit count, and
     last-visit date (typical AdvEntPOS "Customer Report").
  2. TRANSACTION list — one row per purchase (customer + date + amount); rows
     are aggregated by customer.

Duplicate customers (same email/phone/name across rows) are merged: spend summed
(transactions) or taken from the summary, counts summed, last date = max,
first date = min, opt-ins OR-merged.

Output: list of dicts:
  {dedup_key, name, email, phone, total_spent, purchase_count,
   first_purchase_date, last_purchase_date, sms_opt_in, email_opt_in,
   transactions: [{purchase_date, amount, product_name}]}
"""

import math
import re
from datetime import date
from pathlib import Path

import pandas as pd

COLUMN_MAP = {
    "name":        ["customer", "customer name", "name", "full name", "account", "account name", "member"],
    "email":       ["email", "e-mail", "customer email", "email address"],
    "phone":       ["phone", "phone number", "mobile", "cell", "customer phone", "telephone", "contact"],
    "total_spent": ["total spent", "total sales", "lifetime value", "ltv", "total", "net sales", "amount", "sales", "total amount"],
    "count":       ["visits", "visit count", "orders", "order count", "transactions", "purchase count", "invoices", "# visits", "num orders", "trips"],
    "last_date":   ["last visit", "last purchase", "last purchase date", "last sale", "last transaction", "last order", "last seen"],
    "first_date":  ["first visit", "first purchase", "member since", "first seen", "join date", "customer since"],
    "sms_opt":     ["sms opt in", "sms", "text opt in", "sms_opt_in", "opt in sms", "text ok"],
    "email_opt":   ["email opt in", "email_opt_in", "opt in email", "newsletter", "email ok", "marketing email"],
    "amount":      ["amount", "sale amount", "total", "price", "line total"],
    "date":        ["date", "purchase date", "sale date", "transaction date", "order date"],
    "product":     ["product", "item", "description", "product name"],
}

_TRUE = {"y", "yes", "true", "1", "t", "opt-in", "opted in", "subscribed"}


def _match(cols_lower: dict[str, str], candidates: list[str]) -> str | None:
    for cand in candidates:
        if cand in cols_lower:
            return cols_lower[cand]
    return None


def _s(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s if s and s.lower() not in ("nan", "none", "null") else None


def _f(v) -> float:
    if v is None:
        return 0.0
    try:
        cleaned = str(v).replace("$", "").replace(",", "").replace("%", "").strip()
        if not cleaned:
            return 0.0
        r = float(cleaned)
        return r if math.isfinite(r) else 0.0
    except (ValueError, TypeError):
        return 0.0


def _int(v) -> int:
    return int(round(_f(v)))


def _date(v) -> date | None:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    try:
        return pd.to_datetime(v).date()
    except Exception:
        return None


def _bool(v) -> bool:
    s = _s(v)
    return bool(s) and s.lower() in _TRUE


def dedup_key(name: str | None, email: str | None, phone: str | None) -> str | None:
    """Identity key: email → phone digits → name. None if no identity → row skipped."""
    if email:
        return email.strip().lower()
    if phone:
        digits = re.sub(r"\D", "", phone)
        if digits:
            return "p:" + digits
    if name:
        return "n:" + name.strip().lower()
    return None


def _read(file_path: str) -> pd.DataFrame:
    ext = Path(file_path).suffix.lower()
    if ext == ".csv":
        try:
            return pd.read_csv(file_path, dtype=str, encoding="utf-8-sig")
        except UnicodeDecodeError:
            return pd.read_csv(file_path, dtype=str, encoding="latin-1")
    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(file_path, dtype=str)
        # If header isn't usable at row 0, try row 1 (some exports have a title row)
        if not _has_identity(df):
            df = pd.read_excel(file_path, dtype=str, header=1)
        return df
    raise ValueError(f"Unsupported file type: {ext}")


def _has_identity(df: pd.DataFrame) -> bool:
    cols = {str(c).lower().strip() for c in df.columns}
    ident = COLUMN_MAP["name"] + COLUMN_MAP["email"] + COLUMN_MAP["phone"]
    return any(c in cols for c in ident)


def parse_customers(file_path: str) -> list[dict]:
    df = _read(file_path)
    if df.empty:
        raise ValueError("The customer file has no data rows.")

    cols_lower = {str(c).lower().strip(): c for c in df.columns}
    resolved = {k: _match(cols_lower, v) for k, v in COLUMN_MAP.items()}

    if not (resolved["name"] or resolved["email"] or resolved["phone"]):
        raise ValueError(
            "No customer identity column found (need a name, email, or phone). "
            f"Columns: {', '.join(str(c) for c in df.columns)}"
        )

    # Summary reports have a visit COUNT or a LAST-VISIT column; transaction
    # lists have a per-row date/amount instead. (Generic "amount"/"total" alone
    # is ambiguous, so we key off count/last_date.)
    is_summary = resolved["count"] is not None or resolved["last_date"] is not None

    merged: dict[str, dict] = {}
    for _, row in df.iterrows():
        name = _s(row.get(resolved["name"])) if resolved["name"] else None
        email = _s(row.get(resolved["email"])) if resolved["email"] else None
        phone = _s(row.get(resolved["phone"])) if resolved["phone"] else None
        key = dedup_key(name, email, phone)
        if not key:
            continue

        rec = merged.get(key)
        if rec is None:
            rec = {
                "dedup_key": key, "name": name, "email": email, "phone": phone,
                "total_spent": 0.0, "purchase_count": 0,
                "first_purchase_date": None, "last_purchase_date": None,
                "sms_opt_in": False, "email_opt_in": False, "transactions": [],
            }
            merged[key] = rec
        else:
            rec["name"] = rec["name"] or name
            rec["email"] = rec["email"] or email
            rec["phone"] = rec["phone"] or phone

        if resolved["sms_opt"]:
            rec["sms_opt_in"] = rec["sms_opt_in"] or _bool(row.get(resolved["sms_opt"]))
        if resolved["email_opt"]:
            rec["email_opt_in"] = rec["email_opt_in"] or _bool(row.get(resolved["email_opt"]))

        if is_summary:
            spent = _f(row.get(resolved["total_spent"])) if resolved["total_spent"] else 0.0
            cnt = _int(row.get(resolved["count"])) if resolved["count"] else 1
            rec["total_spent"] += spent
            rec["purchase_count"] += max(cnt, 0)
            last = _date(row.get(resolved["last_date"])) if resolved["last_date"] else None
            first = _date(row.get(resolved["first_date"])) if resolved["first_date"] else None
            rec["last_purchase_date"] = _max_date(rec["last_purchase_date"], last)
            rec["first_purchase_date"] = _min_date(rec["first_purchase_date"], first)
        else:
            amount = _f(row.get(resolved["amount"])) if resolved["amount"] else 0.0
            pdate = _date(row.get(resolved["date"])) if resolved["date"] else None
            product = _s(row.get(resolved["product"])) if resolved["product"] else None
            rec["total_spent"] += amount
            rec["purchase_count"] += 1
            rec["last_purchase_date"] = _max_date(rec["last_purchase_date"], pdate)
            rec["first_purchase_date"] = _min_date(rec["first_purchase_date"], pdate)
            rec["transactions"].append(
                {"purchase_date": pdate, "amount": round(amount, 2), "product_name": product}
            )

    for rec in merged.values():
        rec["total_spent"] = round(rec["total_spent"], 2)

    return list(merged.values())


def _max_date(a: date | None, b: date | None) -> date | None:
    return max([d for d in (a, b) if d], default=None)


def _min_date(a: date | None, b: date | None) -> date | None:
    return min([d for d in (a, b) if d], default=None)
