"""Deterministic synthetic dataset, used when Jira credentials are absent so the
dashboard renders end-to-end for demos and local development."""
import numpy as np
import pandas as pd

import config


def sample_dataframe(n: int = 320) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    start = pd.Timestamp.today().normalize() - pd.Timedelta(days=240)
    created = start + pd.to_timedelta(rng.integers(0, 240, n), unit="D")

    request_types = ["RFP / RFI / Diligence", "Analysis", "Coverage / Extraction",
                     "Raw Data", "Bug", "More Information request", "Solutions Centre"]
    categories = ["Coverage analysis", "Data extraction", "Datafeed", "Missing data",
                  "Product question", "Metric mapping", "Custom request"]
    areas = ["Climate", "SFDR", "EU Taxonomy", "ESG Risk", "Exposures", "Impact", "Controversies"]
    tiers = ["Tier 1", "Tier 2", "Tier 3"]
    accounts = ["Client", "Prospect", "Internal Use"]
    complexity = ["Low", "Medium", "High"]
    workload = ["Low", "Medium", "Strategic"]
    assignees = ["A. Aguado", "R. Jimenez", "G. Rossi", "V. Estrada", "M. Gisbert", "C. Manchón"]

    rows = []
    for i in range(n):
        cplx = rng.choice(complexity, p=[0.45, 0.4, 0.15])
        genai = rng.random() < (0.18 + 0.0014 * (created[i] - start).days)  # adoption grows over time
        base = {"Low": 2, "Medium": 5, "High": 11}[cplx]
        dur = max(0.2, rng.gamma(2.2, base / 2.2) * (0.7 if genai else 1.0))
        resolved_flag = rng.random() < 0.78
        resolved = created[i] + pd.Timedelta(days=dur) if resolved_flag else pd.NaT
        due = created[i] + pd.Timedelta(days=base + rng.integers(1, 6))
        rows.append({
            "key": f"CCON-{1000 + i}",
            "url": f"{config.JIRA_BASE_URL}/browse/CCON-{1000 + i}",
            "summary": f"Sample ticket {i}",
            "status": "Closed" if resolved_flag else rng.choice(["In Progress", "To Do", "Blocked"]),
            "status_category": "Done" if resolved_flag else "In Progress",
            "issuetype": "Task",
            "priority": rng.choice(["Low", "Medium", "High"], p=[0.5, 0.35, 0.15]),
            "assignee": rng.choice(assignees),
            "reporter": rng.choice(assignees),
            "owner": rng.choice(assignees),
            "created": created[i],
            "resolved": resolved,
            "due": due,
            "resolution": "Done" if resolved_flag else None,
            "genai": "Yes" if genai else "No",
            "genai_used": bool(genai),
            "request_type": rng.choice(request_types),
            "thematic_area": rng.choice(areas),
            "ps_category": rng.choice(categories),
            "client_tier": rng.choice(tiers, p=[0.3, 0.4, 0.3]),
            "account_type": rng.choice(accounts, p=[0.7, 0.2, 0.1]),
            "complexity": cplx,
            "workload": rng.choice(workload, p=[0.5, 0.35, 0.15]),
            "severity": rng.choice(["SEV-2", "SEV-3", "SEV-4", None], p=[0.05, 0.15, 0.2, 0.6]),
        })

    df = pd.DataFrame(rows)
    df["is_resolved"] = df["resolved"].notna()
    df["resolution_days"] = (df["resolved"] - df["created"]).dt.total_seconds() / 86400
    df["on_time"] = (df["resolved"].notna() & df["due"].notna()
                     & (df["resolved"].dt.normalize() <= df["due"].dt.normalize()))
    df["has_due"] = df["due"].notna()
    today = pd.Timestamp.now().normalize()
    df["overdue_open"] = (~df["is_resolved"]) & df["has_due"] & (df["due"].dt.normalize() < today)
    return df
