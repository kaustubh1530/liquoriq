"""
services/parsers/base_parser.py — Abstract base class for all parsers

Every source-specific parser (generic, AdvEntPOS, DoorDash, Uber Eats)
must inherit from BaseParser and implement the `parse()` method.

The contract:
  Input:  file_path (str) — path to the uploaded CSV or Excel file
  Output: list of dicts, each dict having these keys (all optional except product_name):
    {
        "product_name":   str,
        "sku":            str | None,
        "category":       str | None,
        "quantity":       float | None,
        "unit_price":     float | None,
        "total_amount":   float | None,
        "sale_date":      date | None,
        "channel":        str,           # "pos", "uber_eats", "doordash", etc.
        "customer_name":  str | None,
        "customer_email": str | None,
        "customer_phone": str | None,
        "raw_row":        dict,          # the original CSV row for debugging
    }

This pattern means the parse_service.py doesn't care which parser it's
using — it just calls parse() and saves the results.
"""

from abc import ABC, abstractmethod


class BaseParser(ABC):

    def __init__(self, channel: str = "pos"):
        """
        Args:
            channel: the sales channel this parser targets.
                     Stored on every NormalizedSale row for analytics.
        """
        self.channel = channel

    @abstractmethod
    def parse(self, file_path: str) -> list[dict]:
        """
        Read the file and return a list of normalized row dicts.
        Raise ValueError with a clear message if the file can't be parsed.
        Never raise silently — the parse_service catches errors and records them.
        """
        ...

    def _safe_float(self, value) -> float | None:
        """Convert a value to float safely, stripping $ , % characters."""
        if value is None:
            return None
        try:
            cleaned = str(value).replace("$", "").replace(",", "").replace("%", "").strip()
            return float(cleaned) if cleaned else None
        except (ValueError, TypeError):
            return None

    def _safe_str(self, value) -> str | None:
        """Convert a value to a clean string, return None if blank."""
        if value is None:
            return None
        s = str(value).strip()
        return s if s and s.lower() not in ("nan", "none", "null", "") else None