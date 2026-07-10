"""
services/parsers/adventpos_parser.py — AdvEntPOS-specific parser

Two formats are handled:

1. "Sales By Item Summary Report" (.xls) — the REAL export from the pilot
   store (verified against an actual file in Phase 13). This is a print-style
   paginated report, not a clean table:
     - rows 0-5: store letterhead (name, address, phone)
     - report period buried in the letterhead: "From 01-Jul-2026 To 31-Jul-2026"
     - header row appears ~row 6 AND REPEATS on every printed page (41x)
     - page footers with a timestamp + "Page N of M" repeat too
     - long product names WRAP onto continuation rows that must be merged
       ("HAMILTON JAMAICAN POT STILL BLACK ," / next row: "750 ml")
     - columns: UPC | Item | Quantity Sold | Stock-On-Hand | Sales Amount
     - NO per-sale dates (summary over the period) → every row gets
       sale_date = period END date. Weekly exports are recommended so
       campaign ROI windows stay meaningful.
     - NO unit price column → derived as sales_amount / quantity

2. Legacy/simple exports (clean header row at 0 or 1) — the original
   COLUMN_MAP-based path, kept as fallback for other AdvEntPOS report types
   and CSV exports.

Detection is layout-based (find a header row containing both "UPC" and
"Quantity Sold" in the first ~15 raw rows), not extension-based.
"""

import logging
import re
from datetime import date
from pathlib import Path

import pandas as pd

from app.services.parsers.base_parser import BaseParser

logger = logging.getLogger(__name__)

# ── Legacy direct column mapping (fallback path) ──────────────────────────────

COLUMN_MAP = {
    "product_name":   ["description", "item description", "item name", "dept description", "product name", "product", "item"],
    "sku":            ["upc", "item code", "plu", "barcode"],
    "category":       ["dept", "department", "category"],
    "quantity":       ["qty sold", "qty", "quantity sold", "quantity"],
    "unit_price":     ["avg price", "average price", "unit price", "price"],
    "total_amount":   ["net sales", "total sales", "sales", "total amount", "amount", "sales amount"],
    "sale_date":      ["date", "sale date", "order date", "transaction date"],
    "customer_name":  ["customer", "customer name"],
    "customer_email": ["email", "customer email"],
    "customer_phone": ["phone", "customer phone"],
    "stock_on_hand":  ["stock-on-hand", "stock on hand", "on hand", "in stock"],
}

# Regex for the period line in the letterhead, e.g. "From  01-Jul-2026  To  31-Jul-2026"
_PERIOD_RE = re.compile(r"From\s+(\S+)\s+To\s+(\S+)", re.IGNORECASE)
# Page footer timestamps look like "7/9/26 10:55 AM"
_FOOTER_TS_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}\b")


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
    Tries the real-world "Sales By Item Summary" layout first, then falls
    back to generic column detection for simpler exports.
    """

    def parse(self, file_path: str) -> list[dict]:
        path = Path(file_path)
        extension = path.suffix.lower()

        if extension in (".xlsx", ".xls"):
            # Read RAW (no header assumption) to detect the report layout.
            # .xls needs the xlrd engine; .xlsx uses openpyxl — pandas picks
            # automatically as long as both libs are installed.
            try:
                raw = pd.read_excel(file_path, header=None, dtype=str)
            except Exception as e:
                raise ValueError(f"Could not read AdvEntPOS file: {e}") from e

            header_idx = self._find_summary_header(raw)
            if header_idx is not None:
                return self._parse_summary_report(raw, header_idx)

            # Not the summary layout → legacy path (header at row 0 or 1)
            df = pd.read_excel(file_path, dtype=str)
            if not self._has_usable_columns(df):
                df = pd.read_excel(file_path, dtype=str, header=1)
        elif extension == ".csv":
            try:
                df = pd.read_csv(file_path, dtype=str, encoding="utf-8-sig")
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, dtype=str, encoding="latin-1")
        else:
            raise ValueError(f"Unsupported file type: {extension}")

        return self._parse_legacy(df)

    # ══════════════════════════════════════════════════════════════════════════
    # Format 1: Sales By Item Summary Report (the real pilot-store export)
    # ══════════════════════════════════════════════════════════════════════════

    def _find_summary_header(self, raw: pd.DataFrame) -> int | None:
        """
        Return the row index of the summary-report header, or None.
        Signature: a row containing both 'UPC' and 'Quantity Sold' cells.
        """
        for idx in range(min(15, len(raw))):
            values = {str(v).strip().lower() for v in raw.iloc[idx] if pd.notna(v)}
            if "upc" in values and "quantity sold" in values:
                return idx
        return None

    def _parse_summary_report(self, raw: pd.DataFrame, header_idx: int) -> list[dict]:
        # ── Column positions from the header row ──────────────────────────────
        header = raw.iloc[header_idx]
        col_idx: dict[str, int] = {}
        for i, v in header.items():
            if pd.isna(v):
                continue
            name = str(v).strip().lower()
            if name == "upc":
                col_idx["upc"] = i
            elif name == "item":
                col_idx["item"] = i
            elif name == "quantity sold":
                col_idx["qty"] = i
            elif name == "stock-on-hand":
                col_idx["stock"] = i
            elif name == "sales amount":
                col_idx["sales"] = i

        missing = {"item", "qty", "sales"} - set(col_idx)
        if missing:
            raise ValueError(
                f"Summary report detected but columns missing: {missing}. "
                f"Header row was: {[str(v) for v in header if pd.notna(v)]}"
            )

        # ── Report period from the letterhead (rows above the header) ─────────
        # All rows get sale_date = period END (weekly exports recommended so
        # ROI windows stay granular).
        period_end: date | None = None
        for idx in range(header_idx):
            for v in raw.iloc[idx]:
                if isinstance(v, str) and (m := _PERIOD_RE.search(v)):
                    period_end = _parse_date(m.group(2))
                    break
            if period_end:
                break
        if period_end is None:
            logger.warning("Summary report: no 'From ... To ...' period found — sale_date will be NULL")

        # ── Walk rows: merge wrapped names, skip page headers/footers ─────────
        def cell(row, key):
            return row.iloc[col_idx[key]] if key in col_idx else None

        rows: list[dict] = []
        current: dict | None = None
        skipped_blocks = 0
        # Page-boundary reprints: the report repeats the LAST product of a page
        # as the FIRST product of the next page. Verified on a real file: 7 such
        # reprints inflated totals by exactly their sum ($183.05 / 9 units) vs
        # the report's printed grand total. Detect: identical raw values on the
        # first product row after a repeated page header → skip.
        crossed_page_header = False
        last_key: tuple | None = None
        reprints_skipped = 0

        def flush():
            nonlocal current
            if current is None:
                return
            qty = current["quantity"]
            total = current["total_amount"]
            current["unit_price"] = (
                round(total / qty, 2) if (qty and total is not None and qty > 0) else None
            )
            rows.append(current)
            current = None

        for idx in range(header_idx + 1, len(raw)):
            row = raw.iloc[idx]
            upc, item = cell(row, "upc"), cell(row, "item")
            qty, stock, sales = cell(row, "qty"), cell(row, "stock"), cell(row, "sales")
            first_cell = row.iloc[0]

            # Repeated page header ("UPC | Item | ...")
            if isinstance(upc, str) and upc.strip().lower() == "upc":
                skipped_blocks += 1
                crossed_page_header = True
                continue
            # Page footer (timestamp in first column / "Page N of M")
            if isinstance(first_cell, str) and _FOOTER_TS_RE.match(first_cell.strip()):
                continue

            if pd.notna(upc) and pd.notna(qty):
                # New product row
                key = (self._safe_str(upc), self._safe_str(qty),
                       self._safe_str(stock), self._safe_str(sales))
                if crossed_page_header and key == last_key:
                    # Reprint of the previous page's last product — skip it
                    reprints_skipped += 1
                    crossed_page_header = False
                    continue
                crossed_page_header = False
                last_key = key
                flush()
                current = {
                    "product_name":   self._safe_str(item) or "",
                    "sku":            self._safe_str(upc),
                    "category":       None,          # not present in this report type
                    "quantity":       self._safe_float(qty),
                    "unit_price":     None,          # derived on flush
                    "total_amount":   self._safe_float(sales),
                    "stock_on_hand":  self._safe_float(stock),
                    "sale_date":      period_end,
                    "channel":        self.channel,
                    "customer_name":  None,
                    "customer_email": None,
                    "customer_phone": None,
                    "raw_row": {
                        "upc": self._safe_str(upc),
                        "item": self._safe_str(item),
                        "quantity_sold": self._safe_str(qty),
                        "stock_on_hand": self._safe_str(stock),
                        "sales_amount": self._safe_str(sales),
                    },
                }
            elif current is not None and pd.notna(item) and pd.isna(upc) and pd.isna(qty):
                # Wrapped continuation of the previous product's name
                extra = self._safe_str(item)
                if extra:
                    current["product_name"] = f"{current['product_name']} {extra}".strip()
                    current["raw_row"]["item"] = current["product_name"]

        flush()

        # Drop rows that ended up with no usable name (defensive)
        rows = [r for r in rows if r["product_name"]]

        logger.warning(
            "AdvEntPOS summary parsed: %d products, period_end=%s, "
            "%d page headers skipped, %d page-boundary reprints deduplicated",
            len(rows), period_end, skipped_blocks, reprints_skipped,
        )
        return rows

    # ══════════════════════════════════════════════════════════════════════════
    # Format 2: legacy clean-table exports (original path)
    # ══════════════════════════════════════════════════════════════════════════

    def _parse_legacy(self, df: pd.DataFrame) -> list[dict]:
        if df.empty:
            raise ValueError("The AdvEntPOS export file has no data rows.")

        col_lower = {str(col).lower().strip(): col for col in df.columns}
        resolved = {field: _match_column(col_lower, candidates) for field, candidates in COLUMN_MAP.items()}

        if resolved.get("product_name") is None:
            available = ", ".join(str(c) for c in df.columns.tolist())
            raise ValueError(
                f"Could not find a product name column in this AdvEntPOS export. "
                f"Available columns: {available}. "
                f"Update COLUMN_MAP in adventpos_parser.py to match your export format."
            )

        rows = []
        for _, row in df.iterrows():
            product_name = self._safe_str(row.get(resolved["product_name"]))
            if not product_name:
                continue  # skip blank/total rows

            rows.append({
                "product_name":   product_name,
                "sku":            self._safe_str(row.get(resolved["sku"])) if resolved["sku"] else None,
                "category":       self._safe_str(row.get(resolved["category"])) if resolved["category"] else None,
                "quantity":       self._safe_float(row.get(resolved["quantity"])) if resolved["quantity"] else None,
                "unit_price":     self._safe_float(row.get(resolved["unit_price"])) if resolved["unit_price"] else None,
                "total_amount":   self._safe_float(row.get(resolved["total_amount"])) if resolved["total_amount"] else None,
                "stock_on_hand":  self._safe_float(row.get(resolved["stock_on_hand"])) if resolved["stock_on_hand"] else None,
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
        col_lower = {str(col).lower().strip() for col in df.columns}
        all_candidates = [c for candidates in COLUMN_MAP.values() for c in candidates]
        return any(c.lower() in col_lower for c in all_candidates)
