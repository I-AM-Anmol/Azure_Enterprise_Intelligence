import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import math
import time
from datetime import datetime
from calendar import monthrange
from azure.identity import AzureCliCredential, ClientSecretCredential
from streamlit_autorefresh import st_autorefresh

# ── Configuration ─────────────────────────────────────────────────────────────
TENANT_ID    = "e240d61e-61e3-4c9e-ab90-8644b2f4d2a9"
WORKSPACE_ID = "eca3c81e-a968-42a5-899f-d8fc1a45ebec"
DATASET_ID   = "56e6e1c3-8b70-4c53-b288-331041ce1f3f"
CLIENT_ID    = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
TENANT_NAME  = "MedInsight Production · Engineering · Milliman"
# Semantic model: MedInsight Azure Spend Analysis
# Workspace:      MI - Azure Cost Analysis and FinOps Dashboard

st_autorefresh(interval=300000)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
#MainMenu, footer, [data-testid="stToolbar"] { display:none !important; }
section[data-testid="stSidebar"] {
  background-color:#1a2744 !important; transform:translateX(0px) !important;
  display:block !important; visibility:visible !important; min-width:260px !important;
}
[data-testid="stSidebarCollapseButton"] { display:none !important; }
[data-testid="collapsedControl"] { display:none !important; }

.top-banner {
  background: linear-gradient(100deg, #1a3a6e 0%, #1e4d8c 60%, #2255a4 100%);
  border-radius: 12px; padding: 22px 32px 18px 32px; margin-bottom: 20px;
  box-shadow: 0 4px 18px rgba(26,58,110,0.20); position: relative; overflow: hidden;
}
.top-banner::before {
  content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 5px;
  background: linear-gradient(180deg, #60a5fa 0%, #2563eb 100%);
  border-radius: 12px 0 0 12px;
}
.top-banner .dash-title { font-size:1.55rem; font-weight:700; color:#fff; line-height:1.3; letter-spacing:-0.02em; }
.top-banner .dash-title span { color:#60a5fa; }
.top-banner .dash-meta { display:flex; gap:0; flex-wrap:wrap; margin-top:8px; align-items:center; }
.top-banner .dash-meta .m {
  font-size:0.73rem; color:rgba(255,255,255,0.55);
  padding-right:14px; margin-right:14px; border-right:1px solid rgba(255,255,255,0.15);
}
.top-banner .dash-meta .m:last-child { border-right:none; padding-right:0; margin-right:0; }

.kpi-card {
  background:#fff; border-radius:10px; padding:16px 18px;
  border:1px solid #e2e8f0; border-top:4px solid #2563eb;
  box-shadow:0 1px 4px rgba(0,0,0,0.06);
}
.kpi-card.red   { border-top-color:#dc2626; }
.kpi-card.green { border-top-color:#16a34a; }
.kpi-card.ora   { border-top-color:#ea580c; }
.kpi-card.pur   { border-top-color:#7c3aed; }
.kpi-lbl { font-size:0.68rem; font-weight:700; color:#64748b; text-transform:uppercase; letter-spacing:.06em; margin-bottom:5px; }
.kpi-val { font-size:1.9rem; font-weight:700; color:#0f172a; line-height:1.1; }
.kpi-val.red { color:#dc2626; } .kpi-val.grn { color:#16a34a; }
.kpi-val.ora { color:#ea580c; } .kpi-val.blu { color:#2563eb; }
.kpi-val.pur { color:#7c3aed; }
.kpi-sub { font-size:0.71rem; color:#64748b; margin-top:3px; }

.section-label {
  font-size:0.95rem; font-weight:700; color:#1e293b;
  margin:18px 0 10px 0; padding-bottom:6px; border-bottom:2px solid #e2e8f0;
}
.source-tag {
  display:inline-block; font-size:10px; font-weight:600; padding:1px 7px;
  border-radius:4px; background:#eff6ff; color:#2563eb;
  border:1px solid #bfdbfe; margin-left:8px; vertical-align:middle;
}
.source-tag.grn { background:#f0fdf4; color:#15803d; border-color:#86efac; }
.source-tag.ora { background:#fff7ed; color:#c2410c; border-color:#fed7aa; }

.fg-wrap { overflow-x:auto; border-radius:8px; border:1px solid #e2e8f0; }
table.fg { width:100%; border-collapse:collapse; font-size:12px; }
table.fg thead tr { background:#f8fafc; border-bottom:2px solid #e2e8f0; }
table.fg th { padding:9px 12px; text-align:left; font-size:11px; font-weight:600;
              text-transform:uppercase; letter-spacing:.05em; color:#64748b; white-space:nowrap; }
table.fg th.num { text-align:right; }
table.fg td { padding:7px 12px; border-bottom:1px solid #f1f5f9; vertical-align:middle; }
table.fg td.num { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
table.fg tr.row-actual   td { background:#f0fdf4; }
table.fg tr.row-current  td { background:#eff6ff; font-weight:600; }
table.fg tr.row-forecast td { background:#fafafa; color:#64748b; }
table.fg tr.row-over     td { background:#fef2f2; }
table.fg tr:hover td { background:#f8fafc; }

.mtype-actual   { background:#dcfce7; color:#15803d; border-radius:4px; padding:1px 7px; font-size:10px; font-weight:600; display:inline-block; }
.mtype-current  { background:#dbeafe; color:#1d4ed8; border-radius:4px; padding:1px 7px; font-size:10px; font-weight:600; display:inline-block; }
.mtype-forecast { background:#f1f5f9; color:#64748b; border-radius:4px; padding:1px 7px; font-size:10px; font-weight:600; display:inline-block; }
.acc-badge { display:inline-flex; align-items:center; padding:3px 10px; border-radius:20px;
             font-size:10px; font-weight:700; letter-spacing:.04em; white-space:nowrap; }
.acc-good  { background:#dcfce7; color:#16a34a; border:1px solid #86efac; }
.acc-ok    { background:#fef9c3; color:#ca8a04; border:1px solid #fde047; }
.acc-poor  { background:#fee2e2; color:#dc2626; border:1px solid #fca5a5; }
.pill-row  { display:flex; gap:10px; flex-wrap:wrap; margin:10px 0 14px 0; }

.method-box {
  background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px;
  padding:14px 16px; font-size:11px; color:#475569; line-height:1.7; margin-top:12px;
}
.method-box b { color:#0f172a; }

.dash-footer {
  font-size:0.7rem; color:#94a3b8; margin-top:24px; padding-top:10px;
  border-top:1px solid #e2e8f0; display:flex; justify-content:space-between; flex-wrap:wrap; gap:6px;
}

[data-testid="stPlotlyChart"] { border:1px solid #e2e8f0; border-radius:10px; overflow:hidden; }

.stDownloadButton > button {
  background:#2563eb !important; color:#fff !important;
  border:none !important; border-radius:6px !important;
  font-size:0.78rem !important; padding:7px 18px !important; font-weight:600 !important;
}
.stDownloadButton > button:hover { background:#1d4ed8 !important; }
</style>
""", unsafe_allow_html=True)


# ── Auth ──────────────────────────────────────────────────────────────────────
def get_token():
    try:
        az = st.secrets["azure"]
        cred = ClientSecretCredential(az["tenant_id"], az["client_id"], az["client_secret"])
        return cred.get_token("https://analysis.windows.net/powerbi/api/.default").token
    except (KeyError, FileNotFoundError):
        pass
    try:
        cred = AzureCliCredential(tenant_id=TENANT_ID)
        return cred.get_token("https://analysis.windows.net/powerbi/api/.default").token
    except Exception as e:
        st.error(
            f"Authentication failed. Configure **[azure]** secrets or run "
            f"`az login --tenant {TENANT_ID}` locally.\nError: {e}"
        )
        st.stop()


def strip_prefix(col):
    return col.split("[")[-1].rstrip("]") if "[" in col else col


def _pbi_query(token, dax, timeout=180):
    url = (
        f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}"
        f"/datasets/{DATASET_ID}/executeQueries"
    )
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"queries": [{"query": dax}], "serializerSettings": {"includeNulls": True}},
        timeout=timeout,
    )
    if resp.status_code == 401:
        st.error(f"Power BI API 401 — {resp.text}")
        st.stop()
    resp.raise_for_status()
    rows = resp.json()["results"][0]["tables"][0].get("rows", [])
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df.columns = [strip_prefix(c) for c in df.columns]
    return df


# ══════════════════════════════════════════════════════════════════════════════
#  DAX QUERIES
#  Semantic model: MedInsight Azure Spend Analysis
#  Table:   Azure_Expense_Details
#  Columns: [Date] (DateTime), [Cost] (Double)
#  Measures (on Azure_Expense_Details):
#    [Current month azure cost]  — portal-accurate MTD spend
#    [Exper. azure cost daily]   — average daily burn rate
#    [Max_date]                  — latest date in the dataset
#    [Rolling back 12 month azure cost] — 12-month rolling total
#  No BudgetData table — monthly budget entered via sidebar.
# ══════════════════════════════════════════════════════════════════════════════

# Completed months only (Complete_Month <> "Incomplete").
# Uses [Azure cost] = CALCULATE(SUMX(...Cost), exclude max date="Yes")
# which is exactly what the PBI report shows — matches portal figures.
_MONTHLY_HISTORY_DAX = """
EVALUATE
SUMMARIZECOLUMNS(
    Azure_Expense_Details[Complete_Month],
    FILTER(
        VALUES(Azure_Expense_Details[Complete_Month]),
        Azure_Expense_Details[Complete_Month] <> "Incomplete"
    ),
    "sortKey",   MIN(Azure_Expense_Details[Billing Period Start Date]),
    "totalCost", CALCULATE(
                     SUMX(Azure_Expense_Details, Azure_Expense_Details[Cost]),
                     Azure_Expense_Details[exclude max date] = "Yes"
                 )
)
ORDER BY [sortKey] ASC
"""

# Current-month MTD: bypass the SELECTEDVALUE slicer dependency in
# [Current month azure cost] by directly applying Complete_Month="Incomplete".
# Daily burn uses [Exper. azure cost daily] which already references [Azure cost].
_LIVE_METRICS_DAX = """
EVALUATE
ROW(
    "currentMTD", CALCULATE(
                      [Azure cost],
                      Azure_Expense_Details[Complete_Month] = "Incomplete"
                  ),
    "dailyBurn",  [Exper. azure cost daily],
    "rolling12m", CALCULATE(
                      [Azure cost],
                      DATESINPERIOD(Azure_Expense_Details[Date], [Max_date], -365, DAY)
                  ),
    "maxDate",    [Max_date]
)
"""


@st.cache_data(ttl=300)
def fetch_monthly_history(token):
    """
    Monthly cost aggregates from Azure_Expense_Details.
    Groups by Complete_Month label; MIN(Billing Period Start Date) gives the
    sort date from which Python extracts usageyear / usagemonth.
    """
    t0 = time.time()
    try:
        df = _pbi_query(token, _MONTHLY_HISTORY_DAX, timeout=180)
        if not df.empty:
            df.columns = [c.lower() for c in df.columns]
            # After strip_prefix: columns are "complete_month", "sortkey", "totalcost"
            df["totalcost"] = pd.to_numeric(df["totalcost"], errors="coerce").fillna(0)
            # sortkey is a datetime string from Power BI — parse it to extract year/month
            df["sortkey"] = pd.to_datetime(df["sortkey"], errors="coerce", utc=True)
            df["usageyear"]  = df["sortkey"].dt.year.fillna(0).astype(int)
            df["usagemonth"] = df["sortkey"].dt.month.fillna(0).astype(int)
            df = df[df["usageyear"] > 0].sort_values(["usageyear", "usagemonth"])
    except Exception as exc:
        st.warning(f"Could not query Azure_Expense_Details monthly history: {exc}")
        df = pd.DataFrame()
    return df, round(time.time() - t0, 1)


@st.cache_data(ttl=300)
def fetch_live_metrics(token):
    """
    Scalar live figures from semantic model measures:
      currentMTD  — [Current month azure cost] (portal-accurate MTD)
      dailyBurn   — [Exper. azure cost daily]  (avg $/day this month)
      rolling12m  — [Rolling back 12 month azure cost]
      maxDate     — [Max_date]
    """
    t0 = time.time()
    try:
        df = _pbi_query(token, _LIVE_METRICS_DAX, timeout=60)
        if not df.empty:
            df.columns = [c.lower() for c in df.columns]
            for c in ["currentmtd", "dailyburn", "rolling12m"]:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    except Exception as exc:
        st.warning(f"Could not query live metrics: {exc}")
        df = pd.DataFrame()
    return df, round(time.time() - t0, 1)


# ══════════════════════════════════════════════════════════════════════════════
#  FORECAST ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def build_forecast(hist_df: pd.DataFrame, live_row: dict, today: datetime, monthly_budget: float):
    """
    Returns (rows_list, meta_dict).

    Data sourcing per month type
    ────────────────────────────
    ACTUAL  (month < current):  Azure_Expense_Details[Date/Cost] grouped sum
    CURRENT (month == current): [Current month azure cost] measure  ← portal-accurate MTD
                                projected EOM via [Exper. azure cost daily] × days in month
    FORECAST (month > current): 70% rolling-3m avg + 30% burn×days ← computed

    Forecast accuracy
    ─────────────────
    For each completed month we back-calculate what the model would have predicted
    (rolling avg of the 3 preceding months) and compare to the actual.
    """
    curr_yr  = today.year
    curr_mo  = today.month

    # ── Live figures from semantic model measures ─────────────────────────────
    current_actual  = float(live_row.get("currentmtd",  0) or 0)   # [Current month azure cost]
    current_burn    = float(live_row.get("dailyburn",   0) or 0)   # [Exper. azure cost daily]
    days_in_curr_mo = monthrange(curr_yr, curr_mo)[1]
    days_passed     = today.day
    days_remaining  = days_in_curr_mo - days_passed

    # Project EOM from live daily burn × remaining days
    projected_eom = current_actual + current_burn * days_remaining
    if projected_eom <= 0 and current_actual > 0:
        projected_eom = current_actual  # at least what we've spent

    # ── Build lookup: actual monthly spend from Azure_Expense_Details ─────────
    actual_by_ym: dict = {}
    if not hist_df.empty:
        for _, row in hist_df.iterrows():
            yr = int(row["usageyear"])
            mo = int(row["usagemonth"])
            actual_by_ym[(yr, mo)] = float(row["totalcost"])

    # ── Rolling 3-month average from completed months ─────────────────────────
    completed = [
        actual_by_ym[(curr_yr, m)]
        for m in range(1, curr_mo)
        if (curr_yr, m) in actual_by_ym
    ]
    if len(completed) >= 3:
        rolling_avg = sum(completed[-3:]) / 3
    elif completed:
        rolling_avg = sum(completed) / len(completed)
    else:
        # No history yet — fall back to monthly budget
        rolling_avg = monthly_budget

    # ── Confidence band: ±15% base, widens 2% per month into the future ──────
    def band(base, months_out):
        spread = 0.15 + months_out * 0.02
        return round(base * (1 - spread), 2), round(base * (1 + spread), 2)

    month_names = ["Jan","Feb","Mar","Apr","May","Jun",
                   "Jul","Aug","Sep","Oct","Nov","Dec"]
    rows = []

    for m in range(1, 13):
        dim   = monthrange(curr_yr, m)[1]
        label = f"{month_names[m-1]} {curr_yr}"

        if m < curr_mo:
            # ── ACTUAL: from Azure_Expense_Details ──────────────────────────
            actual   = actual_by_ym.get((curr_yr, m))
            row_type = "actual"
            forecast = actual
            lo, hi   = (actual, actual) if actual is not None else (None, None)
            burn_day = (actual / dim) if actual else None
            accuracy = None  # filled below

        elif m == curr_mo:
            # ── CURRENT: portal-accurate figures from live measures ──────────
            actual   = current_actual    # [Current month azure cost] measure
            row_type = "current"
            forecast = projected_eom     # MTD + daily burn × days remaining
            lo, hi   = band(forecast, 0)
            burn_day = current_burn      # [Exper. azure cost daily] measure
            accuracy = None

        else:
            # ── FORECAST: computed ────────────────────────────────────────────
            months_out = m - curr_mo
            # Blend rolling history with live burn rate signal
            burn_extrap = (current_burn * dim) if current_burn > 0 else rolling_avg
            forecast    = round(0.70 * rolling_avg + 0.30 * burn_extrap, 2)
            actual      = None
            row_type    = "forecast"
            lo, hi      = band(forecast, months_out)
            burn_day    = current_burn if current_burn > 0 else None
            accuracy    = None

        rows.append({
            "month_num":     m,
            "month_name":    month_names[m-1],
            "year":          curr_yr,
            "label":         label,
            "type":          row_type,
            "actual":        actual,
            "budget":        monthly_budget,
            "forecast":      forecast,
            "lower":         lo,
            "upper":         hi,
            "burn_day":      burn_day,
            "days_in_month": dim,
            "accuracy":      None,
        })

    # ── Back-calculate forecast accuracy for completed months ─────────────────
    for i, row in enumerate(rows):
        if row["type"] != "actual" or row["actual"] is None:
            continue
        # What would rolling-3m have predicted for month i?
        preceding = [
            rows[j]["actual"]
            for j in range(max(0, i - 3), i)
            if rows[j]["actual"] is not None
        ]
        if not preceding:
            continue
        implied = sum(preceding) / len(preceding)
        if row["actual"] > 0:
            rows[i]["accuracy"] = round(100 - abs(row["actual"] - implied) / row["actual"] * 100, 1)

    meta = {
        "monthly_budget":   monthly_budget,
        "annual_budget":    monthly_budget * 12,
        "current_actual":   current_actual,
        "current_burn":     current_burn,
        "projected_eom":    projected_eom,
        "days_remaining":   days_remaining,
        "days_passed":      days_passed,
        "days_in_curr_mo":  days_in_curr_mo,
        "rolling_avg":      rolling_avg,
        "completed_count":  len(completed),
        "rolling12m":       float(live_row.get("rolling12m", 0) or 0),
    }
    return rows, meta


def year_end_forecast(rows):
    total = 0.0
    for r in rows:
        if r["type"] == "actual" and r["actual"] is not None:
            total += r["actual"]
        elif r["forecast"] is not None:
            total += r["forecast"]
    return total


def avg_accuracy(rows):
    vals = [r["accuracy"] for r in rows if r.get("accuracy") is not None]
    return round(sum(vals) / len(vals), 1) if vals else None


# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR – monthly budget input (no BudgetData table in this model)
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(
        "<div style='color:#fff;font-size:0.8rem;font-weight:700;margin-bottom:6px;'>💰 Monthly Budget</div>",
        unsafe_allow_html=True,
    )
    monthly_budget_input = st.number_input(
        "Monthly budget ($)",
        min_value=0,
        value=480_000,
        step=10_000,
        format="%d",
        label_visibility="collapsed",
        help="Set the monthly Azure spend budget. Used for variance and year-end forecast calculations.",
    )
    st.markdown(
        f"<div style='color:rgba(255,255,255,0.4);font-size:0.65rem;margin-top:4px;'>"
        f"Annual: ${monthly_budget_input * 12 / 1_000_000:.2f}M</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<hr style='border-color:rgba(255,255,255,0.1);margin:14px 0'>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  LOAD DATA
# ══════════════════════════════════════════════════════════════════════════════
token = get_token()
today = datetime.now()

with st.spinner("Loading Azure spend data from MedInsight Azure Spend Analysis…"):
    hist_df,  hist_elapsed  = fetch_monthly_history(token)
    live_df,  live_elapsed  = fetch_live_metrics(token)

if hist_df.empty and live_df.empty:
    st.warning(
        "No data returned from the Semantic Model.\n\n"
        "Workspace: **MI - Azure Cost Analysis and FinOps Dashboard**\n\n"
        "Dataset: **MedInsight Azure Spend Analysis**"
    )
    st.stop()

# Flatten the single-row live metrics
live_row = live_df.iloc[0].to_dict() if not live_df.empty else {}

rows, meta = build_forecast(hist_df, live_row, today, float(monthly_budget_input))
yef        = year_end_forecast(rows)
acc_avg    = avg_accuracy(rows)

generated  = today.strftime("%Y-%m-%d %H:%M")
user_email = st.session_state.get("user_email", "anmol.sharma@milliman.com")

completed_months = sum(1 for r in rows if r["type"] == "actual")
forecast_months  = sum(1 for r in rows if r["type"] == "forecast")
annual_budget    = meta["annual_budget"]
yef_over         = yef > annual_budget
over_under       = yef - annual_budget
budget_vs_yef    = round(yef / annual_budget * 100, 1) if annual_budget > 0 else 0


# ══════════════════════════════════════════════════════════════════════════════
#  BANNER
# ══════════════════════════════════════════════════════════════════════════════
max_date_str = str(live_row.get("maxdate", "—"))[:10] if live_row else "—"

st.markdown(f"""
<div class="top-banner">
  <div class="dash-title">Azure Spend <span>12-Month Forecast</span></div>
  <div class="dash-meta">
    <span class="m">{TENANT_NAME}</span>
    <span class="m">{user_email}</span>
    <span class="m">Generated: {generated}</span>
    <span class="m">Rolling avg (last 3 mo): ${meta['rolling_avg']/1000:.1f}K/mo</span>
    <span class="m">Current burn: ${meta['current_burn']/1000:.2f}K/day &nbsp;·&nbsp; {meta['days_remaining']}d left</span>
    <span class="m">Data as of: {max_date_str} &nbsp;·&nbsp; History: {hist_elapsed}s · Live: {live_elapsed}s</span>
  </div>
</div>
""", unsafe_allow_html=True)

# Data-source transparency strip
rolling12m_str = f"${meta['rolling12m']/1000:.0f}K" if meta.get('rolling12m') else "—"
st.markdown(f"""
<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px 16px;
            font-size:11px;color:#475569;display:flex;gap:20px;flex-wrap:wrap;margin-bottom:16px;">
  <span>📊 <b>Actuals</b> <span class="source-tag grn">[Azure cost] · exclude max date="Yes" · Complete_Month≠"Incomplete"</span>
        &nbsp;{len(hist_df)} completed months — same filter as PBI report</span>
  <span>💰 <b>Current MTD</b> <span class="source-tag">CALCULATE([Azure cost], Complete_Month="Incomplete")</span>
        &nbsp;${meta['current_actual']/1000:.1f}K</span>
  <span>🔥 <b>Daily burn</b> <span class="source-tag ora">[Exper. azure cost daily]</span>
        &nbsp;${meta['current_burn']/1000:.2f}K/day · Rolling 12m: {rolling12m_str}</span>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  KPI CARDS
# ══════════════════════════════════════════════════════════════════════════════
k1, k2, k3, k4, k5 = st.columns(5)

def acc_color(a):
    if a is None: return "tel"
    return "grn" if a >= 90 else "ora" if a >= 75 else "red"

with k1:
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-lbl">Annual Budget ({today.year})</div>
        <div class="kpi-val blu">${annual_budget/1000:.0f}K</div>
        <div class="kpi-sub">${meta['monthly_budget']/1000:.1f}K/month avg</div>
    </div>""", unsafe_allow_html=True)

with k2:
    st.markdown(f"""<div class="kpi-card {'red' if yef_over else 'green'}">
        <div class="kpi-lbl">Year-End Forecast</div>
        <div class="kpi-val {'red' if yef_over else 'grn'}">${yef/1000:.0f}K</div>
        <div class="kpi-sub">{budget_vs_yef}% of annual budget</div>
    </div>""", unsafe_allow_html=True)

with k3:
    ou_sign = "+" if over_under > 0 else ""
    st.markdown(f"""<div class="kpi-card {'red' if over_under > 0 else 'green'}">
        <div class="kpi-lbl">Variance vs Budget</div>
        <div class="kpi-val {'red' if over_under > 0 else 'grn'}">{ou_sign}${abs(over_under)/1000:.0f}K</div>
        <div class="kpi-sub">{'Over budget pace' if over_under > 0 else 'Under budget pace'}</div>
    </div>""", unsafe_allow_html=True)

with k4:
    rest = meta["projected_eom"] - meta["current_actual"]
    st.markdown(f"""<div class="kpi-card ora">
        <div class="kpi-lbl">Current Month Forecast</div>
        <div class="kpi-val ora">${meta['projected_eom']/1000:.1f}K</div>
        <div class="kpi-sub">${meta['current_actual']/1000:.1f}K actual&nbsp;+&nbsp;${max(rest,0)/1000:.1f}K projected</div>
    </div>""", unsafe_allow_html=True)

with k5:
    ac_disp = f"{acc_avg}%" if acc_avg is not None else "N/A"
    ac_sub  = f"avg over {completed_months} completed months" if acc_avg else "needs 2+ months of history"
    st.markdown(f"""<div class="kpi-card {'green' if (acc_avg and acc_avg>=90) else 'ora' if (acc_avg and acc_avg>=75) else 'red'}">
        <div class="kpi-lbl">Forecast Accuracy</div>
        <div class="kpi-val {acc_color(acc_avg)}">{ac_disp}</div>
        <div class="kpi-sub">{ac_sub}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
#  CHART 1 – 12-Month spend bar + confidence band + budget line
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='section-label'>📈 12-Month Spend vs Forecast vs Budget</div>", unsafe_allow_html=True)

labels = [r["label"] for r in rows]

fig = go.Figure()

# Confidence band (future months only) – fill between upper and lower
fc_rows   = [r for r in rows if r["type"] == "forecast"]
fc_labels = [r["label"] for r in fc_rows]
if fc_rows:
    fig.add_trace(go.Scatter(
        x=fc_labels + fc_labels[::-1],
        y=[r["upper"]/1000 for r in fc_rows] + [r["lower"]/1000 for r in fc_rows[::-1]],
        fill="toself", fillcolor="rgba(37,99,235,0.08)",
        line=dict(color="rgba(0,0,0,0)"), hoverinfo="skip",
        showlegend=True, name="Confidence Band (±15–35%)",
    ))

# Budget line
fig.add_trace(go.Scatter(
    x=labels, y=[r["budget"]/1000 for r in rows],
    mode="lines", name="Monthly Budget",
    line=dict(color="#94a3b8", width=1.5, dash="dot"),
    hovertemplate="%{x}<br>Budget: $%{y:.1f}K<extra></extra>",
))

# Completed months — actual bars
act_x = [r["label"] for r in rows if r["type"] == "actual" and r["actual"] is not None]
act_y = [r["actual"]/1000 for r in rows if r["type"] == "actual" and r["actual"] is not None]
if act_x:
    fig.add_trace(go.Bar(
        x=act_x, y=act_y, name="Actual Spend",
        marker_color="#2563eb", opacity=0.88, borderradius=3,
        hovertemplate="%{x}<br>Actual: $%{y:.1f}K<extra></extra>",
    ))

# Current month — stacked actual (solid) + projected rest (pale)
curr_row = next((r for r in rows if r["type"] == "current"), None)
if curr_row:
    fig.add_trace(go.Bar(
        x=[curr_row["label"]], y=[curr_row["actual"]/1000],
        name="Current Month (MTD — portal)",
        marker_color="#60a5fa", opacity=0.9,
        hovertemplate="%{x}<br>MTD Actual (portal): $%{y:.1f}K<extra></extra>",
    ))
    rest_k = (curr_row["forecast"] - curr_row["actual"]) / 1000
    if rest_k > 0:
        fig.add_trace(go.Bar(
            x=[curr_row["label"]], y=[rest_k],
            name="Projected (rest of month)",
            marker_color="#bfdbfe", opacity=0.85,
            hovertemplate="%{x}<br>Projected remaining: $%{y:.1f}K<extra></extra>",
        ))

# Forecast months
if fc_labels:
    fig.add_trace(go.Bar(
        x=fc_labels, y=[r["forecast"]/1000 for r in fc_rows],
        name="Forecasted Spend",
        marker_color="#a5b4fc", opacity=0.65,
        hovertemplate="%{x}<br>Forecast: $%{y:.1f}K<extra></extra>",
    ))

fig.update_layout(
    barmode="stack", plot_bgcolor="#fff", paper_bgcolor="#fff", height=380,
    margin=dict(t=20, b=40, l=60, r=20),
    legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1, font=dict(size=11)),
    xaxis=dict(showgrid=False, tickfont=dict(size=11)),
    yaxis=dict(showgrid=True, gridcolor="#f1f5f9", ticksuffix="K",
               tickfont=dict(size=11), title=dict(text="USD (thousands)", font=dict(size=10))),
    hovermode="x unified", font=dict(family="Inter, system-ui, sans-serif"),
)
st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
#  CHART 2 – Daily burn rate trend + cumulative spend vs budget
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='section-label'>🔥 Burn Rate Trend &amp; Cumulative Spend vs Budget</div>", unsafe_allow_html=True)

fig2 = make_subplots(specs=[[{"secondary_y": True}]])

# Derive daily burn from actuals; use live figure for current month
burn_x, burn_y = [], []
for r in rows:
    if r["type"] == "actual" and r["actual"] is not None and r["days_in_month"]:
        burn_x.append(r["label"])
        burn_y.append(r["actual"] / r["days_in_month"] / 1000)
    elif r["type"] == "current":
        burn_x.append(r["label"])
        burn_y.append(meta["current_burn"] / 1000)

if burn_x:
    fig2.add_trace(go.Scatter(
        x=burn_x, y=burn_y, mode="lines+markers",
        name="Daily Burn Rate ($K/day)",
        line=dict(color="#ea580c", width=2.5),
        marker=dict(size=6, color="#ea580c"),
        hovertemplate="%{x}<br>Burn: $%{y:.2f}K/day<extra></extra>",
    ), secondary_y=False)

# Cumulative spend (actuals + forecasts)
running = 0.0
cum_x, cum_y = [], []
for r in rows:
    val = r["actual"] if r["type"] == "actual" and r["actual"] is not None else (r["forecast"] or 0)
    running += val
    cum_x.append(r["label"])
    cum_y.append(running / 1000)

fig2.add_trace(go.Scatter(
    x=cum_x, y=cum_y, mode="lines",
    name="Cumulative Spend (actual + forecast)",
    line=dict(color="#7c3aed", width=1.8, dash="dash"),
    hovertemplate="%{x}<br>Cumulative: $%{y:.0f}K<extra></extra>",
), secondary_y=True)

# Cumulative budget reference
cum_bgt = [(i + 1) * meta["monthly_budget"] / 1000 for i in range(12)]
fig2.add_trace(go.Scatter(
    x=labels, y=cum_bgt, mode="lines",
    name="Annual Budget (cumulative pace)",
    line=dict(color="#94a3b8", width=1.5, dash="dot"),
    hovertemplate="%{x}<br>Budget pace: $%{y:.0f}K<extra></extra>",
), secondary_y=True)

fig2.update_layout(
    plot_bgcolor="#fff", paper_bgcolor="#fff", height=300,
    margin=dict(t=20, b=40, l=60, r=60),
    legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1, font=dict(size=11)),
    xaxis=dict(showgrid=False, tickfont=dict(size=11)),
    hovermode="x unified", font=dict(family="Inter, system-ui, sans-serif"),
)
fig2.update_yaxes(title_text="Daily Burn ($K/day)", showgrid=True, gridcolor="#f1f5f9",
                   ticksuffix="K", tickfont=dict(size=11), secondary_y=False)
fig2.update_yaxes(title_text="Cumulative ($K)", ticksuffix="K",
                   tickfont=dict(size=11), secondary_y=True)
st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
#  CHART 3 – Forecast accuracy (completed months only)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='section-label'>🎯 Forecast Accuracy by Month</div>", unsafe_allow_html=True)

acc_rows = [r for r in rows if r.get("accuracy") is not None]
if not acc_rows:
    st.info(
        "Forecast accuracy will populate once 2+ completed months of actuals are available "
        "in Azure_Expense_Details. Currently showing 0 completed months with prior-month data."
    )
else:
    acc_labels = [r["label"]    for r in acc_rows]
    acc_vals   = [r["accuracy"] for r in acc_rows]
    acc_colors = ["#16a34a" if a >= 90 else "#ea580c" if a >= 75 else "#dc2626" for a in acc_vals]

    fig3 = go.Figure(go.Bar(
        x=acc_labels, y=acc_vals,
        marker_color=acc_colors,
        text=[f"{a:.1f}%" for a in acc_vals], textposition="outside",
        hovertemplate="%{x}<br>Accuracy: %{y:.1f}%<extra></extra>",
    ))
    fig3.add_hline(y=90, line_dash="dot", line_color="#16a34a",
                   annotation_text="90% target", annotation_position="bottom right")
    fig3.update_layout(
        plot_bgcolor="#fff", paper_bgcolor="#fff", height=240,
        margin=dict(t=30, b=40, l=50, r=20),
        yaxis=dict(range=[0, 110], showgrid=True, gridcolor="#f1f5f9",
                   ticksuffix="%", tickfont=dict(size=11)),
        xaxis=dict(showgrid=False, tickfont=dict(size=11)),
        showlegend=False, font=dict(family="Inter, system-ui, sans-serif"),
    )
    st.plotly_chart(fig3, use_container_width=True)

    good = sum(1 for a in acc_vals if a >= 90)
    ok   = sum(1 for a in acc_vals if 75 <= a < 90)
    poor = sum(1 for a in acc_vals if a < 75)
    st.markdown(f"""
<div class="pill-row">
  <span class="acc-badge acc-good">✓ {good} months ≥90%</span>
  <span class="acc-badge acc-ok">~ {ok} months 75–89%</span>
  <span class="acc-badge acc-poor">✗ {poor} months &lt;75%</span>
  {'<span class="acc-badge acc-good">Overall: ' + str(acc_avg) + '%</span>' if acc_avg else ''}
</div>
""", unsafe_allow_html=True)

st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
#  DETAIL TABLE
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='section-label'>📋 12-Month Detail Table</div>", unsafe_allow_html=True)

def type_badge(t):
    cls   = {"actual": "mtype-actual", "current": "mtype-current", "forecast": "mtype-forecast"}[t]
    label = {"actual": "Actual",       "current": "In Progress",   "forecast": "Forecast"}[t]
    return f"<span class='{cls}'>{label}</span>"

def variance_html(fc, bgt):
    if fc is None or not bgt: return "<span style='color:#94a3b8'>—</span>"
    v   = fc - bgt
    pct = round(v / bgt * 100, 1)
    if v > 0: return f"<span style='color:#dc2626;font-weight:600'>+${v/1000:.1f}K ({pct}%)</span>"
    return f"<span style='color:#16a34a;font-weight:600'>{pct}% (${abs(v)/1000:.1f}K under)</span>"

def acc_badge(a):
    if a is None: return ""
    cls = "acc-good" if a >= 90 else "acc-ok" if a >= 75 else "acc-poor"
    return f"<span class='acc-badge {cls}'>{a:.1f}%</span>"

def band_cell(r):
    if r["type"] == "actual": return "—"
    lo, hi = r.get("lower"), r.get("upper")
    if lo is None: return "—"
    return f"${lo/1000:.1f}K – ${hi/1000:.1f}K"

rows_html = []
for r in rows:
    if   r["type"] == "actual":  row_css = "row-actual"
    elif r["type"] == "current": row_css = "row-current"
    elif r["forecast"] and r["budget"] and r["forecast"] > r["budget"] * 1.05: row_css = "row-over"
    else:                        row_css = "row-forecast"

    actual_d   = f"${r['actual']/1000:.1f}K"   if r["actual"]   is not None else "<span style='color:#94a3b8'>—</span>"
    forecast_d = f"${r['forecast']/1000:.1f}K"  if r["forecast"] is not None else "<span style='color:#94a3b8'>—</span>"
    burn_d     = f"${r['burn_day']*1000:.0f}/day" if r["burn_day"] else "—"

    rows_html.append(f"""<tr class='{row_css}'>
  <td><b>{r['label']}</b></td>
  <td>{type_badge(r['type'])}</td>
  <td class='num'>{actual_d}</td>
  <td class='num'>{forecast_d}</td>
  <td class='num'>${r['budget']/1000:.1f}K</td>
  <td class='num'>{variance_html(r['forecast'], r['budget'])}</td>
  <td class='num' style='font-size:10px;color:#64748b'>{band_cell(r)}</td>
  <td class='num'>{burn_d}</td>
  <td class='num'>{acc_badge(r.get('accuracy'))}</td>
</tr>""")

st.markdown(f"""
<div class="fg-wrap">
<table class="fg">
<thead><tr>
  <th>Month</th><th>Type</th>
  <th class="num">Actual Spend</th>
  <th class="num">Forecast / EOM</th>
  <th class="num">Monthly Budget</th>
  <th class="num">Forecast vs Budget</th>
  <th class="num">Confidence Band</th>
  <th class="num">Avg Daily Burn</th>
  <th class="num">Forecast Accuracy</th>
</tr></thead>
<tbody>{"".join(rows_html)}</tbody>
</table>
</div>
""", unsafe_allow_html=True)

st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
#  YEAR-END SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='section-label'>📊 Year-End Summary</div>", unsafe_allow_html=True)

col_chart, col_stats = st.columns([3, 2])

with col_chart:
    # Waterfall: each month as an incremental bar, final "total" bar
    wf_labels = [r["label"] for r in rows] + ["Year-End Total"]
    wf_vals   = [
        (r["actual"] if r["type"] == "actual" and r["actual"] is not None else r["forecast"] or 0)
        for r in rows
    ]
    wf_measure = ["relative"] * 12 + ["total"]
    wf_colors  = [
        "#2563eb" if r["type"] == "actual"
        else "#60a5fa" if r["type"] == "current"
        else "#a5b4fc"
        for r in rows
    ] + ["#7c3aed"]

    fig4 = go.Figure(go.Waterfall(
        orientation="v",
        measure=wf_measure,
        x=wf_labels,
        y=wf_vals + [0],
        connector=dict(line=dict(color="#e2e8f0", width=1)),
        decreasing=dict(marker=dict(color="#16a34a")),
        increasing=dict(marker=dict(color="#2563eb")),
        totals=dict(marker=dict(color="#7c3aed")),
        hovertemplate="%{x}<br>$%{y:,.0f}<extra></extra>",
    ))
    fig4.add_hline(
        y=annual_budget, line_dash="dot", line_color="#dc2626",
        annotation_text=f"Annual Budget ${annual_budget/1000:.0f}K",
        annotation_position="bottom right",
    )
    fig4.update_layout(
        plot_bgcolor="#fff", paper_bgcolor="#fff", height=340,
        margin=dict(t=30, b=40, l=60, r=20),
        yaxis=dict(showgrid=True, gridcolor="#f1f5f9", tickfont=dict(size=10)),
        xaxis=dict(tickfont=dict(size=9)),
        showlegend=False, font=dict(family="Inter, system-ui, sans-serif"),
        title=dict(text="Month-by-Month Build-up to Year-End", font=dict(size=12, color="#1e293b")),
    )
    st.plotly_chart(fig4, use_container_width=True)

with col_stats:
    pace_note = "On Track" if abs(over_under) / annual_budget < 0.05 else ("Over Pace" if yef_over else "Under Pace")
    pct_yr_done = round(completed_months / 12 * 100, 0)

    st.markdown(f"""
<div style="background:#fff;border-radius:10px;border:1px solid #e2e8f0;padding:18px 20px;">
  <div style="font-size:0.82rem;font-weight:700;color:#1e293b;margin-bottom:12px;">Year-End Forecast Summary</div>
  <table style="width:100%;font-size:12px;border-collapse:collapse;">
    <tr><td style="color:#64748b;padding:5px 0">Annual Budget</td>
        <td style="text-align:right;font-weight:600">${annual_budget/1000:.0f}K</td></tr>
    <tr style="border-top:1px solid #f1f5f9">
        <td style="color:#64748b;padding:5px 0">YE Forecast (dynamic)</td>
        <td style="text-align:right;font-weight:700;color:{'#dc2626' if yef_over else '#16a34a'}">${yef/1000:.0f}K</td></tr>
    <tr style="border-top:1px solid #f1f5f9">
        <td style="color:#64748b;padding:5px 0">Budget Variance</td>
        <td style="text-align:right;font-weight:600;color:{'#dc2626' if over_under>0 else '#16a34a'}">
          {'+' if over_under>0 else ''}${over_under/1000:.0f}K</td></tr>
    <tr style="border-top:1px solid #f1f5f9">
        <td style="color:#64748b;padding:5px 0">Run-Rate (rolling avg × 12)</td>
        <td style="text-align:right;font-weight:600">${meta['rolling_avg']*12/1000:.0f}K</td></tr>
    <tr style="border-top:1px solid #f1f5f9">
        <td style="color:#64748b;padding:5px 0">Current Daily Burn</td>
        <td style="text-align:right;font-weight:600">${meta['current_burn']/1000:.2f}K/day</td></tr>
    <tr style="border-top:1px solid #f1f5f9">
        <td style="color:#64748b;padding:5px 0">Months Completed</td>
        <td style="text-align:right;font-weight:600">{completed_months} of 12 ({int(pct_yr_done)}%)</td></tr>
    <tr style="border-top:1px solid #f1f5f9">
        <td style="color:#64748b;padding:5px 0">Months Remaining</td>
        <td style="text-align:right;font-weight:600">{forecast_months}</td></tr>
    <tr style="border-top:1px solid #f1f5f9">
        <td style="color:#64748b;padding:5px 0">Forecast Accuracy (avg)</td>
        <td style="text-align:right;font-weight:600;color:{'#16a34a' if acc_avg and acc_avg>=90 else '#ea580c' if acc_avg and acc_avg>=75 else '#94a3b8'}">
          {str(acc_avg)+'%' if acc_avg else 'N/A'}</td></tr>
    <tr style="border-top:1px solid #f1f5f9">
        <td style="color:#64748b;padding:5px 0">Pace</td>
        <td style="text-align:right;font-weight:600">{pace_note}</td></tr>
  </table>
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div class="method-box" style="margin-top:12px;">
  <b>Data sourcing — MedInsight Azure Spend Analysis</b><br>
  <b>Actuals</b> — <code>CALCULATE(SUMX([Cost]), exclude max date="Yes")</code> · Complete_Month ≠ "Incomplete" · identical to PBI report<br>
  <b>Current month MTD</b> — <code>CALCULATE([Azure cost], Complete_Month="Incomplete")</code> · bypasses slicer dependency<br>
  <b>Daily burn</b> — <code>[Exper. azure cost daily]</code> measure<br>
  <b>EOM projection</b> — MTD + daily burn × days remaining in month<br>
  <b>Future forecast</b> — 70% rolling 3-month avg + 30% burn × days in month<br>
  <b>Confidence band</b> — ±15% base, +2%/month out<br>
  <b>Budget</b> — entered manually via sidebar (no budget table in this model)
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  EXPORT HTML  — injects real computed numbers into a self-contained HTML file
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("<div class='section-label'>📥 Export</div>", unsafe_allow_html=True)

# Build JSON payload for the HTML template
export_payload = {
    "generated":      generated,
    "tenantName":     TENANT_NAME,
    "userEmail":      user_email,
    "annualBudget":   round(annual_budget, 2),
    "monthlyBudget":  round(meta["monthly_budget"], 2),
    "yef":            round(yef, 2),
    "overUnder":      round(over_under, 2),
    "projectedEOM":   round(meta["projected_eom"], 2),
    "currentActual":  round(meta["current_actual"], 2),
    "currentBurn":    round(meta["current_burn"], 2),
    "daysRemaining":  meta["days_remaining"],
    "rollingAvg":     round(meta["rolling_avg"], 2),
    "accAvg":         acc_avg,
    "completedMonths": completed_months,
    "forecastMonths":  forecast_months,
    "rows": [
        {
            "label":      r["label"],
            "type":       r["type"],
            "actual":     round(r["actual"],   2) if r["actual"]   is not None else None,
            "forecast":   round(r["forecast"], 2) if r["forecast"] is not None else None,
            "budget":     round(r["budget"],   2),
            "lower":      round(r["lower"],    2) if r["lower"]    is not None else None,
            "upper":      round(r["upper"],    2) if r["upper"]    is not None else None,
            "burn_day":   round(r["burn_day"], 4) if r["burn_day"] is not None else None,
            "accuracy":   r.get("accuracy"),
        }
        for r in rows
    ],
}

# Read the HTML template and inject the data
try:
    import os
    template_path = os.path.join(os.path.dirname(__file__), "..", "forecast_dashboard.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html_template = f.read()

    # Replace the static DATA block with real numbers
    json_str = json.dumps(export_payload, ensure_ascii=False)
    html_out = html_template.replace(
        "// @@INJECT_DATA@@",
        f"const EXPORT = {json_str};\n"
        "const MONTHS = EXPORT.rows.map(r => r.label);\n"
        "const BUDGET_MO = EXPORT.monthlyBudget / 1000;\n"
        "const DATA = EXPORT.rows.map(r => ({...r, "
        "actual: r.actual ? r.actual/1000 : null, "
        "forecast: r.forecast ? r.forecast/1000 : null, "
        "budget: r.budget/1000, "
        "lower: r.lower ? r.lower/1000 : null, "
        "upper: r.upper ? r.upper/1000 : null, "
        "burn: r.burn_day ? r.burn_day : null }));\n",
    )

    exp_col, _ = st.columns([2, 8])
    with exp_col:
        st.download_button(
            "⬇ Export as HTML (live data)",
            html_out.encode("utf-8"),
            file_name=f"Azure_Forecast_{today.strftime('%Y%m%d')}.html",
            mime="text/html",
            key="dl_html",
        )
except Exception as exc:
    st.info(f"HTML export unavailable: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
#  FOOTER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(f"""
<div class="dash-footer">
  <span>
    {completed_months} months actual (Azure_Expense_Details) &nbsp;·&nbsp;
    {forecast_months} months forecast &nbsp;·&nbsp;
    accuracy {str(acc_avg)+'%' if acc_avg else 'N/A'}
  </span>
  <span>
    Power BI REST API &nbsp;·&nbsp; Dataset: {DATASET_ID[:8]}...
    &nbsp;·&nbsp; Cache: 5 min &nbsp;·&nbsp; Auto-refresh: 5 min
  </span>
</div>
""", unsafe_allow_html=True)
