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
                f"Connected to Jira, but the query returned 0 issues. Check that "
                f"filter {config.FILTER_ID} is shared with your token's account.")
    except Exception as e:  # noqa: BLE001 - surface any auth/network issue as a banner
        detail = str(e) or repr(e)
        return sample_data.sample_dataframe(), "sample", detail


@st.cache_data(ttl=900, show_spinner=False)
def load_on_time() -> dict:
    """Daily on-time snapshot rows from the DART Google Sheet (Rei + Alberto)."""
    import sheet_client

    return sheet_client.fetch_on_time_df()


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


def explode_area(d: pd.DataFrame) -> pd.DataFrame:
    """Thematic area is a multi-select stored as 'A, B'. Split so each area
    counts independently."""
    s = d.assign(area=d["thematic_area"].fillna("").str.split(", ")).explode("area")
    return s[s["area"].str.len() > 0]


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
        # Default the date window to start at Jan 2026 (clamped to available data).
        dmin = df["created"].min().date()
        dmax = pd.Timestamp.now().date()
        default_start = max(dmin, pd.Timestamp("2026-01-01").date())
        date_range = st.date_input("Created between", value=(default_start, dmax),
                                   min_value=dmin, max_value=dmax)
    else:
        date_range = None

    def multi(label: str, col: str):
        opts = sorted([v for v in df[col].dropna().unique()])
        return st.multiselect(label, opts)

    f_type = multi("Request type", "request_type")
    f_tier = multi("Client tier", "client_tier")
    f_account = multi("Account type", "account_type")
    f_owner = multi("Owner (analyst)", "owner")
    f_requester = multi("Requester", "reporter")
    if st.button("🔄 Refresh from Jira"):
        st.cache_data.clear()
        st.rerun()

# Apply filters
mask = pd.Series(True, index=df.index)
if date_range and len(date_range) == 2:
    start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1]) + pd.Timedelta(days=1)
    mask &= df["created"].between(start, end)
for col, sel in [("request_type", f_type), ("client_tier", f_tier), ("account_type", f_account),
                 ("owner", f_owner), ("reporter", f_requester)]:
    if sel:
        mask &= df[col].isin(sel)
fdf = df[mask]

resolved = fdf[fdf["is_resolved"]]
# Closed-only subset: these two KPIs count strictly tickets in status "Closed".
closed = fdf[fdf["status"] == "Closed"]

# --- KPI row --------------------------------------------------------------
st.subheader("Key KPIs")
k1, k2, k3, k4, k5 = st.columns(5)

median_ttr = closed["resolution_days"].median()
k1.metric("Median time to resolve", f"{median_ttr:.1f} d" if pd.notna(median_ttr) else "–",
          help="Median days from creation to resolution, for tickets in status 'Closed'.")

genai_n = int(closed["genai_used"].sum())
k2.metric("Gen AI used", pct(genai_n, len(closed)),
          help=f"{genai_n} of {len(closed)} Closed tickets flagged 'GenAI used = Yes'.")

ontime = load_on_time()
ot_err = ontime.get("error")
ot_df = ontime.get("df")
if ot_df is not None:
    # Average '% On Time today' across snapshots in the selected period (Rei + Alberto).
    snaps = ot_df
    if date_range and len(date_range) == 2:
        snaps = snaps[snaps["date"].between(pd.Timestamp(date_range[0]),
                                            pd.Timestamp(date_range[1]) + pd.Timedelta(days=1))]
    if snaps.empty:
        k3.metric("Delivered on time", "–", help="No snapshots in the selected period.")
    else:
        per = " · ".join(f"{n.split()[0]}: {p:.0f}%"
                         for n, p in snaps.groupby("name")["pct"].mean().items())
        k3.metric("Delivered on time", f"{snaps['pct'].mean():.0f}%",
                  help=f"Avg of '% On Time today' across {len(snaps)} snapshots in the selected "
                       f"period for Rei + Alberto. {per}")
else:
    k3.metric("Delivered on time", "–", help="On-time sheet could not be read.")
    st.warning(f"⚠️ Delivered-on-time sheet not loaded: {ot_err}")

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
    st.markdown("**Ticket creation trend** (tickets created per month)")
    cm = fdf.dropna(subset=["created"]).set_index("created").resample("ME").size()
    cm = cm.rename("count"); cm.index.name = "month"
    cm = cm.reset_index()
    if not cm.empty:
        st.altair_chart(
            alt.Chart(cm).mark_area(
                opacity=0.5, line={"color": config.BRAND["primary"]}, color=config.BRAND["teal"]
            ).encode(
                x=alt.X("month:T", title=None),
                y=alt.Y("count:Q", title="Created"),
                tooltip=["month:T", "count:Q"],
            ).properties(height=280),
            use_container_width=True,
        )

with c2:
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

c3, c4 = st.columns(2)
with c3:
    st.markdown("**Gen AI adoption over time** (% of Closed tickets)")
    ga = closed.dropna(subset=["resolved"]).set_index("resolved")
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
with c4:
    st.markdown("**On-time delivery rate per month** (Closed tickets)")
    ot = closed[closed["has_due"]].dropna(subset=["resolved"]).set_index("resolved")
    if not ot.empty:
        otm = ot.resample("ME")["on_time"].mean().mul(100).rename("on_time_pct").reset_index()
        st.altair_chart(
            alt.Chart(otm).mark_line(point=True, color=config.BRAND["primary"]).encode(
                x=alt.X("resolved:T", title=None),
                y=alt.Y("on_time_pct:Q", title="% on time", scale=alt.Scale(domain=[0, 100])),
                tooltip=["resolved:T", alt.Tooltip("on_time_pct:Q", format=".0f")],
            ).properties(height=280),
            use_container_width=True,
        )

st.divider()

# --- Thematic area & Gen AI analysis --------------------------------------
st.subheader("Thematic area & Gen AI analysis")
closed_area = explode_area(closed)

a1, a2 = st.columns(2)
with a1:
    comp = closed.groupby("genai_used")["resolution_days"].median().rename("median_days").reset_index()
    comp["genai_used"] = comp["genai_used"].map({True: "Gen AI", False: "No Gen AI"})
    st.altair_chart(bar(comp, "median_days", "genai_used", "Resolve time by Gen AI used (median days)"),
                    use_container_width=True)
with a2:
    ga_area = (closed_area.groupby("area")["genai_used"].mean().mul(100)
               .rename("genai_pct").reset_index().sort_values("genai_pct", ascending=False))
    if not ga_area.empty:
        st.altair_chart(bar(ga_area, "genai_pct", "area", "Gen AI used by thematic area (%)"),
                        use_container_width=True)

a3, a4 = st.columns(2)
with a3:
    rt_area = (closed_area.dropna(subset=["resolution_days"]).groupby("area")["resolution_days"]
               .median().rename("median_days").reset_index().sort_values("median_days", ascending=False))
    if not rt_area.empty:
        st.altair_chart(bar(rt_area, "median_days", "area", "Resolve time by thematic area (median days)"),
                        use_container_width=True)
with a4:
    counts = (explode_area(fdf).groupby("area").size().rename("count")
              .reset_index().sort_values("count", ascending=False).head(12))
    if not counts.empty:
        st.altair_chart(bar(counts, "count", "area", "Ticket volume by thematic area"),
                        use_container_width=True)

st.divider()

# --- Time tracking (Time Spent) -------------------------------------------
st.subheader("Time tracking")
if "time_spent_h" in fdf.columns and fdf["time_spent_h"].fillna(0).sum() > 0:
    logged = closed[closed["time_spent_h"].fillna(0) > 0]
    m1, m2, m3 = st.columns(3)
    m1.metric("Total hours logged", f"{fdf['time_spent_h'].fillna(0).sum():,.0f} h",
              help="Sum of logged time across all tickets in scope.")
    m2.metric("Median per closed ticket",
              f"{logged['time_spent_h'].median():.1f} h" if len(logged) else "–",
              help="Median logged hours per Closed ticket that has any logged time.")
    m3.metric("Avg per closed ticket",
              f"{logged['time_spent_h'].mean():.1f} h" if len(logged) else "–")

    t1, t2 = st.columns(2)
    with t1:
        by_owner = (closed.groupby("owner")["time_spent_h"].sum()
                    .rename("hours").reset_index().sort_values("hours", ascending=False).head(12))
        by_owner = by_owner[by_owner["hours"] > 0]
        if not by_owner.empty:
            st.altair_chart(bar(by_owner, "hours", "owner", "Total hours by owner (analyst)"),
                            use_container_width=True)
    with t2:
        area_h = (explode_area(closed).groupby("area")["time_spent_h"].sum()
                  .rename("hours").reset_index().sort_values("hours", ascending=False))
        area_h = area_h[area_h["hours"] > 0]
        if not area_h.empty:
            st.altair_chart(bar(area_h, "hours", "area", "Total hours by thematic area"),
                            use_container_width=True)

    t3, t4 = st.columns(2)
    with t3:
        eff = logged.groupby("genai_used")["time_spent_h"].median().rename("median_h").reset_index()
        eff["genai_used"] = eff["genai_used"].map({True: "Gen AI", False: "No Gen AI"})
        if not eff.empty:
            st.altair_chart(bar(eff, "median_h", "genai_used",
                                "Median effort per ticket: Gen AI vs not (h)"),
                            use_container_width=True)
    with t4:
        sc = logged.dropna(subset=["resolution_days"])
        if not sc.empty:
            st.markdown("**Effort vs calendar time** (Closed tickets)")
            st.altair_chart(
                alt.Chart(sc).mark_circle(opacity=0.5, color=config.BRAND["primary"]).encode(
                    x=alt.X("time_spent_h:Q", title="Hours logged"),
                    y=alt.Y("resolution_days:Q", title="Days to resolve"),
                    tooltip=["key", "owner", "time_spent_h", "resolution_days"],
                ).properties(height=260),
                use_container_width=True,
            )
else:
    st.info("No Time tracking (Time Spent) data found on the tickets in scope.")

st.divider()

# --- Breakdowns -----------------------------------------------------------
st.subheader("Where the work goes")
b4, b5, b6 = st.columns(3)
for col_obj, field, title in [(b4, "client_tier", "By client tier"),
                              (b5, "account_type", "By account type"),
                              (b6, "owner", "Workload by owner (analyst)")]:
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
        ["key", "summary", "owner", "reporter", "client_tier", "due", "days_overdue", "status", "url"]
    ]
    st.dataframe(
        show, use_container_width=True, hide_index=True,
        column_config={
            "url": st.column_config.LinkColumn("Open", display_text="↗"),
            "due": st.column_config.DateColumn("Due"),
            "days_overdue": st.column_config.NumberColumn("Days overdue"),
            "owner": st.column_config.TextColumn("Owner"),
            "reporter": st.column_config.TextColumn("Requester"),
        },
    )

with st.expander("Browse all tickets in scope"):
    st.dataframe(
        fdf[["key", "summary", "status", "request_type", "owner", "reporter", "created",
             "resolved", "due", "resolution_days", "time_spent_h", "genai_used", "on_time", "url"]],
        use_container_width=True, hide_index=True,
        column_config={
            "url": st.column_config.LinkColumn("Open", display_text="↗"),
            "owner": st.column_config.TextColumn("Owner"),
            "reporter": st.column_config.TextColumn("Requester"),
        },
    )
    st.download_button("⬇️ Download CSV", fdf.to_csv(index=False).encode("utf-8"),
                       "dart_tickets.csv", "text/csv")
