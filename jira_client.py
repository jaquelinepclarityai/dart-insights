"""Thin Jira REST client + normalisation into a tidy pandas DataFrame.

Auth uses an Atlassian email + API token (HTTP basic auth). On Streamlit Cloud
these come from st.secrets; locally from .streamlit/secrets.toml or env vars.
"""
from __future__ import annotations

import os
import re
from typing import Any

import pandas as pd
import requests

import config


def _credentials() -> tuple[str, str]:
    """Return (email, api_token) from Streamlit secrets or environment."""
    email = token = None
    try:
        import streamlit as st

        email = st.secrets.get("JIRA_EMAIL")
        token = st.secrets.get("JIRA_API_TOKEN")
    except Exception:
        pass
    email = email or os.environ.get("JIRA_EMAIL")
    token = token or os.environ.get("JIRA_API_TOKEN")
    if not email or not token:
        raise RuntimeError(
            "Missing Jira credentials. Set JIRA_EMAIL and JIRA_API_TOKEN in "
            ".streamlit/secrets.toml (or as environment variables)."
        )
    return email, token


def fetch_issues(jql: str = config.JQL_ALL, page_size: int = 100,
                 max_pages: int | None = None) -> list[dict[str, Any]]:
    """Fetch all issues matching JQL using the enhanced search endpoint.

    max_pages limits how many pages are pulled (used by the connection test).
    """
    email, token = _credentials()
    url = f"{config.JIRA_BASE_URL}/rest/api/3/search/jql"
    session = requests.Session()
    session.auth = (email, token)
    session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

    issues: list[dict[str, Any]] = []
    next_token: str | None = None
    pages = 0
    while True:
        payload: dict[str, Any] = {
            "jql": jql,
            "maxResults": page_size,
            "fields": config.API_FIELDS,
        }
        if next_token:
            payload["nextPageToken"] = next_token
        resp = session.post(url, json=payload, timeout=60)
        if resp.status_code >= 400:
            # Surface the API's own explanation (auth / bad filter / bad field).
            raise RuntimeError(
                f"Jira API {resp.status_code} {resp.reason}: {resp.text[:500]}"
            )
        data = resp.json()
        issues.extend(data.get("issues", []))
        next_token = data.get("nextPageToken")
        pages += 1
        if not next_token or data.get("isLast") or (max_pages and pages >= max_pages):
            break
    return issues


# --- normalisation ---------------------------------------------------------

def _opt_value(v: Any) -> Any:
    """Extract a readable value from a Jira field that may be an option dict,
    a list of option dicts, or a user/scalar."""
    if v is None:
        return None
    if isinstance(v, dict):
        return v.get("value") or v.get("name") or v.get("displayName")
    if isinstance(v, list):
        vals = [_opt_value(x) for x in v]
        vals = [x for x in vals if x]
        return ", ".join(vals) if vals else None
    return v


def _adf_text(node: Any) -> str:
    """Flatten an Atlassian Document Format (ADF) description to plain text."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return " ".join(_adf_text(n) for n in node)
    if isinstance(node, dict):
        txt = node.get("text", "")
        return (txt + " " + _adf_text(node.get("content"))).strip()
    return ""


def _client_from_summary(summary: str | None) -> str:
    """Tickets are titled like '[CLIENT] ...' — pull the leading bracket tag."""
    if not summary:
        return "Unknown"
    m = re.match(r"\s*\[([^\]]+)\]", summary)
    return m.group(1).strip() if m else "Unknown"


def issues_to_dataframe(issues: list[dict[str, Any]]) -> pd.DataFrame:
    f = config.FIELDS
    rows = []
    for it in issues:
        fld = it.get("fields", {})
        genai_raw = _opt_value(fld.get(f["genai"]))
        summary = fld.get("summary")
        desc = fld.get("description")
        desc_text = desc if isinstance(desc, str) else _adf_text(desc)
        rows.append(
            {
                "key": it.get("key"),
                "url": f"{config.JIRA_BASE_URL}/browse/{it.get('key')}",
                "summary": summary,
                "description": desc_text,
                "client": _client_from_summary(summary),
                "status": _opt_value(fld.get("status")),
                "status_category": (fld.get("status") or {}).get("statusCategory", {}).get("name"),
                "issuetype": _opt_value(fld.get("issuetype")),
                "priority": _opt_value(fld.get("priority")),
                "assignee": _opt_value(fld.get("assignee")),
                "reporter": _opt_value(fld.get("reporter")),
                "owner": _opt_value(fld.get(f["owner"])),
                "created": fld.get("created"),
                "resolved": fld.get("resolutiondate"),
                "time_spent_h": (
                    # Jira "Time tracking" field → timeSpentSeconds; fall back to
                    # the aggregate/system timespent fields if not present.
                    ((fld.get("timetracking") or {}).get("timeSpentSeconds")
                     or fld.get("aggregatetimespent") or fld.get("timespent") or 0) / 3600.0
                ),
                "due": fld.get(f["duedate"]),
                "resolution": _opt_value(fld.get("resolution")),
                "genai": genai_raw,
                "genai_used": (genai_raw is not None and config.GENAI_YES_VALUE in str(genai_raw)),
                "request_type": _opt_value(fld.get(f["request_type"])),
                "thematic_area": _opt_value(fld.get(f["thematic_area"])),
                "ps_category": _opt_value(fld.get(f["ps_category"])),
                "client_tier": _opt_value(fld.get(f["client_tier"])),
                "account_type": _opt_value(fld.get(f["account_type"])),
                "complexity": _opt_value(fld.get(f["complexity"])),
                "workload": _opt_value(fld.get(f["workload"])),
                "severity": _opt_value(fld.get(f["severity"])),
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Datetime parsing (UTC-aware -> tz-naive for easy plotting/arithmetic).
    for col in ["created", "resolved", "due"]:
        df[col] = pd.to_datetime(df[col], errors="coerce", utc=True).dt.tz_localize(None)

    df["is_resolved"] = df["resolved"].notna()
    df["resolution_days"] = (df["resolved"] - df["created"]).dt.total_seconds() / 86400
    # On time = resolved on/before due date (only meaningful when both exist).
    df["on_time"] = (df["resolved"].notna() & df["due"].notna()
                     & (df["resolved"].dt.normalize() <= df["due"].dt.normalize()))
    df["has_due"] = df["due"].notna()
    # Overdue open tickets (not resolved, due date in the past).
    today = pd.Timestamp.now().normalize()
    df["overdue_open"] = (~df["is_resolved"]) & df["has_due"] & (df["due"].dt.normalize() < today)
    return df
