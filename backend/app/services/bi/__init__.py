"""
services/bi — PHASE 22: BUSINESS INTELLIGENCE ENGINE

Turns parsed POS rows into ranked business decisions.

THE RULE THAT SHAPES EVERY MODULE HERE:
    Business logic is DETERMINISTIC. GPT only explains.

Every threshold, classification, score, dollar figure and ranking is computed
in pure Python and unit-tested. GPT is handed finished numbers and asked only
to write the sentence a human reads. If OpenAI is down or out of credits, the
whole engine still works — only the prose is missing.

Modules:
    assumptions.py      every threshold and margin, in one traceable place
    categorizer.py      5-tier category/brand/size resolution
    product_metrics.py  per-product metrics, 9 stock classes, 2 scores
    opportunities.py    7 detectors, ranked by value x confidence
    action_center.py    executive actions + store-level business health
    explain.py          the ONLY place GPT is touched (optional, fallback-safe)
"""
