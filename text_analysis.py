"""Heuristic request-type classification from ticket title + description.

Goal: surface billable potential — recurring/data-issue work is part of the
subscription, but **one-off extractions / custom ad-hoc work for existing
Clients** is the kind of thing that can be charged as extra. We tag each ticket
into a category and flag billable candidates.

This is a transparent keyword classifier (no external LLM, so it runs anywhere).
Patterns are ordered: the first matching category wins.
"""
from __future__ import annotations

import re

import pandas as pd

# Category -> list of regex keyword patterns (matched case-insensitively).
CATEGORY_PATTERNS: list[tuple[str, list[str]]] = [
    ("One-off / extraction", [
        r"\bone[ -]?off\b", r"\bad[ -]?hoc\b", r"\bextraction\b", r"\bextract\b",
        r"\bdata pull\b", r"\bpull the data\b", r"\bexport\b", r"\bcustom (?:request|extract|data)\b",
        r"\bbespoke\b", r"\bmanual extraction\b", r"\bdata dump\b", r"\bsnapshot of\b",
    ]),
    ("Datafeed / recurring delivery", [
        r"\bdatafeed\b", r"\bdata feed\b", r"\bmonthly delivery\b", r"\bquarterly\b",
        r"\brecurring\b", r"\bperiodic\b", r"\bscheduled\b", r"\bSOP\b",
    ]),
    ("Coverage / data gap", [
        r"\bcoverage\b", r"\bmissing\b", r"\black of\b", r"\badd (?:company|companies|issuer)\b",
        r"\bexpand (?:universe|coverage)\b", r"\bnot covered\b", r"\bnew universe\b",
    ]),
    ("Data quality / bug", [
        r"\bincorrect\b", r"\bwrong\b", r"\berror\b", r"\bbug\b", r"\bmismatch\b",
        r"\bdiscrepan", r"\bfix\b", r"\boutdated\b", r"\bfreshness\b", r"\bissue with\b",
    ]),
    ("RFP / diligence", [
        r"\bRFP\b", r"\bRFI\b", r"\bdiligence\b", r"\bquestionnaire\b", r"\binfosec\b",
    ]),
    ("Methodology / product question", [
        r"\bhow (?:do|does|can|to)\b", r"\bwhy\b", r"\bmethodolog", r"\bclarif",
        r"\bexplain\b", r"\bunderstand\b", r"\bquestion\b", r"\bdefinition\b",
    ]),
]

_COMPILED = [(cat, [re.compile(p, re.IGNORECASE) for p in pats]) for cat, pats in CATEGORY_PATTERNS]

# Categories that, for an existing Client, represent chargeable extra work.
BILLABLE_CATEGORIES = {"One-off / extraction"}


def classify(text: str) -> str:
    text = text or ""
    for cat, patterns in _COMPILED:
        if any(p.search(text) for p in patterns):
            return cat
    return "Other / uncategorised"


def annotate(df: pd.DataFrame) -> pd.DataFrame:
    """Add 'req_category' and 'billable_candidate' columns."""
    out = df.copy()
    blob = (out["summary"].fillna("") + " . " + out.get("description", pd.Series("", index=out.index)).fillna(""))
    out["req_category"] = blob.map(classify)
    # Billable = chargeable category AND an existing Client (not a prospect/internal).
    out["billable_candidate"] = (
        out["req_category"].isin(BILLABLE_CATEGORIES) & out["account_type"].eq("Client")
    )
    return out
