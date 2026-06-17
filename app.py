"""DART Insights — Streamlit dashboard for the Product Specialists / DART team.

Reads tickets live from Jira (CCON project, via your saved filters) and surfaces
team KPIs and insights. Falls back to synthetic sample data when no Jira
credentials are configured, so the app always renders.
"""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

import config

st.set_page_config(page_title=config.APP_TITLE, page_icon=config.APP_ICON, layout="wide")

# Clarity AI brand styling
st.markdown(
    f"""
    <style>
      .stApp h1, .stApp h2, .stApp h3 {{ color: {config.BRAND['primary']}; }}
      div[data-testid="stMetric"] {{
        background: {config.BRAND['light']};
        border: 1px solid {config.BRAND['teal']}33;
        border-radius: 12px; padding: 14px 16px;
      }}
      div[data-testid="stMetricValue"] {{ color: {config.BRAND['primary']}; }}
      .clarity-bar {{
        height: 6px; border-radius: 6px; margin-bottom: 8px;
        background: linear-gradient(90deg, {config.BRAND['primary']}, {config.BRAND['teal']}, {config.BRAND['purple']});
      }}
    </style>
    <div class="clarity-bar"></div>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=900, show_spinner="Loading tickets from Jira…")
def load_data() -> tuple[pd.DataFrame, str, str]:
    """Return (dataframe, source_label, detail). Tries Jira, falls back to sample."""
    import sample_data

    try:
        import jira_client

        issues = jira_client.fetch_issues()
        df = jira_client.issues_to_dataframe(issues)
        if not df.empty:
            return df, "live", f"{len(df)} tickets"
        return (sample_data.sample_dataframe(), "sample",
                "Connected to Jira, but the query returned 0 issues. Check that "
                "filters 12331 / 14650 are shared with your token's account.")
    except Exception as e:  # noqa: BLE001 - surface any auth/network issue as a banner
        detail = str(e) or repr(e)
        return sample_data.sample_dataframe(), "sample", detail


def pct(n: int, d: int) -> str:
    return f"{(100 * n / d):.0f}%" if d else "–"


def bar(data: pd.DataFrame, x: str, y: str, title: str, color: str | None = None):
    enc = {
        "x": alt.X(f"{x}:Q", title=None),
        "y": alt.Y(f"{y}:N", sort="-x", title=None),
        "tooltip": list(data.columns),
    }
    mark = {}
    if color:
        enc["color"] = alt.Color(f"{color}:N", legend=None,
                                 scale=alt.Scale(range=config.BRAND_SCALE))
    else:
        mark["color"] = config.BRAND["primary"]
    return (alt.Chart(data).mark_bar(**mark).encode(**enc)
            .properties(title=title, height=max(120, 28 * len(data))))


df, source, detail = load_data()

# --- Header ---------------------------------------------------------------
st.title(f"{config.APP_ICON} {config.APP_TITLE}")
st.caption("Ticket insights & KPIs for the DART (Product Specialists) team · data from Jira CCON")

if source == "sample":
    st.warning("⚠️ Showing **synthetic sample data** (not connected to live Jira).")
    st.error(f"**Reason:** {detail}")
else:
    st.success(f"✅ Live data · {len(df):,} tickets loaded from Jira.")

# --- Sidebar filters ------------------------------------------------------
with st.sidebar:
    st.header("Filters")
    if df["created"].notna().any():
        dmin = df["created"].min().date()
        dmax = pd.Timestamp.now().date()
        date_range = st.date_input("Created between", value=(dmin, dmax), min_value=dmin, max_value=dmax)
    else:
        date_range = None

    def multi(label: str, col: str):
        opts = sorted([v for v in df[col].dropna().unique()])
        return st.multiselect(label, opts)

    f_type = multi("Request type", "request_type")
    f_tier = multi("Client tier", "client_tier")
    f_account = multi("Account type", "account_type")
    f_complexity = multi("Complexity", "complexity")
    f_assignee = multi("Assignee", "assignee")
    if st.button("🔄 Refresh from Jira"):
        st.cache_data.clear()
        st.rerun()

    with st.expander("🔌 Test Jira connection"):
        if st.button("Run test"):
            try:
                import jira_client

                email, token = jira_client._credentials()
                st.write(f"Credentials found for: `{email}`")
                issues = jira_client.fetch_issues(page_size=5, max_pages=1)
                st.success(f"HTTP 200 · query returned {len(issues)} issue(s) on first page.")
            except Exception as e:  # noqa: BLE001
                st.error(f"{type(e).__name__}: {e}")

# Apply filters
mask = pd.Series(True, index=df.index)
if date_range and len(date_range) == 2:
    start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1]) + pd.Timedelta(days=1)
    mask &= df["created"].between(start, end)
for col, sel in [("request_type", f_type), ("client_tier", f_tier), ("account_type", f_account),
                 ("complexity", f_complexity), ("assignee", f_assignee)]:
    if sel:
        mask &= df[col].isin(sel)
fdf = df[mask]

resolved = fdf[fdf["is_resolved"]]

# --- KPI row --------------------------------------------------------------
st.subheader("Key KPIs")
k1, k2, k3, k4, k5 = st.columns(5)

median_ttr = resolved["resolution_days"].median()
k1.metric("Median time to resolve", f"{median_ttr:.1f} d" if pd.notna(median_ttr) else "–",
          help="Median days from ticket creation to resolution (resolved tickets).")

genai_n = int(resolved["genai_used"].sum())
k2.metric("Gen AI used", pct(genai_n, len(resolved)),
          help=f"{genai_n} of {len(resolved)} resolved tickets flagged 'GenAI used = Yes'.")

with_due = resolved[resolved["has_due"]]
on_time_n = int(with_due["on_time"].sum())
k3.metric("Delivered on time", pct(on_time_n, len(with_due)),
          help=f"{on_time_n} of {len(with_due)} resolved tickets (with a due date) met the due date.")

k4.metric("Open tickets", f"{int((~fdf['is_resolved']).sum()):,}",
          help="Currently unresolved tickets in scope.")

overdue_n = int(fdf["overdue_open"].sum())
k5.metric("Overdue & open", f"{overdue_n:,}", delta=None,
          delta_color="inverse", help="Open tickets whose due date has already passed.")

st.divider()

# --- Trends ---------------------------------------------------------------
st.subheader("Throughput & trends")
c1, c2 = st.columns(2)

with c1:
    created_m = fdf.set_index("created").resample("ME").size().rename("Created")
    resolved_m = resolved.set_index("resolved").resample("ME").size().rename("Resolved")
    flow = pd.concat([created_m, resolved_m], axis=1).fillna(0)
    flow.index.name = "month"
    flow = flow.reset_index().melt("month", var_name="type", value_name="count")
    st.markdown("**Created vs Resolved per month**")
    st.altair_chart(
        alt.Chart(flow).mark_line(point=True).encode(
            x=alt.X("month:T", title=None),
            y=alt.Y("count:Q", title="Tickets"),
            color=alt.Color("type:N", title=None, scale=alt.Scale(range=config.BRAND_SCALE)),
            tooltip=["month:T", "type:N", "count:Q"],
        ).properties(height=280),
        use_container_width=True,
    )

with c2:
    st.markdown("**Gen AI adoption over time** (% of resolved tickets)")
    ga = resolved.dropna(subset=["resolved"]).set_index("resolved")
    if not ga.empty:
        adoption = ga.resample("ME")["genai_used"].mean().mul(100).rename("genai_pct").reset_index()
        st.altair_chart(
            alt.Chart(adoption).mark_area(
                opacity=0.5, line={"color": config.BRAND["primary"]}, color=config.BRAND["teal"]
            ).encode(
                x=alt.X("resolved:T", title=None),
                y=alt.Y("genai_pct:Q", title="% Gen AI", scale=alt.Scale(domain=[0, 100])),
                tooltip=["resolved:T", alt.Tooltip("genai_pct:Q", format=".0f")],
            ).properties(height=280),
            use_container_width=True,
        )

# On-time trend + resolution by complexity
c3, c4 = st.columns(2)
with c3:
    st.markdown("**On-time delivery rate per month**")
    ot = resolved[resolved["has_due"]].dropna(subset=["resolved"]).set_index("resolved")
    if not ot.empty:
        otm = ot.resample("ME")["on_time"].mean().mul(100).rename("on_time_pct").reset_index()
        st.altair_chart(
            alt.Chart(otm).mark_line(point=True, color=config.BRAND["primary"]).encode(
                x=alt.X("resolved:T", title=None),
                y=alt.Y("on_time_pct:Q", title="% on time", scale=alt.Scale(domain=[0, 100])),
                tooltip=["resolved:T", alt.Tooltip("on_time_pct:Q", format=".0f")],
            ).properties(height=260),
            use_container_width=True,
        )
with c4:
    st.markdown("**Time to resolve by complexity** (days)")
    if resolved["complexity"].notna().any():
        st.altair_chart(
            alt.Chart(resolved.dropna(subset=["complexity", "resolution_days"])).mark_boxplot(extent="min-max").encode(
                x=alt.X("complexity:N", sort=["Low", "Medium", "High"], title=None),
                y=alt.Y("resolution_days:Q", title="Days"),
                color=alt.Color("complexity:N", legend=None, scale=alt.Scale(range=config.BRAND_SCALE)),
            ).properties(height=260),
            use_container_width=True,
        )

st.divider()

# --- Gen AI impact --------------------------------------------------------
st.subheader("Gen AI impact")
g1, g2 = st.columns([1, 2])
with g1:
    comp = resolved.groupby("genai_used")["resolution_days"].median().rename("median_days").reset_index()
    comp["genai_used"] = comp["genai_used"].map({True: "Gen AI", False: "No Gen AI"})
    st.altair_chart(bar(comp, "median_days", "genai_used", "Median resolve time: Gen AI vs not"),
                    use_container_width=True)
with g2:
    by_type = (resolved.groupby("request_type")["genai_used"].mean().mul(100)
               .rename("genai_pct").reset_index().sort_values("genai_pct", ascending=False))
    st.altair_chart(bar(by_type, "genai_pct", "request_type", "Gen AI usage by request type (%)"),
                    use_container_width=True)

st.divider()

# --- Breakdowns -----------------------------------------------------------
st.subheader("Where the work goes")
b1, b2, b3 = st.columns(3)
breakdowns = [
    (b1, "request_type", "By request type"),
    (b2, "ps_category", "By PS category"),
    (b3, "thematic_area", "By thematic area"),
]
for col_obj, field, title in breakdowns:
    with col_obj:
        counts = fdf[field].dropna().value_counts().head(12).rename_axis(field).reset_index(name="count")
        if not counts.empty:
            st.altair_chart(bar(counts, "count", field, title), use_container_width=True)

b4, b5, b6 = st.columns(3)
for col_obj, field, title in [(b4, "client_tier", "By client tier"),
                              (b5, "account_type", "By account type"),
                              (b6, "assignee", "Workload by assignee")]:
    with col_obj:
        counts = fdf[field].dropna().value_counts().head(12).rename_axis(field).reset_index(name="count")
        if not counts.empty:
            st.altair_chart(bar(counts, "count", field, title), use_container_width=True)

st.divider()

# --- Attention list -------------------------------------------------------
st.subheader("⚠️ Open & overdue tickets")
overdue = fdf[fdf["overdue_open"]].copy()
if overdue.empty:
    st.info("No overdue open tickets in the current selection. 🎉")
else:
    overdue["days_overdue"] = (pd.Timestamp.now().normalize() - overdue["due"].dt.normalize()).dt.days
    show = overdue.sort_values("days_overdue", ascending=False)[
        ["key", "summary", "assignee", "client_tier", "due", "days_overdue", "status", "url"]
    ]
    st.dataframe(
        show, use_container_width=True, hide_index=True,
        column_config={
            "url": st.column_config.LinkColumn("Open", display_text="↗"),
            "due": st.column_config.DateColumn("Due"),
            "days_overdue": st.column_config.NumberColumn("Days overdue"),
        },
    )

with st.expander("Browse all tickets in scope"):
    st.dataframe(
        fdf[["key", "summary", "status", "request_type", "assignee", "created",
             "resolved", "due", "resolution_days", "genai_used", "on_time", "url"]],
        use_container_width=True, hide_index=True,
        column_config={"url": st.column_config.LinkColumn("Open", display_text="↗")},
    )
    st.download_button("⬇️ Download CSV", fdf.to_csv(index=False).encode("utf-8"),
                       "dart_tickets.csv", "text/csv")
