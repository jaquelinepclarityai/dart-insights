"""Read the DART on-time snapshot Google Sheet.

The 'Delivered on time' KPI is not derived from Jira due dates — it comes from
the team's snapshot sheet, averaging the '% All tickets On Time today' column
across daily snapshots for the configured owners (Rei + Alberto).

Access: the sheet/tab must be shared "Anyone with the link → Viewer" so the CSV
export endpoint is reachable without Google auth.
"""
from __future__ import annotations

import io

import pandas as pd
import requests

import config


def _csv_url() -> str:
    return (
        f"https://docs.google.com/spreadsheets/d/{config.ONTIME_SHEET_ID}"
        f"/gviz/tq?tqx=out:csv&gid={config.ONTIME_SHEET_GID}"
    )


def _to_pct(series: pd.Series) -> pd.Series:
    """Coerce values like '75%' or '0.75' or '75' to a 0-100 float."""
    s = series.astype(str).str.replace("%", "", regex=False).str.strip()
    vals = pd.to_numeric(s, errors="coerce")
    # If the column was stored as fractions (<=1), scale up to a percentage.
    if vals.dropna().le(1).all() and vals.dropna().gt(0).any():
        vals = vals * 100
    return vals


def fetch_on_time() -> dict:
    """Return on-time stats for the configured owners.

    {"pct": float|None, "per_owner": {name: pct}, "snapshots": int, "error": str|None}
    """
    try:
        resp = requests.get(_csv_url(), timeout=30)
        if resp.status_code >= 400:
            return {"pct": None, "per_owner": {}, "snapshots": 0,
                    "error": f"Sheet HTTP {resp.status_code} — is it shared 'Anyone with the link'?"}
        # No clean header row in this tab: read positionally.
        raw = pd.read_csv(io.StringIO(resp.text), header=None, dtype=str)
    except Exception as e:  # noqa: BLE001
        return {"pct": None, "per_owner": {}, "snapshots": 0, "error": str(e) or repr(e)}

    df = pd.DataFrame({
        "date": pd.to_datetime(raw.iloc[:, config.ONTIME_DATE_IDX], errors="coerce"),
        "name": raw.iloc[:, config.ONTIME_NAME_IDX],
        "pct": _to_pct(raw.iloc[:, config.ONTIME_PCT_IDX]),
    })
    df = df[df["name"].isin(config.ONTIME_OWNERS)].dropna(subset=["pct", "date"])
    if df.empty:
        return {"pct": None, "per_owner": {}, "snapshots": 0, "as_of": None,
                "error": "No snapshot rows found for the configured owners."}

    # The sheet is appended to daily — use each owner's most recent snapshot.
    latest = df.sort_values("date").groupby("name").tail(1)
    per_owner = latest.set_index("name")["pct"].round(1).to_dict()
    return {"pct": float(latest["pct"].mean()), "per_owner": per_owner,
            "snapshots": int(len(latest)),
            "as_of": latest["date"].max().date().isoformat(), "error": None}
