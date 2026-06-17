# 📊 DART Insights

A Streamlit dashboard for the **DART / Product Specialists team** that turns Jira
tickets (project `CCON`) into team insights and KPIs.

## KPIs tracked

- **Median time to resolve** — days from creation to resolution.
- **Gen AI used** — % of resolved tickets flagged `GenAI used = Yes` (`customfield_10702`), its trend over time, and its impact on resolution time.
- **Delivered on time** — % of resolved tickets closed on/before their **Due date** (`customfield_10448`), plus monthly on-time trend.
- **Open** and **Overdue & open** ticket counts, with a prioritised attention list.

## Insights included

- Created vs Resolved throughput per month (flow / backlog health)
- Gen AI adoption trend and Gen AI vs non-Gen AI resolution time
- Gen AI usage by request type
- Time to resolve by complexity (box plot)
- Breakdowns by request type, PS category, thematic area, client tier, account type, and assignee workload
- Overdue-open ticket table + full ticket browser with CSV export

All charts respect the sidebar filters (date range, request type, client tier, account type, complexity, assignee).

## Data source

Tickets are pulled live from Jira using your existing saved filters
(`filter = 12331` closed, `filter = 14650` open — see `config.py`). Field IDs are
already mapped to the CCON project. If no credentials are present, the app shows
**synthetic sample data** so it still renders.

## Run locally

```bash
cd dart-insights
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# add credentials
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edit .streamlit/secrets.toml with your Atlassian email + API token

streamlit run app.py
```

Create an API token at <https://id.atlassian.com/manage-profile/security/api-tokens>.

## Deploy on Streamlit Community Cloud

1. Push this folder to a GitHub repo (see below).
2. Go to <https://share.streamlit.io> → **New app** → pick the repo, branch, and `app.py`.
3. In **Advanced settings → Secrets**, paste:
   ```toml
   JIRA_EMAIL = "you@clarity.ai"
   JIRA_API_TOKEN = "..."
   ```
4. Deploy. Data is cached for 15 min; use **🔄 Refresh from Jira** to force a reload.

## Push to GitHub

```bash
cd dart-insights
git init
git add .
git commit -m "DART Insights Streamlit dashboard"
git branch -M main
git remote add origin https://github.com/<your-org>/dart-insights.git
git push -u origin main
```

## Project layout

| File | Purpose |
|------|---------|
| `app.py` | Streamlit UI, KPIs, charts |
| `jira_client.py` | Jira REST fetch + normalisation to a DataFrame |
| `config.py` | Jira site, filters, field-ID mapping |
| `sample_data.py` | Synthetic fallback data |
| `requirements.txt` | Dependencies |
| `.streamlit/` | Theme + secrets template |
