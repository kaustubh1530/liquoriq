"""
Generates adventpos_summary_sample.xls — a SYNTHETIC replica of the real
AdvEntPOS "Sales By Item Summary Report" layout, safe to commit (no real
store data). Re-run if the layout logic ever needs new edge cases:

    pip install xlwt && python tests/fixtures/generate_fixture.py

Layout replicated (verified against a real export):
  letterhead rows → period line ("From ... To ...") → header row →
  data rows with WRAPPED product names → page footer with timestamp →
  REPEATED header on page 2 → more data → trailing footer.
"""

from pathlib import Path

import xlwt

wb = xlwt.Workbook()
ws = wb.add_sheet("Sheet1")


def row(r, cells: dict[int, object]):
    for col, val in cells.items():
        ws.write(r, col, val)


# ── Letterhead ────────────────────────────────────────────────────────────────
row(0, {1: "Demo Liquor Store"})
row(1, {1: "123 Test Street NW"})
row(2, {1: "Testville, VA 00000"})
row(3, {1: "5551234567", 12: "From  01-Jun-2026  To  07-Jun-2026"})

# ── Page 1 header (row 6, matching the real file's position) ─────────────────
HEADER = {1: "UPC", 2: "Item", 8: "Quantity Sold", 9: "Stock-On-Hand", 12: "Sales Amount"}
row(6, HEADER)

# ── Page 1 data ───────────────────────────────────────────────────────────────
row(8,  {1: "00000000001", 2: "TEST WHISKEY SINGLE BARREL RESERVE ,", 8: "2", 9: "5", 12: "61.72"})
row(9,  {2: "750 ml"})                                    # wrapped name continuation
row(10, {1: "00000000002", 2: "TEST VODKA , 1 Lt", 8: "1", 9: "3", 12: "19.99"})

# ── Page 1 footer ─────────────────────────────────────────────────────────────
row(12, {0: "6/8/26 10:00 AM", 5: "Sales By Item Summary Report", 12: "Page 1 of 2"})

# ── Page 2: repeated header + PAGE-BOUNDARY REPRINT + data ────────────────────
row(14, HEADER)
# The real report repeats the last product of the previous page as the first
# row of the next page — the parser must deduplicate this:
row(15, {1: "00000000002", 2: "TEST VODKA , 1 Lt", 8: "1", 9: "3", 12: "19.99"})
row(16, {1: "00000000003", 2: "TEST WINE CABERNET SAUVIGNON RESERVE ,", 8: "4", 9: "12", 12: "79.96"})
row(17, {2: "750 ml, GIFT BOX"})                          # two-part wrap
row(18, {1: "00000000004", 2: "TEST BEER , 12-PACK CANS", 8: "3", 9: "24", 12: "41.97"})

# ── Grand total row (must NOT become a product) ───────────────────────────────
row(20, {1: "Total", 8: "10", 12: "203.64"})

# ── Final footer ──────────────────────────────────────────────────────────────
row(21, {0: "6/8/26 10:00 AM", 5: "Sales By Item Summary Report", 12: "Page 2 of 2"})

out = Path(__file__).parent / "adventpos_summary_sample.xls"
wb.save(str(out))
print(f"wrote {out}")
