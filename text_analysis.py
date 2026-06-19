"""Heuristic classification of ticket text (title + description).

Two purposes:
  1) A general request-type bucket for the overview chart.
  2) "Change Requests" detection — matching the one-off analysis methodology:
     client extra-work split into **Datafeed Changes** and **One-Off
     Extractions**. These are the candidates to charge existing Clients for.

Transparent keyword classifier (no external LLM, runs anywhere). Tune freely.
"""
from __future__ import annotations

import re

import pandas as pd

# --- General request-type buckets (overview chart) -------------------------
CATEGORY_PATTERNS: list[tuple[str, list[str]]] = [
    ("One-off / extraction", [
        r"\bone[ -]?off\b", r"\bad[ -]?hoc\b", r"\bextraction\b", r"\bextract\b",
        r"\bdata pull\b", r"\bexport\b", r"\bbespoke\b", r"\bcomparison\b", r"\bsample\b",
    ]),
    ("Datafeed / recurring delivery", [
        r"\bdatafeed\b", r"\bdata feed\b", r"\bmonthly delivery\b", r"\brecurring\b",
        r"\bperiodic\b", r"\bscheduled\b", r"\bSOP\b", r"\bmapping file\b",
    ]),
    ("Coverage / data gap", [
        r"\bcoverage\b", r"\bmissing\b", r"\black of\b", r"\badd (?:company|companies|issuer)\b",
        r"\bexpand (?:universe|coverage)\b", r"\bnew universe\b",
    ]),
    ("Data quality / bug", [
        r"\bincorrect\b", r"\bwrong\b", r"\berror\b", r"\bbug\b", r"\bmismatch\b",
        r"\bdiscrepan", r"\bfix\b", r"\boutdated\b", r"\bfreshness\b",
    ]),
    ("RFP / diligence", [r"\bRFP\b", r"\bRFI\b", r"\bdiligence\b", r"\bquestionnaire\b", r"\binfosec\b"]),
    ("Methodology / product question", [
        r"\bhow (?:do|does|can|to)\b", r"\bwhy\b", r"\bmethodolog", r"\bclarif",
        r"\bexplain\b", r"\bquestion\b", r"\bdefinition\b",
    ]),
]
_COMPILED = [(c, [re.compile(p, re.IGNORECASE) for p in pats]) for c, pats in CATEGORY_PATTERNS]


def classify(text: str) -> str:
    text = text or ""
    for cat, patterns in _COMPILED:
        if any(p.search(text) for p in patterns):
            return cat
    return "Other / uncategorised"


# --- One-off extractions (chargeable extra work) ---------------------------
# Match anything related to a one-off / ad-hoc extraction.
ONE_OFF = [re.compile(p, re.IGNORECASE) for p in [
    r"\bone[ -]?off\b", r"\bad[ -]?hoc\b", r"\bextraction\b", r"\bextract\b",
    r"\bbespoke\b", r"\bcustom (?:extract|data|request)\b", r"\bdata pull\b",
]]


def is_one_off(text: str) -> bool:
    """True if the text describes a one-off / ad-hoc extraction (not a routine delivery)."""
    t = text or ""
    # Exclude routine recurring work — anything mentioning "monthly".
    if re.search(r"\bmonthly\b", t, re.IGNORECASE):
        return False
    return any(p.search(t) for p in ONE_OFF)


def annotate(df: pd.DataFrame) -> pd.DataFrame:
    """Add 'req_category', 'one_off', and 'is_one_off' columns.

    is_one_off = one-off extraction AND an existing Client (not prospect/internal).
    """
    out = df.copy()
    blob = (out["summary"].fillna("") + " . "
            + out.get("description", pd.Series("", index=out.index)).fillna(""))
    out["req_category"] = blob.map(classify)
    out["one_off"] = blob.map(is_one_off)
    out["is_one_off"] = out["one_off"] & out["account_type"].eq("Client")
    return out
