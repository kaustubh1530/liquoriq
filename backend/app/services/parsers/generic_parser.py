"""
services/parsers/generic_parser.py — Smart generic CSV/Excel parser

This parser works on any CSV or Excel file by attempting to detect which
column maps to which field using a list of known synonyms.

Example: "product_name" could be called any of:
  "Item", "Description", "Product", "Name", "Item Name", "Item Description",
  "Product Name", "Product Title", "Menu Item" ...

Detection strategy:
  1. Normalize all column names to lowercase + stripped
  2. Check each column against synonym lists
  3. Pick the first match found for each target field
  4. Rows where product_name can't be found are skipped with a warning

This is the fallback parser — used when source = "other" or when no
source-specific parser exists yet.
"""

from datetime import date
from pathlib import Path

import pandas as pd

from app.services.parsers.base_parser import BaseParser

# ── Column synonym maps ───────────────────────────────────────────────────────
# Add more synonyms as you discover new export formats.

COLUMN_SYNONYMS = {
    "product_name": [
        "item", "description", "product", "name", "item name", "item description",
        "product name", "product title", "menu item", "sku name", "article",
        "product description", "item_name", "product_name", "dept description",
    ],
    "sku": [
        "sku", "item code", "item_code", "upc", "barcode", "product code",
        "product_code", "item id", "item_id", "code", "plu",
    ],
    "category": [
        "category", "department", "dept", "type", "group", "product category",
        "item category", "section", "class", "division",
    ],
    "quantity": [
        "quantity", "qty", "units", "count", "qty sold", "units sold",
        "quantity sold", "qty_sold", "quantity_sold", "sold", "pieces",
    ],
    "unit_price": [
        "unit price", "price", "rate", "cost", "unit_price", "avg price",
        "average price", "price each", "each price", "item price",
    ],
    "total_amount": [
        "total", "amount", "sales", "revenue", "total amount", "gross sales",
        "net sales", "total sales", "subtotal", "sale amount", "extended",
        "extended price", "line total", "total_amount", "net_sales",
    ],
    "sale_date": [
        "date", "order date", "sale date", "transaction date", "created at",
        "order_date", "sale_date", "transaction_date", "datetime", "day",
    ],
    "customer_name": [
        "customer", "customer name", "name", "client", "buyer",
        "customer_name", "full name",
    ],
    "customer_email": [
        "email", "customer email", "e-mail", "customer_email", "email address",
    ],
    "customer_phone": [
        "phone", "customer phone", "telephone", "mobile", "customer_phone",
        "phone number",
    ],
}


def _detect_columns(df_columns: list[str]) -> dict[str, str]:
    """
    Returns a mapping of target_field → actual_column_name.
    E.g. {"product_name": "Item Description", "total_amount": "Net Sales"}
    """
    normalized = {col.lower().strip(): col for col in df_columns}
    mapping = {}

    for target_field, synonyms in COLUMN_SYNONYMS.items():
        for synonym in synonyms:
            if synonym in normalized:
                mapping[target_field] = normalized[synonym]
                break

    return mapping


def _parse_date(value) -> date | None:
    """Try to parse a date value — pandas usually handles this well."""
    if pd.isna(value) or value is None:
        return None
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None


class GenericParser(BaseParser):
    """
    Smart generic parser. Works on any CSV or Excel file by detecting columns
    from a synonym dictionary.
    """

    def parse(self, file_path: str) -> list[dict]:
        path = Path(file_path)
        extension = path.suffix.lower()

        # ── Load file with pandas ─────────────────────────────────────────────
        try:
            if extension == ".csv":
                df = pd.read_csv(file_path, dtype=str, na_values=["", "N/A", "n/a"])
            elif extension in (".xlsx", ".xls"):
                df = pd.read_excel(file_path, dtype=str)
            else:
                raise ValueError(f"Unsupported file type: {extension}")
        except Exception as e:
            raise ValueError(f"Could not read file: {e}") from e

        if df.empty:
            raise ValueError("The uploaded file has no data rows.")

        # ── Detect column mapping ─────────────────────────────────────────────
        col_map = _detect_columns(list(df.columns))

        if "product_name" not in col_map:
            available = ", ".join(df.columns.tolist())
            raise ValueError(
                f"Could not find a product name column. "
                f"Available columns: {available}. "
                f"Expected one of: {COLUMN_SYNONYMS['product_name']}"
            )

        # ── Parse each row ────────────────────────────────────────────────────
        rows = []
        for _, row in df.iterrows():
            product_name = self._safe_str(row.get(col_map.get("product_name")))
            if not product_name:
                continue  # skip rows with no product name (totals rows, blanks)

            rows.append({
                "product_name": product_name,
                "sku": self._safe_str(row.get(col_map.get("sku"))),
                "category": self._safe_str(row.get(col_map.get("category"))),
                "quantity": self._safe_float(row.get(col_map.get("quantity"))),
                "unit_price": self._safe_float(row.get(col_map.get("unit_price"))),
                "total_amount": self._safe_float(row.get(col_map.get("total_amount"))),
                "sale_date": _parse_date(row.get(col_map.get("sale_date"))),
                "channel": self.channel,
                "customer_name": self._safe_str(row.get(col_map.get("customer_name"))),
                "customer_email": self._safe_str(row.get(col_map.get("customer_email"))),
                "customer_phone": self._safe_str(row.get(col_map.get("customer_phone"))),
                "raw_row": row.to_dict(),
            })

        return rows