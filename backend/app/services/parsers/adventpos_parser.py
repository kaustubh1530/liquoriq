"""
services/parsers/adventpos_parser.py — AdvEntPOS-specific parser

AdvEntPOS is the POS system used at the first real LiquorIQ test store.
This parser maps AdvEntPOS's known export column names directly — no guessing.

AdvEntPOS report types we expect to handle:
  - Item Sales Report (most useful for LiquorIQ)
  - Inventory Report
  - Department Sales Report

Typical AdvEntPOS Item Sales export columns (may vary by version):
  "Dept"              → category
  "Description"       → product_name
  "UPC"               → sku
  "Qty Sold"          → quantity
  "Avg Price"         → unit_price
  "Net Sales"         → total_amount
  "Date"              → sale_date

NOTE: If you get the actual export from your uncle's store and the columns
are different, update COLUMN_MAP below — that's all you need to change.
The rest of the parser handles it automatically.
"""

from datetime import date
from pathlib import Path

import pandas as pd

from app.services.parsers.base_parser import BaseParser

# ── Direct column mapping for AdvEntPOS exports ───────────────────────────────
# Key   = LiquorIQ standard field name
# Value = exact column name as it appears in AdvEntPOS export (case-insensitive)
#
# TODO: Once you get a real export from your uncle's AdvEntPOS system,
# open the file, look at the header row, and update these values to match exactly.

COLUMN_MAP = {
    "product_name":   ["description", "item description", "item name", "dept description", "product name", "product"],
    "sku":            ["upc", "item code", "plu", "barcode"],
    "category":       ["dept", "department", "category"],
    "quantity":       ["qty sold", "qty", "quantity sold", "quantity"],
    "unit_price":     ["avg price", "average price", "unit price", "price"],
    "total_amount":   ["net sales", "total sales", "sales", "total amount", "amount"],
    "sale_date":      ["date", "sale date", "order date", "transaction date"],
    "customer_name":  ["customer", "customer name"],
    "customer_email": ["email", "customer email"],
    "customer_phone": ["phone", "customer phone"],
}


def _match_column(df_columns_lower: dict[str, str], candidates: list[str]) -> str | None:
    """Return the actual DataFrame column name for the first matching candidate."""
    for candidate in candidates:
        if candidate.lower().strip() in df_columns_lower:
            return df_columns_lower[candidate.lower().strip()]
    return None


def _parse_date(value) -> date | None:
    if pd.isna(value) or value is None:
        return None
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None


class AdvEntPOSParser(BaseParser):
    """
    Parser tailored specifically for AdvEntPOS sales report exports.
    Falls back to generic column detection if the known column names
    don't match — so it degrades gracefully on different AdvEntPOS versions.
    """

    def parse(self, file_path: str) -> list[dict]:
        path = Path(file_path)
        extension = path.suffix.lower()

        # ── Load file ─────────────────────────────────────────────────────────
        try:
            if extension == ".csv":
                # Try to handle AdvEntPOS quirks: possible BOM, different encodings
                try:
                    df = pd.read_csv(file_path, dtype=str, encoding="utf-8-sig")
                except UnicodeDecodeError:
                    df = pd.read_csv(file_path, dtype=str, encoding="latin-1")
            elif extension in (".xlsx", ".xls"):
                # AdvEntPOS sometimes has a summary header row before the data
                # Try row 0 first; if no recognizable columns, try row 1
                df = pd.read_excel(file_path, dtype=str)
                if not self._has_usable_columns(df):
                    df = pd.read_excel(file_path, dtype=str, header=1)
            else:
                raise ValueError(f"Unsupported file type: {extension}")
        except Exception as e:
            raise ValueError(f"Could not read AdvEntPOS file: {e}") from e

        if df.empty:
            raise ValueError("The AdvEntPOS export file has no data rows.")

        # ── Build a lowercase → actual column name lookup ─────────────────────
        col_lower = {col.lower().strip(): col for col in df.columns}

        # ── Map AdvEntPOS columns to our standard fields ──────────────────────
        resolved = {}
        for field, candidates in COLUMN_MAP.items():
            resolved[field] = _match_column(col_lower, candidates)

        # product_name is mandatory
        if resolved.get("product_name") is None:
            available = ", ".join(df.columns.tolist())
            raise ValueError(
                f"Could not find a product name column in this AdvEntPOS export. "
                f"Available columns: {available}. "
                f"Update COLUMN_MAP in adventpos_parser.py to match your export format."
            )

        # ── Parse each row ────────────────────────────────────────────────────
        rows = []
        for _, row in df.iterrows():
            product_name = self._safe_str(
                row.get(resolved["product_name"]) if resolved["product_name"] else None
            )
            if not product_name:
                continue  # skip blank/total rows

            rows.append({
                "product_name":   product_name,
                "sku":            self._safe_str(row.get(resolved["sku"])) if resolved["sku"] else None,
                "category":       self._safe_str(row.get(resolved["category"])) if resolved["category"] else None,
                "quantity":       self._safe_float(row.get(resolved["quantity"])) if resolved["quantity"] else None,
                "unit_price":     self._safe_float(row.get(resolved["unit_price"])) if resolved["unit_price"] else None,
                "total_amount":   self._safe_float(row.get(resolved["total_amount"])) if resolved["total_amount"] else None,
                "sale_date":      _parse_date(row.get(resolved["sale_date"])) if resolved["sale_date"] else None,
                "channel":        self.channel,
                "customer_name":  None,  # AdvEntPOS POS reports don't include customer PII
                "customer_email": None,
                "customer_phone": None,
                "raw_row":        row.to_dict(),
            })

        return rows

    def _has_usable_columns(self, df: pd.DataFrame) -> bool:
        """Check if the DataFrame has at least one column we recognize."""
        col_lower = {col.lower().strip() for col in df.columns}
        all_candidates = [c for candidates in COLUMN_MAP.values() for c in candidates]
        return any(c.lower() in col_lower for c in all_candidates)
