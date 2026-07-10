try:
    import truststore
    truststore.inject_into_ssl()  # Windows cert store — fixes corporate proxy SSL
except ImportError:
    pass  # not needed on Linux/cloud environments

import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import time
from datetime import datetime
from calendar import monthrange
from azure.identity import AzureCliCredential
from streamlit_autorefresh import st_autorefresh

# ── Configuration ──────────────────────────────────────────────────────────────
TENANT_ID            = "e240d61e-61e3-4c9e-ab90-8644b2f4d2a9"
WORKSPACE_ID         = "eca3c81e-a968-42a5-899f-d8fc1a45ebec"
WORKSPACE_NAME       = "MI - Azure Cost Analysis and FinOps Dashboard"
DATASET_ID           = "10b45f31-71d5-463c-ac78-bce785b9fd8f"
SEMANTIC_MODEL_NAME  = "Azure_Spend_Forecast"
FORECAST_YEAR        = 2026
TENANT_NAME          = "MedInsight Production · Engineering · Milliman"

st_autorefresh(interval=300000)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
#MainMenu, footer, [data-testid="stToolbar"] { display:none !important; }
section[data-testid="stSidebar"] {
  background-color:#1a2744 !important; transform:translateX(0px) !important;
  display:block !important; visibility:visible !important; min-width:260px !important;
}
[data-testid="stSidebarCollapseButton"] { display:none !important; }
[data-testid="collapsedControl"]        { display:none !important; }

.top-banner {
  background: linear-gradient(100deg, #1a3a6e 0%, #1e4d8c 60%, #2255a4 100%);
  border-radius:12px; padding:22px 32px 18px 32px; margin-bottom:20px;
  box-shadow:0 4px 18px rgba(26,58,110,0.20); position:relative; overflow:hidden;
}
.top-banner::before {
  content:""; position:absolute; left:0; top:0; bottom:0; width:5px;
  background:linear-gradient(180deg,#60a5fa 0%,#2563eb 100%);
  border-radius:12px 0 0 12px;
}
.top-banner .dash-title { font-size:1.55rem; font-weight:700; color:#fff; line-height:1.3; }
.top-banner .dash-title span { color:#60a5fa; }
.top-banner .dash-meta { display:flex; gap:0; flex-wrap:wrap; margin-top:8px; align-items:center; }
.top-banner .dash-meta .m {
  font-size:0.73rem; color:rgba(255,255,255,0.55);
  padding-right:14px; margin-right:14px; border-right:1px solid rgba(255,255,255,0.15);
}
.top-banner .dash-meta .m:last-child { border-right:none; }

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
.kpi-sub { font-size:0.71rem; color:#64748b; margin-top:3px; }

.section-label {
  font-size:0.95rem; font-weight:700; color:#1e293b;
  margin:18px 0 10px 0; padding-bottom:6px; border-bottom:2px solid #e2e8f0;
}
.source-tag {
  display:inline-block; font-size:10px; font-weight:600; padding:1px 7px;
  border-radius:4px; background:#eff6ff; color:#2563eb;
  border:1px solid #bfdbfe; margin-left:6px;
}
.source-tag.grn { background:#f0fdf4; color:#15803d; border-color:#86efac; }

.fg-wrap { overflow-x:auto; border-radius:8px; border:1px solid #e2e8f0; }
table.fg { width:100%; border-collapse:collapse; font-size:12px; }
table.fg thead tr { background:#f8fafc; border-bottom:2px solid #e2e8f0; }
table.fg th { padding:9px 12px; text-align:left; font-size:11px; font-weight:600;
              text-transform:uppercase; letter-spacing:.05em; color:#64748b; white-space:nowrap; }
table.fg th.num { text-align:right; }
table.fg td { padding:7px 12px; border-bottom:1px solid #f1f5f9; }
table.fg td.num { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
table.fg tr.row-actual   td { background:#f0fdf4; }
table.fg tr.row-current  td { background:#eff6ff; font-weight:600; }
table.fg tr.row-forecast td { background:#fafafa; color:#64748b; }
table.fg tr.row-over     td { background:#fef2f2; }
table.fg tr:hover td     { background:#f8fafc; }

.mtype-actual   { background:#dcfce7; color:#15803d; border-radius:4px; padding:1px 7px; font-size:10px; font-weight:600; display:inline-block; }
.mtype-current  { background:#dbeafe; color:#1d4ed8; border-radius:4px; padding:1px 7px; font-size:10px; font-weight:600; display:inline-block; }
.mtype-forecast { background:#f1f5f9; color:#64748b;  border-radius:4px; padding:1px 7px; font-size:10px; font-weight:600; display:inline-block; }

.acc-badge { display:inline-flex; align-items:center; padding:3px 10px; border-radius:20px;
             font-size:10px; font-weight:700; letter-spacing:.04em; white-space:nowrap; }
.acc-good  { background:#dcfce7; color:#16a34a; border:1px solid #86efac; }
.acc-ok    { background:#fef9c3; color:#ca8a04; border:1px solid #fde047; }
.acc-poor  { background:#fee2e2; color:#dc2626; border:1px solid #fca5a5; }

.method-box {
  background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px;
  padding:14px 16px; font-size:11px; color:#475569; line-height:1.7; margin-top:12px;
}
.dash-footer {
  font-size:0.7rem; color:#94a3b8; margin-top:24px; padding-top:10px;
  border-top:1px solid #e2e8f0; display:flex; justify-content:space-between; flex-wrap:wrap; gap:6px;
}
.stDownloadButton > button {
  background:#2563eb !important; color:#fff !important;
  border:none !important; border-radius:6px !important;
  font-size:0.78rem !important; padding:7px 18px !important; font-weight:600 !important;
}
</style>
""", unsafe_allow_html=True)


# ── Auth ───────────────────────────────────────────────────────────────────────
def _sp_token_via_msal(tenant_id, client_id, client_secret):
    """Get SP token via MSAL with a shared requests session (Windows cert store already injected)."""
    import msal
    session = requests.Session()
    app = msal.ConfidentialClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=client_secret,
        http_client=session,
    )
    result = app.acquire_token_for_client(
        scopes=["https://analysis.windows.net/powerbi/api/.default"]
    )
    if "access_token" in result:
        return result["access_token"]
    raise RuntimeError(f"MSAL SP auth failed: {result.get('error_description', result)}")


def get_token():
    # Try az login (user delegated token) first — works locally, bypasses SP tenant restriction
    try:
        cred = AzureCliCredential(tenant_id=TENANT_ID)
        return cred.get_token("https://analysis.windows.net/powerbi/api/.default").token
    except Exception:
        pass  # no az login session — try SP next

    # Fallback: Service Principal from secrets.toml
    try:
        az = st.secrets["azure"]
        return _sp_token_via_msal(az["tenant_id"], az["client_id"], az["client_secret"])
    except (KeyError, FileNotFoundError):
        pass
    except Exception as sp_err:
        st.error(
            f"**Auth failed.** SP error: `{sp_err}`\n\n"
            "**For local use:** Run `az login --tenant e240d61e-61e3-4c9e-ab90-8644b2f4d2a9` in terminal, then refresh.\n\n"
            "**For Streamlit Cloud (SP):** A Power BI admin must enable "
            "**Allow service principals to use Power BI APIs** in the "
            "[Power BI Admin Portal → Developer settings]"
            "(https://app.powerbi.com/admin-portal/tenantSettings)."
        )
        st.stop()

    st.error(
        "**Auth failed — no valid credential found.**\n\n"
        "Run `az login --tenant e240d61e-61e3-4c9e-ab90-8644b2f4d2a9` in your terminal, then refresh."
    )
    st.stop()


def strip_prefix(col):
    return col.split("[")[-1].rstrip("]") if "[" in col else col


def _pbi_query(token, dax, timeout=60):
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
    if not resp.ok:
        raise RuntimeError(f"PBI API {resp.status_code}: {resp.text[:800]}")
    rows = resp.json()["results"][0]["tables"][0].get("rows", [])
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df.columns = [strip_prefix(c) for c in df.columns]
    return df


# ── DAX — single flat query against Azure_Spend_Forecast model ────────────────
# Table: Azure_spend_Analysis
# Columns: billing_period_start_date, complete_month, total_cost,
#          max_date, days_in_month, days_with_data
_DAX = """
EVALUATE
SUMMARIZECOLUMNS(
    'Azure_spend_Analysis'[complete_month],
    'Azure_spend_Analysis'[billing_period_start_date],
    'Azure_spend_Analysis'[max_date],
    'Azure_spend_Analysis'[days_in_month],
    'Azure_spend_Analysis'[days_with_data],
    "total_cost", SUM('Azure_spend_Analysis'[total_cost])
)
ORDER BY 'Azure_spend_Analysis'[billing_period_start_date] ASC
"""


@st.cache_data(ttl=300, show_spinner=False)
def fetch_spend_data(token):
    t0 = time.time()
    try:
        df = _pbi_query(token, _DAX)
    except Exception as exc:
        st.warning(f"Could not query Azure_spend_Analysis: {exc}")
        return pd.DataFrame(), {}, round(time.time() - t0, 1)

    if df.empty:
        return pd.DataFrame(), {}, round(time.time() - t0, 1)

    df.columns = [c.lower() for c in df.columns]
    df["total_cost"]                 = pd.to_numeric(df["total_cost"], errors="coerce").fillna(0)
    df["days_in_month"]              = pd.to_numeric(df["days_in_month"], errors="coerce").fillna(0).astype(int)
    df["days_with_data"]             = pd.to_numeric(df["days_with_data"], errors="coerce").fillna(0).astype(int)
    df["billing_period_start_date"]  = pd.to_datetime(df["billing_period_start_date"], errors="coerce", utc=True)
    df["max_date"]                   = pd.to_datetime(df["max_date"], errors="coerce", utc=True)

    # Split incomplete (current partial month) vs completed months
    is_incomplete = df["complete_month"].str.strip() == "Incomplete"
    hist_df       = df[~is_incomplete].copy()
    inc_df        = df[is_incomplete]

    hist_df["usageyear"]  = hist_df["billing_period_start_date"].dt.year.fillna(0).astype(int)
    hist_df["usagemonth"] = hist_df["billing_period_start_date"].dt.month.fillna(0).astype(int)
    hist_df = hist_df[hist_df["usageyear"] > 0].sort_values(["usageyear", "usagemonth"])

    live_row = {}
    if not inc_df.empty:
        r = inc_df.iloc[0]
        live_row["currentmtd"]    = float(r["total_cost"])
        live_row["days_in_month"] = int(r["days_in_month"])
        live_row["days_with_data"]= int(r["days_with_data"])
        live_row["maxdate"]       = str(r["max_date"])[:10] if pd.notna(r["max_date"]) else "—"
    elif not hist_df.empty:
        live_row["currentmtd"]    = 0.0
        live_row["days_in_month"] = 0
        live_row["days_with_data"]= 0
        live_row["maxdate"]       = str(df["max_date"].max())[:10]

    return hist_df, live_row, round(time.time() - t0, 1)


# ── Forecast engine ────────────────────────────────────────────────────────────
def build_forecast(
    hist_df,
    live_row,
    today,
    monthly_budget,
    target_year,
    rolling_weight,
    burn_weight,
    conf_base,
    conf_step,
    portal_current_mtd=None,
):
    curr_yr = target_year
    curr_mo = today.month if target_year == today.year else 1

    current_actual   = float(live_row.get("currentmtd", 0) or 0)
    if portal_current_mtd is not None and portal_current_mtd > 0:
        current_actual = float(portal_current_mtd)
    days_in_curr_mo  = int(live_row.get("days_in_month", monthrange(curr_yr, curr_mo)[1]))
    days_with_data   = int(live_row.get("days_with_data", today.day))
    days_remaining   = days_in_curr_mo - days_with_data
    # Daily burn from actual MTD ÷ days elapsed
    current_burn     = (current_actual / days_with_data) if days_with_data > 0 and current_actual > 0 else 0
    projected_eom    = current_actual + current_burn * days_remaining
    if projected_eom <= 0 and current_actual > 0:
        projected_eom = current_actual

    # Build year/month → cost lookup from completed months
    actual_by_ym = {}
    if not hist_df.empty:
        for _, row in hist_df.iterrows():
            actual_by_ym[(int(row["usageyear"]), int(row["usagemonth"]))] = float(row["total_cost"])

    # Rolling 3-month average from completed months this year
    completed = [actual_by_ym[(curr_yr, m)] for m in range(1, curr_mo) if (curr_yr, m) in actual_by_ym]
    if len(completed) >= 3:
        rolling_avg = sum(completed[-3:]) / 3
    elif completed:
        rolling_avg = sum(completed) / len(completed)
    else:
        rolling_avg = monthly_budget

    def band(base, months_out):
        spread = conf_base + months_out * conf_step
        return round(base * (1 - spread), 2), round(base * (1 + spread), 2)

    month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    rows = []

    for m in range(1, 13):
        dim   = monthrange(curr_yr, m)[1]
        label = f"{month_names[m-1]} {curr_yr}"

        if m < curr_mo:
            actual   = actual_by_ym.get((curr_yr, m))
            row_type = "actual"
            forecast = actual
            lo, hi   = (actual, actual) if actual is not None else (None, None)
            burn_day = (actual / dim) if actual else None
            accuracy = None

        elif m == curr_mo and target_year == today.year:
            actual   = current_actual
            row_type = "current"
            forecast = projected_eom
            lo, hi   = band(forecast, 0)
            burn_day = current_burn
            accuracy = None

        else:
            months_out  = m - curr_mo
            burn_extrap = (current_burn * dim) if current_burn > 0 else rolling_avg
            forecast    = round((rolling_weight * rolling_avg) + (burn_weight * burn_extrap), 2)
            actual      = None
            row_type    = "forecast"
            lo, hi      = band(forecast, months_out)
            burn_day    = current_burn if current_burn > 0 else None
            accuracy    = None

        rows.append({
            "month_num": m, "month_name": month_names[m-1], "year": curr_yr,
            "label": label, "type": row_type,
            "actual": actual, "budget": monthly_budget,
            "forecast": forecast, "lower": lo, "upper": hi,
            "burn_day": burn_day, "days_in_month": dim, "accuracy": None,
        })

    # Back-calculate forecast accuracy for completed months
    for i, row in enumerate(rows):
        if row["type"] != "actual" or row["actual"] is None:
            continue
        preceding = [rows[j]["actual"] for j in range(max(0, i-3), i) if rows[j]["actual"] is not None]
        if not preceding:
            continue
        implied = sum(preceding) / len(preceding)
        if row["actual"] > 0:
            rows[i]["accuracy"] = round(100 - abs(row["actual"] - implied) / row["actual"] * 100, 1)

    meta = {
        "monthly_budget":  monthly_budget,
        "annual_budget":   monthly_budget * 12,
        "current_actual":  current_actual,
        "current_burn":    current_burn,
        "projected_eom":   projected_eom,
        "days_remaining":  days_remaining,
        "days_with_data":  days_with_data,
        "days_in_curr_mo": days_in_curr_mo,
        "rolling_avg":     rolling_avg,
        "completed_count": len(completed),
    }
    return rows, meta


def year_end_forecast(rows):
    return sum(
        r["actual"] if r["type"] == "actual" and r["actual"] is not None
        else (r["forecast"] or 0)
        for r in rows
    )

def avg_accuracy(rows):
    vals = [r["accuracy"] for r in rows if r.get("accuracy") is not None]
    return round(sum(vals) / len(vals), 1) if vals else None


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("<div style='color:#fff;font-size:0.8rem;font-weight:700;margin-bottom:6px;'>💰 Monthly Budget</div>",
                unsafe_allow_html=True)
    monthly_budget_input = st.number_input(
        "Monthly budget ($)", min_value=0, value=480_000, step=10_000,
        format="%d", label_visibility="collapsed",
    )
    st.markdown(
        f"<div style='color:rgba(255,255,255,0.4);font-size:0.65rem;margin-top:4px;'>"
        f"Annual: ${monthly_budget_input * 12 / 1_000_000:.2f}M</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<hr style='border-color:rgba(255,255,255,0.1);margin:14px 0'>", unsafe_allow_html=True)
    st.markdown("<div style='color:#fff;font-size:0.8rem;font-weight:700;margin-bottom:6px;'>📐 Forecast Method</div>", unsafe_allow_html=True)
    st.caption("Weighted rolling-average monthly forecast for remaining 2026 months.")
    rolling_weight = st.slider("Rolling average weight", min_value=0.5, max_value=0.9, value=0.7, step=0.05)
    burn_weight = round(1.0 - rolling_weight, 2)
    st.caption(f"Burn-rate weight: {burn_weight:.2f}")
    conf_base = st.slider("Confidence base spread", min_value=0.10, max_value=0.25, value=0.15, step=0.01)
    conf_step = st.slider("Confidence monthly increment", min_value=0.01, max_value=0.05, value=0.02, step=0.01)

    st.markdown("<hr style='border-color:rgba(255,255,255,0.1);margin:14px 0'>", unsafe_allow_html=True)
    st.markdown("<div style='color:#fff;font-size:0.8rem;font-weight:700;margin-bottom:6px;'>🔌 Azure Portal (Optional)</div>", unsafe_allow_html=True)
    use_portal_override = st.checkbox("Use Azure Portal current-month MTD override", value=False)
    portal_current_mtd = None
    if use_portal_override:
        portal_current_mtd = st.number_input(
            "Portal MTD spend ($)",
            min_value=0.0,
            value=0.0,
            step=1000.0,
            format="%.2f",
        )

    st.markdown("<hr style='border-color:rgba(255,255,255,0.1);margin:14px 0'>", unsafe_allow_html=True)


# ── Load data ──────────────────────────────────────────────────────────────────
token = get_token()
today = datetime.now()

with st.spinner(f"Loading Azure spend data from {SEMANTIC_MODEL_NAME}…"):
    hist_df, live_row, elapsed = fetch_spend_data(token)

if hist_df.empty and not live_row:
    st.warning(
        "No data returned from the Semantic Model.\n\n"
        f"Workspace: **{WORKSPACE_NAME}**\n\n"
        f"Dataset: **{SEMANTIC_MODEL_NAME}**"
    )
    st.stop()

rows, meta    = build_forecast(
    hist_df,
    live_row,
    today,
    float(monthly_budget_input),
    FORECAST_YEAR,
    rolling_weight,
    burn_weight,
    conf_base,
    conf_step,
    portal_current_mtd=portal_current_mtd,
)
yef           = year_end_forecast(rows)
acc_avg       = avg_accuracy(rows)
generated     = today.strftime("%Y-%m-%d %H:%M")
user_email    = st.session_state.get("user_email", "anmol.sharma@milliman.com")
completed_months = sum(1 for r in rows if r["type"] == "actual")
forecast_months  = sum(1 for r in rows if r["type"] == "forecast")
annual_budget    = meta["annual_budget"]
yef_over         = yef > annual_budget
over_under       = yef - annual_budget
budget_vs_yef    = round(yef / annual_budget * 100, 1) if annual_budget > 0 else 0
max_date_str     = live_row.get("maxdate", "—")


# ── Banner ─────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="top-banner">
    <div class="dash-title">Azure Spend <span>{FORECAST_YEAR} Monthly Forecast</span></div>
  <div class="dash-meta">
    <span class="m">{TENANT_NAME}</span>
        <span class="m">Workspace: {WORKSPACE_NAME}</span>
        <span class="m">Semantic model: {SEMANTIC_MODEL_NAME}</span>
    <span class="m">{user_email}</span>
    <span class="m">Generated: {generated}</span>
    <span class="m">Rolling avg (last 3 mo): ${meta['rolling_avg']/1000:.1f}K/mo</span>
    <span class="m">Daily burn: ${meta['current_burn']/1000:.2f}K/day · {meta['days_remaining']}d remaining</span>
    <span class="m">Data as of: {max_date_str} · Query: {elapsed}s</span>
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px 16px;
            font-size:11px;color:#475569;display:flex;gap:20px;flex-wrap:wrap;margin-bottom:16px;">
  <span>📊 <b>Actuals</b>
        <span class="source-tag grn">Azure_spend_Analysis · SUM(total_cost) · complete_month ≠ Incomplete</span>
    &nbsp;{len(hist_df)} completed months</span>
  <span>💰 <b>Current MTD</b>
    <span class="source-tag">complete_month = Incomplete</span>
        &nbsp;${meta['current_actual']/1000:.1f}K ({meta['days_with_data']} days){' · portal override' if use_portal_override else ''}</span>
  <span>🔥 <b>Daily burn</b>
    <span class="source-tag" style="background:#fff7ed;color:#c2410c;border-color:#fed7aa;">MTD ÷ days elapsed</span>
    &nbsp;${meta['current_burn']/1000:.2f}K/day</span>
</div>
""", unsafe_allow_html=True)


# ── KPI cards ──────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)

def acc_color(a):
    if a is None: return "blu"
    return "grn" if a >= 90 else "ora" if a >= 75 else "red"

with k1:
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-lbl">Annual Budget ({FORECAST_YEAR})</div>
        <div class="kpi-val blu">${annual_budget/1000:.0f}K</div>
        <div class="kpi-sub">${meta['monthly_budget']/1000:.1f}K/month</div>
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
    rest = max(meta["projected_eom"] - meta["current_actual"], 0)
    st.markdown(f"""<div class="kpi-card ora">
        <div class="kpi-lbl">Current Month EOM</div>
        <div class="kpi-val ora">${meta['projected_eom']/1000:.1f}K</div>
        <div class="kpi-sub">${meta['current_actual']/1000:.1f}K MTD + ${rest/1000:.1f}K projected</div>
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


# ── Chart 1 — 12-month spend bar + confidence band + budget line ───────────────
st.markdown("<div class='section-label'>📈 12-Month Spend vs Forecast vs Budget</div>", unsafe_allow_html=True)

labels   = [r["label"] for r in rows]
fc_rows  = [r for r in rows if r["type"] == "forecast"]
fc_labels= [r["label"] for r in fc_rows]

fig = go.Figure()

if fc_rows:
    fig.add_trace(go.Scatter(
        x=fc_labels + fc_labels[::-1],
        y=[r["upper"]/1000 for r in fc_rows] + [r["lower"]/1000 for r in fc_rows[::-1]],
        fill="toself", fillcolor="rgba(37,99,235,0.08)",
        line=dict(color="rgba(0,0,0,0)"), hoverinfo="skip",
        showlegend=True, name="Confidence Band (±15–35%)",
    ))

fig.add_trace(go.Scatter(
    x=labels, y=[r["budget"]/1000 for r in rows],
    mode="lines", name="Monthly Budget",
    line=dict(color="#94a3b8", width=1.5, dash="dot"),
    hovertemplate="%{x}<br>Budget: $%{y:.1f}K<extra></extra>",
))

act_x = [r["label"] for r in rows if r["type"] == "actual" and r["actual"] is not None]
act_y = [r["actual"]/1000 for r in rows if r["type"] == "actual" and r["actual"] is not None]
if act_x:
    fig.add_trace(go.Bar(x=act_x, y=act_y, name="Actual Spend",
        marker_color="#2563eb", opacity=0.88,
        hovertemplate="%{x}<br>Actual: $%{y:.1f}K<extra></extra>"))

curr_row = next((r for r in rows if r["type"] == "current"), None)
if curr_row:
    fig.add_trace(go.Bar(
        x=[curr_row["label"]], y=[curr_row["actual"]/1000],
        name="Current Month (MTD)", marker_color="#60a5fa", opacity=0.9,
        hovertemplate="%{x}<br>MTD: $%{y:.1f}K<extra></extra>"))
    rest_k = (curr_row["forecast"] - curr_row["actual"]) / 1000
    if rest_k > 0:
        fig.add_trace(go.Bar(
            x=[curr_row["label"]], y=[rest_k],
            name="Projected (rest of month)", marker_color="#bfdbfe", opacity=0.85,
            hovertemplate="%{x}<br>Projected remaining: $%{y:.1f}K<extra></extra>"))

if fc_labels:
    fig.add_trace(go.Bar(x=fc_labels, y=[r["forecast"]/1000 for r in fc_rows],
        name="Forecasted Spend", marker_color="#a5b4fc", opacity=0.65,
        hovertemplate="%{x}<br>Forecast: $%{y:.1f}K<extra></extra>"))

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


# ── Chart 2 — Daily burn + cumulative spend ────────────────────────────────────
st.markdown("<div class='section-label'>📉 Cumulative Spend Pace vs Budget (Monthly Forecast)</div>", unsafe_allow_html=True)

fig2 = make_subplots(specs=[[{"secondary_y": True}]])

burn_x, burn_y = [], []
for r in rows:
    if r["type"] == "actual" and r["actual"] is not None and r["days_in_month"]:
        burn_x.append(r["label"]); burn_y.append(r["actual"] / r["days_in_month"] * 30 / 1000)
    elif r["type"] == "current":
        burn_x.append(r["label"]); burn_y.append(meta["current_burn"] * 30 / 1000)

if burn_x:
    fig2.add_trace(go.Scatter(x=burn_x, y=burn_y, mode="lines+markers",
        name="Monthly Run-Rate at Current Pace ($K/mo)", line=dict(color="#ea580c", width=2.5),
        marker=dict(size=6), hovertemplate="%{x}<br>Run-rate: $%{y:.2f}K/mo<extra></extra>"),
        secondary_y=False)

running = 0.0
cum_x, cum_y = [], []
for r in rows:
    val = r["actual"] if r["type"] == "actual" and r["actual"] is not None else (r["forecast"] or 0)
    running += val; cum_x.append(r["label"]); cum_y.append(running / 1000)

fig2.add_trace(go.Scatter(x=cum_x, y=cum_y, mode="lines",
    name="Cumulative Spend", line=dict(color="#7c3aed", width=1.8, dash="dash"),
    hovertemplate="%{x}<br>Cumulative: $%{y:.0f}K<extra></extra>"), secondary_y=True)

cum_bgt = [(i+1) * meta["monthly_budget"] / 1000 for i in range(12)]
fig2.add_trace(go.Scatter(x=labels, y=cum_bgt, mode="lines",
    name="Budget Pace", line=dict(color="#94a3b8", width=1.5, dash="dot"),
    hovertemplate="%{x}<br>Budget pace: $%{y:.0f}K<extra></extra>"), secondary_y=True)

fig2.update_layout(
    plot_bgcolor="#fff", paper_bgcolor="#fff", height=300,
    margin=dict(t=20, b=40, l=60, r=60),
    legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1, font=dict(size=11)),
    xaxis=dict(showgrid=False, tickfont=dict(size=11)),
    hovermode="x unified", font=dict(family="Inter, system-ui, sans-serif"),
)
fig2.update_yaxes(title_text="Monthly Run-Rate ($K/mo)", showgrid=True, gridcolor="#f1f5f9",
                  ticksuffix="K", tickfont=dict(size=11), secondary_y=False)
fig2.update_yaxes(title_text="Cumulative ($K)", ticksuffix="K",
                  tickfont=dict(size=11), secondary_y=True)
st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")


# ── Chart 3 — Forecast accuracy ────────────────────────────────────────────────
st.markdown("<div class='section-label'>🎯 Forecast Accuracy by Month</div>", unsafe_allow_html=True)

acc_rows = [r for r in rows if r.get("accuracy") is not None]
if not acc_rows:
    st.info("Forecast accuracy will populate once 2+ completed months of actuals are available.")
else:
    acc_vals   = [r["accuracy"] for r in acc_rows]
    acc_colors = ["#16a34a" if a >= 90 else "#ea580c" if a >= 75 else "#dc2626" for a in acc_vals]
    fig3 = go.Figure(go.Bar(
        x=[r["label"] for r in acc_rows], y=acc_vals,
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

st.markdown("---")


# ── Detail table ───────────────────────────────────────────────────────────────
st.markdown("<div class='section-label'>📋 12-Month Detail Table</div>", unsafe_allow_html=True)

def type_badge(t):
    cls   = {"actual":"mtype-actual","current":"mtype-current","forecast":"mtype-forecast"}[t]
    label = {"actual":"Actual","current":"In Progress","forecast":"Forecast"}[t]
    return f"<span class='{cls}'>{label}</span>"

def variance_html(fc, bgt):
    if fc is None or not bgt: return "<span style='color:#94a3b8'>—</span>"
    v = fc - bgt; pct = round(v / bgt * 100, 1)
    if v > 0: return f"<span style='color:#dc2626;font-weight:600'>+${v/1000:.1f}K ({pct}%)</span>"
    return f"<span style='color:#16a34a;font-weight:600'>{pct}% (${abs(v)/1000:.1f}K under)</span>"

def acc_badge_html(a):
    if a is None: return ""
    cls = "acc-good" if a >= 90 else "acc-ok" if a >= 75 else "acc-poor"
    return f"<span class='acc-badge {cls}'>{a:.1f}%</span>"

rows_html = []
for r in rows:
    if   r["type"] == "actual":  row_css = "row-actual"
    elif r["type"] == "current": row_css = "row-current"
    elif r["forecast"] and r["budget"] and r["forecast"] > r["budget"] * 1.05: row_css = "row-over"
    else:                        row_css = "row-forecast"

    actual_d   = f"${r['actual']/1000:.1f}K"   if r["actual"]   is not None else "<span style='color:#94a3b8'>—</span>"
    forecast_d = f"${r['forecast']/1000:.1f}K"  if r["forecast"] is not None else "<span style='color:#94a3b8'>—</span>"
    lo, hi     = r.get("lower"), r.get("upper")
    band_d     = f"${lo/1000:.1f}K–${hi/1000:.1f}K" if lo is not None and r["type"] != "actual" else "—"
    burn_d     = f"${r['burn_day']*1000:.0f}/day" if r["burn_day"] else "—"

    rows_html.append(f"""<tr class='{row_css}'>
  <td><b>{r['label']}</b></td><td>{type_badge(r['type'])}</td>
  <td class='num'>{actual_d}</td><td class='num'>{forecast_d}</td>
  <td class='num'>${r['budget']/1000:.1f}K</td>
  <td class='num'>{variance_html(r['forecast'], r['budget'])}</td>
  <td class='num' style='font-size:10px;color:#64748b'>{band_d}</td>
  <td class='num'>{burn_d}</td>
  <td class='num'>{acc_badge_html(r.get('accuracy'))}</td>
</tr>""")

st.markdown(f"""
<div class="fg-wrap"><table class="fg">
<thead><tr>
  <th>Month</th><th>Type</th>
  <th class="num">Actual Spend</th><th class="num">Forecast / EOM</th>
  <th class="num">Monthly Budget</th><th class="num">Forecast vs Budget</th>
  <th class="num">Confidence Band</th><th class="num">Avg Daily Burn</th>
  <th class="num">Forecast Accuracy</th>
</tr></thead>
<tbody>{"".join(rows_html)}</tbody>
</table></div>
""", unsafe_allow_html=True)

st.markdown("---")


# ── Year-end summary ───────────────────────────────────────────────────────────
st.markdown("<div class='section-label'>📊 Year-End Summary</div>", unsafe_allow_html=True)

col_chart, col_stats = st.columns([3, 2])

with col_chart:
    wf_labels  = [r["label"] for r in rows] + ["Year-End Total"]
    wf_vals    = [(r["actual"] if r["type"]=="actual" and r["actual"] is not None else r["forecast"] or 0) for r in rows]
    wf_measure = ["relative"] * 12 + ["total"]
    wf_colors  = ["#2563eb" if r["type"]=="actual" else "#60a5fa" if r["type"]=="current" else "#a5b4fc" for r in rows] + ["#7c3aed"]

    fig4 = go.Figure(go.Waterfall(
        orientation="v", measure=wf_measure, x=wf_labels, y=wf_vals + [0],
        connector=dict(line=dict(color="#e2e8f0", width=1)),
        increasing=dict(marker=dict(color="#2563eb")),
        totals=dict(marker=dict(color="#7c3aed")),
        hovertemplate="%{x}<br>$%{y:,.0f}<extra></extra>",
    ))
    fig4.add_hline(y=annual_budget, line_dash="dot", line_color="#dc2626",
                   annotation_text=f"Annual Budget ${annual_budget/1000:.0f}K",
                   annotation_position="bottom right")
    fig4.update_layout(
        plot_bgcolor="#fff", paper_bgcolor="#fff", height=340,
        margin=dict(t=30, b=40, l=60, r=20),
        yaxis=dict(showgrid=True, gridcolor="#f1f5f9", tickfont=dict(size=10)),
        xaxis=dict(tickfont=dict(size=9)), showlegend=False,
        font=dict(family="Inter, system-ui, sans-serif"),
        title=dict(text="Month-by-Month Build-up to Year-End", font=dict(size=12, color="#1e293b")),
    )
    st.plotly_chart(fig4, use_container_width=True)

with col_stats:
    pace_note   = "On Track" if abs(over_under)/annual_budget < 0.05 else ("Over Pace" if yef_over else "Under Pace")
    pct_yr_done = round(completed_months / 12 * 100, 0)

    st.markdown(f"""
<div style="background:#fff;border-radius:10px;border:1px solid #e2e8f0;padding:18px 20px;">
  <div style="font-size:0.82rem;font-weight:700;color:#1e293b;margin-bottom:12px;">Year-End Forecast Summary</div>
  <table style="width:100%;font-size:12px;border-collapse:collapse;">
    <tr><td style="color:#64748b;padding:5px 0">Annual Budget</td>
        <td style="text-align:right;font-weight:600">${annual_budget/1000:.0f}K</td></tr>
    <tr style="border-top:1px solid #f1f5f9">
        <td style="color:#64748b;padding:5px 0">YE Forecast</td>
        <td style="text-align:right;font-weight:700;color:{'#dc2626' if yef_over else '#16a34a'}">${yef/1000:.0f}K</td></tr>
    <tr style="border-top:1px solid #f1f5f9">
        <td style="color:#64748b;padding:5px 0">Budget Variance</td>
        <td style="text-align:right;font-weight:600;color:{'#dc2626' if over_under>0 else '#16a34a'}">
          {'+' if over_under>0 else ''}${over_under/1000:.0f}K</td></tr>
    <tr style="border-top:1px solid #f1f5f9">
        <td style="color:#64748b;padding:5px 0">Run-Rate (rolling avg × 12)</td>
        <td style="text-align:right;font-weight:600">${meta['rolling_avg']*12/1000:.0f}K</td></tr>
    <tr style="border-top:1px solid #f1f5f9">
        <td style="color:#64748b;padding:5px 0">Daily Burn Rate</td>
        <td style="text-align:right;font-weight:600">${meta['current_burn']/1000:.2f}K/day</td></tr>
    <tr style="border-top:1px solid #f1f5f9">
        <td style="color:#64748b;padding:5px 0">Months Completed</td>
        <td style="text-align:right;font-weight:600">{completed_months} of 12 ({int(pct_yr_done)}%)</td></tr>
    <tr style="border-top:1px solid #f1f5f9">
        <td style="color:#64748b;padding:5px 0">Forecast Accuracy (avg)</td>
        <td style="text-align:right;font-weight:600;color:{'#16a34a' if acc_avg and acc_avg>=90 else '#ea580c' if acc_avg and acc_avg>=75 else '#94a3b8'}">
          {str(acc_avg)+'%' if acc_avg else 'N/A'}</td></tr>
    <tr style="border-top:1px solid #f1f5f9">
        <td style="color:#64748b;padding:5px 0">Pace</td>
        <td style="text-align:right;font-weight:600">{pace_note}</td></tr>
  </table>
</div>""", unsafe_allow_html=True)

    st.markdown("""
<div class="method-box" style="margin-top:12px;">
        <b>Data source — Azure_Spend_Forecast</b><br>
  <b>Table:</b> Azure_spend_Analysis · 6 columns · pre-aggregated in Fabric<br>
  <b>Actuals:</b> SUM(total_cost) · complete_month ≠ "Incomplete"<br>
  <b>Current MTD:</b> total_cost where complete_month = "Incomplete"<br>
  <b>Daily burn:</b> MTD ÷ days_with_data<br>
  <b>EOM projection:</b> MTD + burn × days remaining<br>
        <b>Forecast:</b> weighted rolling-average business rule (configurable from sidebar)<br>
        <b>Confidence band:</b> configurable base + month-out increment
</div>""", unsafe_allow_html=True)


# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="dash-footer">
  <span>{completed_months} months actual · {forecast_months} months forecast · accuracy {str(acc_avg)+'%' if acc_avg else 'N/A'}</span>
    <span>{SEMANTIC_MODEL_NAME} · Dataset: {DATASET_ID[:8]}... · Cache: 5 min · Auto-refresh: 5 min</span>
</div>
""", unsafe_allow_html=True)
