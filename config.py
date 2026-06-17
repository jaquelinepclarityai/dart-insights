"""Central configuration for the DART Insights dashboard.

Everything that is environment- or Jira-specific lives here so the rest of the
app stays generic. Field IDs were resolved from the CCON (Product Specialists
Team) project field metadata.
"""

# --- Jira site -------------------------------------------------------------
JIRA_BASE_URL = "https://clarityai.atlassian.net"

# Saved Jira filters that define the DART scope. These are the filters you
# already use in Jira, so the dashboard always matches your boards.
FILTER_CLOSED = 12331   # https://clarityai.atlassian.net/issues/?filter=12331
FILTER_OPEN = 14650     # https://clarityai.atlassian.net/issues/?filter=14650

# A single JQL that returns BOTH open and closed DART tickets. We union the two
# saved filters so the dashboard has the full picture in one query.
JQL_ALL = f"filter = {FILTER_CLOSED} OR filter = {FILTER_OPEN}"

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
