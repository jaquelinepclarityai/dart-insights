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


# --- Change Requests (chargeable extra work) -------------------------------
ONE_OFF = [re.compile(p, re.IGNORECASE) for p in [
    r"\bone[ -]?off\b", r"\bad[ -]?hoc\b", r"\bextraction\b", r"\bextract\b",
    r"\bcomparison\b", r"\bsample\b", r"\bhistorical\b", r"\bbespoke\b",
]]
DATAFEED_CHANGE = [re.compile(p, re.IGNORECASE) for p in [
    r"\bdatafeed\b", r"\bdata feed\b", r"\bdataset\b", r"\bmapping file\b",
    r"\bnew mapping\b", r"\badd(?:ing)? column", r"\badd(?:ing)?\b.*\b(metric|field|file)\b",
    r"\breinclud", r"\bremov.*\b(metric|column|field)\b", r"\bplaceholder",
    r"\bcustom\b.*\b(metric|risk|sector|field)\b",
]]
CHANGE_TYPES = ["One-Off Extraction", "Datafeed Change"]


def classify_change_request(text: str) -> str | None:
    """Return 'One-Off Extraction', 'Datafeed Change', or None."""
    t = text or ""
    # Explicit one-off wording wins; otherwise datafeed-modification wording.
    if any(p.search(t) for p in ONE_OFF) and not re.search(r"\bmonthly delivery\b", t, re.I):
        # A datafeed *modification* (not a routine delivery) still counts as datafeed change
        if any(p.search(t) for p in DATAFEED_CHANGE) and not any(
            re.search(p, t, re.I) for p in [r"\bone[ -]?off\b", r"\bad[ -]?hoc\b", r"\bextraction\b"]
        ):
            return "Datafeed Change"
        return "One-Off Extraction"
    if any(p.search(t) for p in DATAFEED_CHANGE) and not re.search(r"\bmonthly delivery\b", t, re.I):
        return "Datafeed Change"
    return None


def annotate(df: pd.DataFrame) -> pd.DataFrame:
    """Add 'req_category', 'change_type', and 'is_change_request' columns."""
    out = df.copy()
    blob = (out["summary"].fillna("") + " . "
            + out.get("description", pd.Series("", index=out.index)).fillna(""))
    out["req_category"] = blob.map(classify)
    out["change_type"] = blob.map(classify_change_request)
    # Change request = a chargeable type AND an existing Client (not prospect/internal).
    out["is_change_request"] = out["change_type"].notna() & out["account_type"].eq("Client")
    return out
