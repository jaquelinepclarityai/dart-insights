"""Central configuration for the DART Insights dashboard.

Everything that is environment- or Jira-specific lives here so the rest of the
app stays generic. Field IDs were resolved from the CCON (Product Specialists
Team) project field metadata.
"""

# --- Jira site -------------------------------------------------------------
JIRA_BASE_URL = "https://clarityai.atlassian.net"

# Saved Jira filter that defines the DART scope (open + closed tickets).
# https://clarityai.atlassian.net/issues?filter=15851
FILTER_ID = 15851

JQL_ALL = f"filter = {FILTER_ID}"

# --- Field mapping (resolved from CCON field metadata) ---------------------
FIELDS = {
    "summary": "summary",
    "status": "status",
    "issuetype": "issuetype",
    "priority": "priority",
    "assignee": "assignee",
    "reporter": "reporter",
    "created": "created",
    "resolutiondate": "resolutiondate",
    "duedate": "customfield_10448",        # "Due date" (team datepicker, not system duedate)
    "genai": "customfield_10702",          # "GenAI used" (Yes/No multicheckbox)
    "request_type": "customfield_10446",   # "Request types"
    "thematic_area": "customfield_10447",  # "Product Thematic Area" (multi)
    "ps_category": "customfield_10624",    # "PS Category" (multi)
    "client_tier": "customfield_10577",    # "Client Tier"
    "account_type": "customfield_10641",   # "Account type"
    "complexity": "customfield_10485",     # "Complexity"
    "workload": "customfield_10965",       # "DART Workload"
    "severity": "customfield_10475",       # "Severity"
    "owner": "customfield_10449",          # "Owner"
}

# Fields requested from the Jira API (system + custom).
API_FIELDS = [
    "summary", "status", "issuetype", "priority", "assignee", "reporter",
    "created", "resolutiondate", "resolution",
    FIELDS["duedate"], FIELDS["genai"], FIELDS["request_type"],
    FIELDS["thematic_area"], FIELDS["ps_category"], FIELDS["client_tier"],
    FIELDS["account_type"], FIELDS["complexity"], FIELDS["workload"],
    FIELDS["severity"], FIELDS["owner"],
]

# Value (as stored in Jira) that means "Gen AI was used".
GENAI_YES_VALUE = "Yes"

# --- Delivered-on-time KPI (Google Sheet snapshots) ------------------------
# The on-time KPI is sourced from the DART snapshot sheet, not from Jira due
# dates. It averages the "% All tickets On Time today" column (column C) across
# the daily snapshots, for the owners listed below.
# The sheet (or this specific tab) must be shared "Anyone with the link → Viewer".
ONTIME_SHEET_ID = "1e6CRPOHJuHDaLqiHfTqIlaf8zW_3pVWBgGadeFIN7Xw"
ONTIME_SHEET_GID = "903942725"
# The snapshot tab has no clean header row, so we read by column position:
# A=Date, B=Name, C="% All tickets On Time today".
ONTIME_DATE_IDX = 0
ONTIME_NAME_IDX = 1
ONTIME_PCT_IDX = 2
ONTIME_OWNERS = ["rei.jimenez", "Alberto Aguado Rodríguez"]

# Branding — Clarity AI palette (sourced from clarity.ai site CSS)
APP_TITLE = "DART Insights"
APP_ICON = "📊"

BRAND = {
    "primary": "#29826C",    # deep teal-green
    "teal": "#53C3B2",       # bright teal
    "mid": "#489087",        # mid green
    "purple": "#8578B9",     # accent purple
    "light": "#E4F8F3",      # light teal background
    "ink": "#1F2A2A",        # near-black text
}
# Ordered scheme for multi-series / categorical charts.
BRAND_SCALE = ["#29826C", "#53C3B2", "#8578B9", "#489087", "#A7E3D6", "#C0B6DE"]
