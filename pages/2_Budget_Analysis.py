import streamlit as st
import requests
import pandas as pd
import msal
from azure.identity import AzureCliCredential, ClientSecretCredential
from datetime import datetime
import math
import time
from streamlit_autorefresh import st_autorefresh

# ── Configuration ─────────────────────────────────────────────────────────────
TENANT_ID    = "e240d61e-61e3-4c9e-ab90-8644b2f4d2a9"
WORKSPACE_ID = "eca3c81e-a968-42a5-899f-d8fc1a45ebec"
DATASET_ID   = "56e6e1c3-8b70-4c53-b288-331041ce1f3f"
CLIENT_ID    = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
AUTHORITY    = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES       = ["https://analysis.windows.net/powerbi/api/.default"]
TENANT_NAME  = "MedInsight Production · Engineering · Milliman"

st_autorefresh(interval=300000)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
#MainMenu, footer, [data-testid="stToolbar"] { display:none !important; }
section[data-testid="stSidebar"] { background-color:#1a2744 !important; transform:translateX(0px) !important; display:block !important; visibility:visible !important; min-width:260px !important; }
[data-testid="stSidebarCollapseButton"] { display:none !important; }
[data-testid="collapsedControl"] { display:none !important; }

.top-banner {
    background:linear-gradient(135deg,#eff6ff 0%,#dbeafe 100%);
    border-radius:12px; padding:22px 28px 18px 28px; margin-bottom:20px;
    border:1px solid #bfdbfe;
}
.top-banner .dash-title { font-size:1.55rem; font-weight:700; color:#1e3a8a; line-height:1.3; }
.top-banner .dash-title span { color:#2563eb; }
.top-banner .dash-meta { display:flex; gap:18px; flex-wrap:wrap; margin-top:6px; }
.top-banner .dash-meta .m { font-size:0.73rem; color:#64748b; }
.top-banner .dash-meta .m::before { content:"● "; color:#2563eb; }

.kpi-card {
    background:#ffffff; border-radius:10px;
    padding:16px 18px; border-top:4px solid #2563eb;
    border-left:1px solid #e2e8f0; border-right:1px solid #e2e8f0; border-bottom:1px solid #e2e8f0;
    box-shadow:0 1px 4px rgba(0,0,0,0.06);
}
.kpi-card.red   { border-top-color:#dc2626; }
.kpi-card.green { border-top-color:#16a34a; }
.kpi-card.ora   { border-top-color:#ea580c; }
.kpi-lbl  { font-size:0.7rem; font-weight:700; color:#64748b; text-transform:uppercase; letter-spacing:.06em; margin-bottom:5px; }
.kpi-val  { font-size:2rem; font-weight:700; color:#0f172a; line-height:1.1; }
.kpi-val.red  { color:#dc2626; }
.kpi-val.grn  { color:#16a34a; }
.kpi-val.ora  { color:#ea580c; }
.kpi-val.blu  { color:#2563eb; }
.kpi-sub  { font-size:0.71rem; color:#64748b; margin-top:3px; }

.mb-wrap { margin:16px 0 6px 0; }
.mb-lbl  { display:flex; justify-content:space-between; font-size:0.72rem; color:#64748b; margin-bottom:5px; }
.mb-track { height:8px; background:#e2e8f0; border-radius:4px; position:relative; overflow:visible; }
.mb-day   { height:100%; border-radius:4px; background:#bfdbfe; position:absolute; top:0; left:0; }
.mb-spend { height:100%; border-radius:4px; background:#2563eb; opacity:.85; position:absolute; top:0; left:0; }
.mb-proj  { position:absolute; top:-3px; height:14px; width:2px; background:#ea580c; border-radius:1px; }

.spill-row { display:flex; gap:8px; flex-wrap:wrap; margin:10px 0 4px 0; }
.spill {
    display:inline-flex; align-items:center; gap:6px;
    background:#ffffff; border:1px solid #e2e8f0; border-radius:20px;
    padding:5px 13px; font-size:12px; color:#374151;
}
.dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
.sc-num { font-weight:700; font-size:14px; }

.section-label {
    font-size:0.95rem; font-weight:700; color:#1e293b;
    margin:18px 0 10px 0; padding-bottom:6px;
    border-bottom:2px solid #e2e8f0;
}

.stDownloadButton > button {
    background:#2563eb !important; color:#fff !important;
    border:none !important; border-radius:6px !important;
    font-size:0.78rem !important; padding:7px 18px !important; font-weight:600 !important;
}
.stDownloadButton > button:hover { background:#1d4ed8 !important; }

div[data-testid="stSegmentedControl"] { gap:0 !important; }
div[data-testid="stSegmentedControl"] > label { display:none !important; }
div[data-testid="stSegmentedControl"] button {
    border-radius:20px !important;
    font-size:0.78rem !important; font-weight:600 !important;
    padding:5px 18px !important;
    border:1.5px solid #e2e8f0 !important;
    background:#f8fafc !important; color:#475569 !important;
    margin:0 3px !important;
}
div[data-testid="stSegmentedControl"] button[aria-checked="true"] {
    background:#2563eb !important; border-color:#2563eb !important; color:#fff !important;
}
div[data-testid="stSegmentedControl"] button:hover {
    border-color:#93c5fd !important; color:#2563eb !important;
}

.bgt-wrap { overflow-x:auto; margin-top:8px; border-radius:8px; border:1px solid #e2e8f0; }
table.bgt { width:100%; border-collapse:collapse; font-size:12px; }
table.bgt thead tr { background:#f8fafc; border-bottom:2px solid #e2e8f0; }
table.bgt th { padding:9px 11px; text-align:left; font-size:11px; font-weight:600;
               text-transform:uppercase; letter-spacing:.05em; color:#64748b; white-space:nowrap; }
table.bgt th.num { text-align:right; }
table.bgt td { padding:7px 11px; border-bottom:1px solid #f1f5f9; vertical-align:middle; color:#0f172a; }
table.bgt td.num { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
table.bgt tr.row-over td { background:#fef2f2; }
table.bgt tr.row-watch td { background:#fff7ed; }
table.bgt tr:hover td { background:#f8fafc; }

.sn  { font-weight:600; color:#0f172a; }
.sf  { font-size:10px; color:#64748b; margin-top:1px; }
.stn { font-size:10px; color:#2563eb; margin-top:2px; }
.bn  { font-size:11px; color:#374151; font-family:monospace; background:#f1f5f9;
       padding:2px 6px; border-radius:4px; white-space:nowrap; }

.bw  { min-width:150px; }
.bt  { height:10px; background:#e2e8f0; border-radius:5px; position:relative; overflow:visible; margin-bottom:3px; }
.bpj { height:100%; border-radius:5px; position:absolute; top:0; left:0; }
.bfl { height:100%; border-radius:5px; position:absolute; top:0; left:0; min-width:2px; }
.bl  { position:absolute; top:-3px; height:16px; width:2px; border-radius:1px; z-index:3; }
.bb  { background:#94a3b8; }
.ba1 { background:#ea580c; }
.ba2 { background:#dc2626; }
.blbl { display:flex; justify-content:space-between; font-size:10px; color:#64748b; }

.ac  { line-height:1.55; }
.ap  { font-size:12px; font-weight:600; white-space:nowrap; }
.aa  { font-size:11px; color:#64748b; font-weight:400; }
.ag  { font-size:11px; }
.pos { color:#16a34a; } .neg { color:#dc2626; } .dys { color:#64748b; font-size:10px; margin-left:3px; }

.proj-over { color:#ea580c; font-weight:600; }
.proj-tag  { font-size:10px; color:#dc2626; margin-left:3px; }
.proj-ok   { color:#0f172a; }
.na        { color:#94a3b8; }
.ow        { font-size:11px; color:#64748b; line-height:1.7; white-space:nowrap; }

.badge { display:inline-flex; align-items:center; padding:3px 8px; border-radius:20px;
         font-size:10px; font-weight:700; letter-spacing:.04em; text-transform:uppercase; white-space:nowrap; }
.badge-over  { background:#fee2e2; color:#dc2626; border:1px solid #fca5a5; }
.badge-crit  { background:#ffedd5; color:#ea580c; border:1px solid #fdba74; }
.badge-warn  { background:#fef9c3; color:#ca8a04; border:1px solid #fde047; }
.badge-watch { background:#fff7ed; color:#c2410c; border:1px solid #fed7aa; }
.badge-ok    { background:#dcfce7; color:#16a34a; border:1px solid #86efac; }

.dash-footer {
    font-size:0.7rem; color:#94a3b8;
    margin-top:24px; padding-top:10px;
    border-top:1px solid #e2e8f0;
    display:flex; justify-content:space-between;
}

/* ── Burn Driver section styles ─────────────────────────────────────────── */
.driver-card {
    background:#fff; border-radius:10px; border:1px solid #e2e8f0;
    padding:16px 18px; margin-bottom:12px;
    box-shadow:0 1px 3px rgba(0,0,0,0.05);
}
.driver-card-title {
    font-size:0.82rem; font-weight:700; color:#1e293b;
    margin-bottom:12px; display:flex; align-items:center; gap:8px;
}
.driver-sub-name { font-size:0.78rem; font-weight:700; color:#1e3a8a; margin-bottom:2px; }
.driver-sub-meta { font-size:0.68rem; color:#64748b; margin-bottom:8px; }

/* ServiceFamily breakdown bar */
.sf-bar-wrap { margin-bottom:6px; }
.sf-bar-label { display:flex; justify-content:space-between; font-size:0.7rem; color:#374151; margin-bottom:3px; }
.sf-bar-track { height:7px; background:#f1f5f9; border-radius:4px; overflow:hidden; }
.sf-bar-fill  { height:100%; border-radius:4px; }

/* Trend pill */
.trend-up   { display:inline-block; background:#fef2f2; color:#dc2626; border:1px solid #fca5a5;
              border-radius:20px; padding:2px 9px; font-size:10px; font-weight:700; }
.trend-dn   { display:inline-block; background:#dcfce7; color:#16a34a; border:1px solid #86efac;
              border-radius:20px; padding:2px 9px; font-size:10px; font-weight:700; }
.trend-flat { display:inline-block; background:#f1f5f9; color:#64748b; border:1px solid #e2e8f0;
              border-radius:20px; padding:2px 9px; font-size:10px; font-weight:700; }
.accel-warn { display:inline-block; background:#fff7ed; color:#c2410c; border:1px solid #fed7aa;
              border-radius:20px; padding:2px 9px; font-size:10px; font-weight:700; margin-left:4px; }

/* Recommendation cards */
.rec-card {
    border-radius:8px; padding:13px 16px; margin-bottom:9px;
    border-left:4px solid #e2e8f0;
}
.rec-immediate { border-left-color:#dc2626; background:#fef2f2; }
.rec-urgent    { border-left-color:#ea580c; background:#fff7ed; }
.rec-high      { border-left-color:#eab308; background:#fefce8; }
.rec-medium    { border-left-color:#3b82f6; background:#eff6ff; }
.rec-review    { border-left-color:#94a3b8; background:#f8fafc; }
.rec-priority  { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.06em; margin-bottom:4px; }
.rec-title     { font-size:0.8rem; font-weight:700; color:#0f172a; margin-bottom:3px; }
.rec-body      { font-size:0.73rem; color:#374151; line-height:1.55; }
.rec-driver    { font-size:0.7rem; color:#64748b; margin-top:5px; font-style:italic; }
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
            f"Authentication failed. Either configure **[azure]** secrets in Streamlit Cloud, "
            f"or run `az login --tenant {TENANT_ID}` locally. Error: {e}"
        )
        st.stop()


def strip_prefix(col):
    return col.split("[")[-1].rstrip("]") if "[" in col else col


def _pbi_query(token, dax):
    url  = (
        f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}"
        f"/datasets/{DATASET_ID}/executeQueries"
    )
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"queries": [{"query": dax}], "serializerSettings": {"includeNulls": True}},
        timeout=30,
    )
    if resp.status_code == 401:
        st.error(f"Power BI API 401 — {resp.text}")
        st.stop()
    resp.raise_for_status()
    rows = resp.json()["results"][0]["tables"][0].get("rows", [])
    if not rows:
        return pd.DataFrame()
    df         = pd.DataFrame(rows)
    df.columns = [strip_prefix(c) for c in df.columns]
    return df


@st.cache_data(ttl=300)
def fetch_budget_data(token):
    t0      = time.time()
    df      = _pbi_query(token, "EVALUATE BudgetData")
    elapsed = round(time.time() - t0, 1)
    return df, elapsed


@st.cache_data(ttl=300)
def fetch_service_data(token):
    """Fetch SpendByService table — returns empty DataFrame if table not yet available."""
    try:
        df = _pbi_query(token, "EVALUATE SpendByService")
        if not df.empty:
            df["cost"]      = pd.to_numeric(df.get("cost", 0),      errors="coerce").fillna(0)
            df["usageDate"] = pd.to_datetime(df.get("usageDate", pd.NaT), errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()


# ── Load & normalise BudgetData ───────────────────────────────────────────────
token        = get_token()
df, elapsed  = fetch_budget_data(token)

if df.empty:
    st.warning("No data returned from the Semantic Model. Run BudgetAnalyzer.py in Fabric first.")
    st.stop()

numeric_cols = ["budgetAmount", "actualSpend", "pctUsed", "remainingUSD",
                "dailyBurnRate", "projectedEOM", "daysRemaining",
                "alert1Pct", "alert1Threshold", "alert1GapUSD", "alert1DaysAway",
                "alert2Pct", "alert2Threshold", "alert2GapUSD", "alert2DaysAway"]
for c in numeric_cols:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

def _display_status(row):
    s = str(row.get("status", "OK"))
    if s == "OK" and pd.notna(row.get("projectedEOM")) and pd.notna(row.get("budgetAmount")):
        if row["projectedEOM"] > row["budgetAmount"]:
            return "WATCH"
    return s

df["_displayStatus"] = df.apply(_display_status, axis=1)
df = df.sort_values("pctUsed", ascending=False).reset_index(drop=True)

# ── KPI totals ────────────────────────────────────────────────────────────────
total_budget  = df["budgetAmount"].sum()
total_actual  = df["actualSpend"].sum()
total_burn    = df["dailyBurnRate"].sum()
total_proj    = df["projectedEOM"].sum()
pct_used      = round(total_actual / total_budget * 100, 1) if total_budget > 0 else 0
proj_pct      = round(total_proj   / total_budget * 100, 1) if total_budget > 0 else 0

n_over  = int((df["_displayStatus"] == "OVER BUDGET").sum())
n_crit  = int((df["_displayStatus"] == "CRITICAL").sum())
n_warn  = int((df["_displayStatus"] == "WARNING").sum())
n_watch = int((df["_displayStatus"] == "WATCH").sum())
n_ok    = int((df["_displayStatus"] == "OK").sum())

days_remaining = int(df["daysRemaining"].dropna().iloc[0]) if not df["daysRemaining"].dropna().empty else 0
today          = datetime.now()
days_in_month  = 28 + (2 if today.month in (1,3,5,7,8,10,12) else (1 if today.month != 2 else 0))
try:
    from calendar import monthrange
    days_in_month = monthrange(today.year, today.month)[1]
except Exception:
    pass
day_num = today.day
day_pct = round(day_num / days_in_month * 100, 0)

user_email = st.session_state.get("user_email", "anmol.sharma@milliman.com")
generated  = datetime.now().strftime("%Y-%m-%d %H:%M")

# ── Banner ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="top-banner">
  <div class="dash-title">Azure Budget Analysis &mdash; <span>MedInsight</span></div>
  <div class="dash-meta">
    <span class="m">{TENANT_NAME}</span>
    <span class="m">{user_email}</span>
    <span class="m">Generated: {generated}</span>
    <span class="m">Day {day_num} of {days_in_month} &nbsp;({days_remaining} days remaining)</span>
    <span class="m">Query: {elapsed}s &nbsp;|&nbsp; Auto-refreshes every 5 min</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── KPI Cards ─────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-lbl">Total Budget (MTD)</div>
        <div class="kpi-val blu">${total_budget/1000:.1f}K</div>
        <div class="kpi-sub">{len(df)} budget entries</div>
    </div>""", unsafe_allow_html=True)
with k2:
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-lbl">Actual Spend MTD</div>
        <div class="kpi-val">${total_actual/1000:.1f}K</div>
        <div class="kpi-sub">{pct_used}% of total budget</div>
    </div>""", unsafe_allow_html=True)
with k3:
    st.markdown(f"""<div class="kpi-card ora">
        <div class="kpi-lbl">Daily Burn Rate</div>
        <div class="kpi-val ora">${total_burn/1000:.2f}K/day</div>
        <div class="kpi-sub">across all subscriptions</div>
    </div>""", unsafe_allow_html=True)
with k4:
    proj_class = "red" if proj_pct > 100 else "grn"
    st.markdown(f"""<div class="kpi-card {'red' if proj_pct > 100 else 'green'}">
        <div class="kpi-lbl">Projected Month-End</div>
        <div class="kpi-val {proj_class}">${total_proj/1000:.1f}K</div>
        <div class="kpi-sub">{proj_pct}% of total budget</div>
    </div>""", unsafe_allow_html=True)
with k5:
    st.markdown(f"""<div class="kpi-card red">
        <div class="kpi-lbl">Status Summary</div>
        <div class="kpi-val red">{n_over} <span style="font-size:13px;color:#64748b">over budget</span></div>
        <div class="kpi-sub">{n_watch} watch &nbsp;&middot;&nbsp; {n_ok} ok</div>
    </div>""", unsafe_allow_html=True)

# ── Month Progress Bar ────────────────────────────────────────────────────────
spend_pct = min(pct_used, 100)
proj_left = min(proj_pct, 99)
st.markdown(f"""
<div class="mb-wrap">
  <div class="mb-lbl">
    <span>Day 1</span>
    <span style="color:#374151">Today: Day {day_num} ({int(day_pct)}%)</span>
    <span>Spend: {pct_used}%</span>
    <span style="color:#f97316">Projected EOM: {proj_pct}%</span>
    <span>Day {days_in_month}</span>
  </div>
  <div class="mb-track">
    <div class="mb-day"   style="width:{day_pct}%"></div>
    <div class="mb-spend" style="width:{spend_pct}%"></div>
    <div class="mb-proj"  style="left:{proj_left}%" title="Projected EOM: {proj_pct}%"></div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Summary pills ─────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="spill-row">
  <div class="spill"><div class="dot" style="background:#ef4444"></div><span class="sc-num">{n_over}</span>Over Budget</div>
  <div class="spill"><div class="dot" style="background:#f97316"></div><span class="sc-num">{n_crit}</span>Critical</div>
  <div class="spill"><div class="dot" style="background:#eab308"></div><span class="sc-num">{n_warn}</span>Warning</div>
  <div class="spill"><div class="dot" style="background:#fb923c"></div><span class="sc-num">{n_watch}</span>Watch (projected to exceed)</div>
  <div class="spill"><div class="dot" style="background:#22c55e"></div><span class="sc-num">{n_ok}</span>OK</div>
  <div class="spill" style="margin-left:auto"><div class="dot" style="background:#94a3b8"></div>Budget line</div>
  <div class="spill"><div class="dot" style="background:#f97316"></div>Alert 1</div>
  <div class="spill"><div class="dot" style="background:#ef4444"></div>Alert 2</div>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ── Filter bar ────────────────────────────────────────────────────────────────
fc1, fc2 = st.columns([4, 8])
with fc1:
    st.caption("FILTER BY STATUS")
    status_filter = st.segmented_control(
        "", ["All", "OVER BUDGET", "CRITICAL", "WARNING", "WATCH", "OK"],
        default="All", label_visibility="collapsed", key="status_seg"
    )
    if status_filter is None:
        status_filter = "All"
with fc2:
    st.caption("SEARCH SUBSCRIPTION")
    search = st.text_input("", placeholder="Type to search...", label_visibility="collapsed", key="search_box")

# ── Apply filters ─────────────────────────────────────────────────────────────
filtered = df.copy()
if status_filter != "All":
    filtered = filtered[filtered["_displayStatus"] == status_filter]
if search.strip():
    q = search.strip().lower()
    filtered = filtered[
        filtered["subscription"].str.lower().str.contains(q, na=False) |
        filtered.get("tenantName", pd.Series(dtype=str)).str.lower().str.contains(q, na=False)
    ]

# ── Export & count ────────────────────────────────────────────────────────────
exp_col, cnt_col = st.columns([2, 10])
with exp_col:
    csv_bytes = filtered.drop(columns=["_displayStatus"], errors="ignore").to_csv(index=False).encode()
    st.download_button("⬇ Export CSV", csv_bytes, "BudgetAnalysis_filtered.csv", "text/csv", key="dl_csv")
with cnt_col:
    st.markdown(
        f'<div style="padding-top:8px;color:#64748b;font-size:12px;">Showing {len(filtered)} of {len(df)} budget entries</div>',
        unsafe_allow_html=True
    )


# ── Build HTML table (unchanged) ──────────────────────────────────────────────
def badge_html(status):
    cls = {"OVER BUDGET": "badge-over", "CRITICAL": "badge-crit",
           "WARNING": "badge-warn", "WATCH": "badge-watch"}.get(status, "badge-ok")
    return f"<span class='badge {cls}'>{status}</span>"


def bar_color(pct):
    if pct >= 100: return "#ef4444"
    if pct >= 85:  return "#f97316"
    if pct >= 70:  return "#eab308"
    if pct >= 50:  return "#3b82f6"
    return "#22c55e"


def row_class(status):
    return {"OVER BUDGET": "row-over", "WATCH": "row-watch"}.get(status, "")


def fmt_gap(gap, days):
    if gap is None or math.isnan(gap):
        return ""
    g_html = (f"<span class='neg'>${int(abs(gap))} over</span>"
              if gap < 0 else f"<span class='pos'>${int(gap)} left</span>")
    if days is None or math.isnan(days):
        d_html = "<span class='neg'>Crossed</span>" if gap < 0 else ""
    elif days <= 0:
        d_html = "<span class='neg'>Crossed</span>"
    else:
        d_html = f"<span class='dys'>in {int(days)}d</span>"
    return f"{g_html} {d_html}"


rows_html = []
for _, r in filtered.iterrows():
    sub       = str(r.get("subscription", "")).replace("MedInsight - ", "")
    full_sub  = str(r.get("subscription", ""))
    tenant    = str(r.get("tenantName", "") or "")
    bname     = str(r.get("budgetName", "") or "")
    budget    = r.get("budgetAmount", 0) or 0
    actual    = r.get("actualSpend", 0)  or 0
    pct       = r.get("pctUsed", 0)      or 0
    burn      = r.get("dailyBurnRate", 0) or 0
    proj      = r.get("projectedEOM", 0)  or 0
    rem       = r.get("remainingUSD", 0)  or 0
    status    = str(r.get("_displayStatus", "OK"))

    a1pct  = r.get("alert1Pct")
    a1amt  = r.get("alert1Threshold")
    a1gap  = r.get("alert1GapUSD")
    a1days = r.get("alert1DaysAway")
    a2pct  = r.get("alert2Pct")
    a2amt  = r.get("alert2Threshold")
    a2gap  = r.get("alert2GapUSD")
    a2days = r.get("alert2DaysAway")
    owners = [o.strip() for o in str(r.get("alert1Recipients", "") or "").split(";") if o.strip()]

    bc      = bar_color(pct)
    proj_bg = "rgba(239,68,68,0.22)" if proj > budget else "rgba(59,130,246,0.15)"
    bar_max = float(a2amt) if (a2amt and not math.isnan(a2amt)) else budget * 2.2
    bar_max = max(bar_max, actual * 1.05) if actual > 0 else max(bar_max, 1)
    act_w   = min(round(actual / bar_max * 100, 1), 100)
    prj_w   = min(round(proj   / bar_max * 100, 1), 100)
    bud_ln  = round(budget / bar_max * 100, 1)
    a1_ln   = (min(round(float(a1amt) / bar_max * 100, 1), 99)
               if (a1amt and not math.isnan(a1amt)) else None)
    a2_ln   = (min(round(float(a2amt) / bar_max * 100, 1), 99)
               if (a2amt and not math.isnan(a2amt)) else None)

    markers = f"<div class='bl bb' style='left:{bud_ln}%' title='Budget: ${int(budget)}'></div>"
    if a1_ln is not None:
        markers += f"<div class='bl ba1' style='left:{a1_ln}%' title='Alert 1: ${int(a1amt)}'></div>"
    if a2_ln is not None:
        markers += f"<div class='bl ba2' style='left:{a2_ln}%' title='Alert 2: ${int(a2amt)}'></div>"

    bar_html = f"""<div class='bw'>
  <div class='bt'>
    <div class='bpj' style='width:{prj_w}%;background:{proj_bg}'></div>
    <div class='bfl' style='width:{act_w}%;background:{bc}'></div>
    {markers}
  </div>
  <div class='blbl'><span style='color:{bc};font-weight:600'>{pct}%</span><span>${int(bar_max)}</span></div>
</div>"""

    if a1pct and not math.isnan(a1pct):
        a1_cell = f"<div class='ac'><div class='ap'>{int(a1pct)}% <span class='aa'>(${int(a1amt or 0)})</span></div><div class='ag'>{fmt_gap(a1gap, a1days)}</div></div>"
    else:
        a1_cell = "<span class='na'>No alerts set</span>"

    if a2pct and not math.isnan(a2pct):
        a2_cell = f"<div class='ac'><div class='ap'>{int(a2pct)}% <span class='aa'>(${int(a2amt or 0)})</span></div><div class='ag'>{fmt_gap(a2gap, a2days)}</div></div>"
    else:
        a2_cell = "<span class='na'>No alerts set</span>"

    if proj > budget:
        proj_cell = f"<span class='proj-over'>${int(proj)}</span> <span class='proj-tag'>+${int(proj-budget)} over</span>"
    else:
        proj_cell = f"<span class='proj-ok'>${int(proj)}</span>"

    rem_cell   = (f"<span class='neg'>${int(abs(rem))} deficit</span>"
                  if rem < 0 else f"<span class='pos'>${int(rem)}</span>")
    owner_html = "".join(f"<div class='ow'>{o}</div>" for o in owners) if owners else "<span class='na'>—</span>"
    tenant_div = f"<div class='stn'>{tenant}</div>" if tenant else ""
    sub_cell   = f"<div class='sn'>{sub}</div><div class='sf'>{full_sub}</div>{tenant_div}"

    rc = row_class(status)
    rows_html.append(f"""<tr class='{rc}'>
  <td>{sub_cell}</td>
  <td><span class='bn'>{bname}</span></td>
  <td class='num'>${int(budget)}</td>
  <td class='num'>${int(actual)}</td>
  <td>{bar_html}</td>
  <td class='num'><b style='color:{bc}'>{pct}%</b></td>
  <td class='num'>${int(burn)}/d</td>
  <td class='num'>{proj_cell}</td>
  <td>{a1_cell}</td>
  <td>{a2_cell}</td>
  <td class='num'>{rem_cell}</td>
  <td>{badge_html(status)}</td>
  <td>{owner_html}</td>
</tr>""")

table_html = f"""
<div class="bgt-wrap">
<table class="bgt">
<thead><tr>
  <th>Subscription</th>
  <th>Budget Name</th>
  <th class="num">Budget (USD)</th>
  <th class="num">Actual MTD</th>
  <th>Progress</th>
  <th class="num">% Used</th>
  <th class="num">Daily Burn</th>
  <th class="num">Projected EOM</th>
  <th>Alert 1</th>
  <th>Alert 2</th>
  <th class="num">Remaining</th>
  <th>Status</th>
  <th>Owner (Alert 1)</th>
</tr></thead>
<tbody>
{"".join(rows_html)}
</tbody>
</table>
</div>
"""
st.markdown(table_html, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# ── BURN RATE DRIVERS & RECOMMENDATIONS (new section) ─────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("---")
st.markdown("<div class='section-label'>🔍 Burn Rate Drivers &amp; Recommendations</div>", unsafe_allow_html=True)

svc_df = fetch_service_data(token)

if svc_df.empty:
    st.info(
        "Service breakdown data is not yet available. "
        "Run **FABRIC_BudgetAnalyzer_v2** in Fabric to populate the SpendByService table, "
        "then refresh this page."
    )
else:
    # ── Compute trend metrics from daily rows ──────────────────────────────────
    # Split into two windows relative to today.
    # curr_window = last 30 days (or all available data if sub has < 30 days of rows)
    # prev_window = prior 30 days (days 31-60)
    from datetime import timedelta as _td
    today_dt   = pd.Timestamp.now(tz="UTC").normalize().tz_localize(None)
    cutoff_30  = today_dt - _td(days=30)
    cutoff_60  = today_dt - _td(days=60)

    svc_df["usageDate"] = pd.to_datetime(svc_df["usageDate"], errors="coerce").dt.tz_localize(None)

    # Use the full 60-day dataset as curr_window so subscriptions whose spend
    # dates fall between day 31-60 (e.g. older data, low-frequency billing) are
    # still included. prev_window uses only days 31-60 for trend comparison.
    curr_window = svc_df[svc_df["usageDate"] >= cutoff_60].copy()   # all 60 days
    prev_window = svc_df[(svc_df["usageDate"] >= cutoff_60) & (svc_df["usageDate"] < cutoff_30)].copy()  # days 31-60

    # Per subscription + serviceFamily aggregates
    curr_sf = curr_window.groupby(["subscription", "serviceFamily"])["cost"].sum().reset_index(name="curr30")
    prev_sf = prev_window.groupby(["subscription", "serviceFamily"])["cost"].sum().reset_index(name="prev30")
    sf_trend = pd.merge(curr_sf, prev_sf, on=["subscription", "serviceFamily"], how="left").fillna(0)

    # % change 30d vs prev 30d
    sf_trend["chg30"] = sf_trend.apply(
        lambda r: round((r["curr30"] - r["prev30"]) / r["prev30"] * 100, 1) if r["prev30"] > 0 else None,
        axis=1
    )

    # 7-day rolling average vs 60-day average (acceleration signal)
    cutoff_7 = today_dt - _td(days=7)
    last7  = svc_df[svc_df["usageDate"] >= cutoff_7].groupby(["subscription", "serviceFamily"])["cost"].mean().reset_index(name="avg7d")
    last30 = curr_window.groupby(["subscription", "serviceFamily"])["cost"].mean().reset_index(name="avg30d")
    accel  = pd.merge(last7, last30, on=["subscription", "serviceFamily"], how="left").fillna(0)
    accel["accelPct"] = accel.apply(
        lambda r: round((r["avg7d"] - r["avg30d"]) / r["avg30d"] * 100, 1) if r["avg30d"] > 0 else None,
        axis=1
    )

    # Merge everything together
    sf_full = sf_trend.merge(accel[["subscription", "serviceFamily", "avg7d", "avg30d", "accelPct"]],
                              on=["subscription", "serviceFamily"], how="left")

    # Per subscription + serviceFamily + meterCategory for drill-down
    curr_mc = curr_window.groupby(["subscription", "serviceFamily", "meterCategory"])["cost"].sum().reset_index(name="curr30")
    prev_mc = prev_window.groupby(["subscription", "serviceFamily", "meterCategory"])["cost"].sum().reset_index(name="prev30")
    mc_trend = pd.merge(curr_mc, prev_mc, on=["subscription", "serviceFamily", "meterCategory"], how="left").fillna(0)
    mc_trend["chg30"] = mc_trend.apply(
        lambda r: round((r["curr30"] - r["prev30"]) / r["prev30"] * 100, 1) if r["prev30"] > 0 else None,
        axis=1
    )

    # Service family colour palette (deterministic)
    SF_COLORS = [
        "#2563eb", "#ea580c", "#16a34a", "#9333ea", "#0891b2",
        "#dc2626", "#ca8a04", "#0d9488", "#db2777", "#64748b",
    ]

    def sf_color(i):
        return SF_COLORS[i % len(SF_COLORS)]

    def trend_pill(pct):
        if pct is None:
            return "<span class='trend-flat'>N/A</span>"
        arrow = "▲" if pct > 0 else "▼"
        if pct > 5:
            return f"<span class='trend-up'>{arrow} {abs(pct):.1f}%</span>"
        if pct < -5:
            return f"<span class='trend-dn'>{arrow} {abs(pct):.1f}%</span>"
        return f"<span class='trend-flat'>≈ {pct:+.1f}%</span>"

    def accel_pill(pct):
        if pct is None or abs(pct) <= 10:
            return ""
        arrow = "▲" if pct > 0 else "▼"
        return f"<span class='accel-warn'>7d avg {arrow}{abs(pct):.0f}% vs 60d</span>"

    # ── Section tabs: Drivers | Recommendations ────────────────────────────────
    tab_drivers, tab_recs = st.tabs(["📊 Burn Rate Drivers", "💡 Recommendations"])

    # ── TAB 1: Burn Rate Drivers ───────────────────────────────────────────────
    with tab_drivers:
        # Union of BudgetData + SpendByService subscriptions, sorted.
        # BudgetData only contains subs with a budget configured.
        # SpendByService contains subs with actual spend in the last 60 days.
        # A sub may appear in SpendByService but not BudgetData (no budget set up),
        # so we combine both to ensure nothing is hidden from the selector.
        budget_subs_set = set(df["subscription"].tolist())
        svc_subs_set    = set(sf_full["subscription"].unique())
        all_budget_subs = sorted(budget_subs_set | svc_subs_set)

        # Default: top 5 by actual spend that have service breakdown data.
        # Keeping default small so the view isn't overwhelming — user can search and add more.
        top_spenders = df[df["subscription"].isin(svc_subs_set)].nlargest(5, "actualSpend")["subscription"].tolist()
        default_sel  = top_spenders

        st.caption("SELECT SUBSCRIPTIONS TO ANALYSE")
        selected_subs = st.multiselect(
            "", all_budget_subs,
            default=default_sel,
            label_visibility="collapsed",
            key="driver_sub_sel"
        )

        # Drill-down toggle
        show_meter = st.toggle("Show MeterCategory drill-down", value=False, key="show_meter_toggle")

        if not selected_subs:
            st.info("Select at least one subscription above.")
        else:
            for sub_name in selected_subs:
                sub_row = df[df["subscription"] == sub_name]
                # Sub may have spend data but no budget configured — still show the card
                if sub_row.empty:
                    budget_amt  = 0
                    actual_amt  = 0
                    burn_rate   = 0
                    remaining   = 0
                    status      = "NO BUDGET"
                else:
                    r           = sub_row.iloc[0]
                    budget_amt  = r.get("budgetAmount", 0) or 0
                    actual_amt  = r.get("actualSpend",  0) or 0
                    burn_rate   = r.get("dailyBurnRate", 0) or 0
                    remaining   = r.get("remainingUSD",  0) or 0
                    status      = str(r.get("_displayStatus", "OK"))
                sub_display = sub_name.replace("MedInsight - ", "")

                sub_sf = sf_full[sf_full["subscription"] == sub_name].sort_values("curr30", ascending=False)
                if sub_sf.empty:
                    # Sub exists in BudgetData but has no spend in SpendByService
                    st.markdown(f"""
<div class="driver-card">
  <div class="driver-sub-name">{sub_display} &nbsp;<span style="font-size:10px;font-weight:400;color:#64748b">{status}</span></div>
  <div class="driver-sub-meta">Budget: ${budget_amt:,.0f} &nbsp;·&nbsp; Actual MTD: ${actual_amt:,.0f} &nbsp;·&nbsp; Burn: ${burn_rate:,.0f}/day</div>
  <div style="font-size:0.75rem;color:#94a3b8;margin-top:6px;">No spend recorded in the last 60 days — no service breakdown available.</div>
</div>""", unsafe_allow_html=True)
                    continue

                total_curr30 = sub_sf["curr30"].sum()

                # Build ServiceFamily breakdown bars + trend pills
                sf_bars_html = ""
                for i, (_, sfr) in enumerate(sub_sf.iterrows()):
                    share    = round(sfr["curr30"] / total_curr30 * 100, 1) if total_curr30 > 0 else 0
                    color    = sf_color(i)
                    t_pill   = trend_pill(sfr.get("chg30"))
                    a_pill   = accel_pill(sfr.get("accelPct"))
                    sf_bars_html += f"""
<div class="sf-bar-wrap">
  <div class="sf-bar-label">
    <span style="font-weight:600">{sfr['serviceFamily']}</span>
    <span>${sfr['curr30']:,.0f} &nbsp;({share}%) &nbsp;{t_pill}{a_pill}</span>
  </div>
  <div class="sf-bar-track">
    <div class="sf-bar-fill" style="width:{share}%;background:{color}"></div>
  </div>
</div>"""

                # MeterCategory drill-down (if toggled on)
                mc_html = ""
                if show_meter:
                    sub_mc = mc_trend[mc_trend["subscription"] == sub_name].sort_values("curr30", ascending=False)
                    if not sub_mc.empty:
                        mc_html = "<div style='margin-top:12px;padding-top:10px;border-top:1px solid #f1f5f9'>"
                        mc_html += "<div style='font-size:0.72rem;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px'>MeterCategory Drill-down</div>"
                        mc_total = sub_mc["curr30"].sum()
                        for _, mcr in sub_mc.iterrows():
                            mc_share = round(mcr["curr30"] / mc_total * 100, 1) if mc_total > 0 else 0
                            mc_pill  = trend_pill(mcr.get("chg30"))
                            mc_html += f"""
<div class="sf-bar-wrap">
  <div class="sf-bar-label">
    <span style="color:#475569">{mcr['serviceFamily']} &rsaquo; {mcr['meterCategory']}</span>
    <span>${mcr['curr30']:,.0f} &nbsp;({mc_share}%) &nbsp;{mc_pill}</span>
  </div>
  <div class="sf-bar-track">
    <div class="sf-bar-fill" style="width:{mc_share}%;background:#94a3b8"></div>
  </div>
</div>"""
                        mc_html += "</div>"

                st.markdown(f"""
<div class="driver-card">
  <div class="driver-sub-name">{sub_display} &nbsp;<span style="font-size:10px;font-weight:400;color:#64748b">{status}</span></div>
  <div class="driver-sub-meta">
    Budget: ${budget_amt:,.0f} &nbsp;·&nbsp;
    Actual MTD: ${actual_amt:,.0f} &nbsp;·&nbsp;
    Burn: ${burn_rate:,.0f}/day &nbsp;·&nbsp;
    Remaining: ${remaining:,.0f}
  </div>
  <div class="driver-card-title">ServiceFamily breakdown — last 30 days &nbsp;
    <span style="font-size:10px;font-weight:400;color:#94a3b8">(trend = vs prior 30 days)</span>
  </div>
  {sf_bars_html}
  {mc_html}
</div>
""", unsafe_allow_html=True)

    # ── TAB 2: Recommendations ─────────────────────────────────────────────────
    with tab_recs:
        st.caption("Prioritised, logic-driven recommendations based on burn rate, service family trends, and budget status.")

        rec_items = []   # list of (sort_order, html)

        for _, r in df.iterrows():
            sub_name    = str(r.get("subscription", ""))
            sub_display = sub_name.replace("MedInsight - ", "")
            status      = str(r.get("_displayStatus", "OK"))
            budget_amt  = float(r.get("budgetAmount",  0) or 0)
            actual_amt  = float(r.get("actualSpend",   0) or 0)
            burn_rate   = float(r.get("dailyBurnRate", 0) or 0)
            remaining   = float(r.get("remainingUSD",  0) or 0)
            days_rem    = float(r.get("daysRemaining", 0) or 0)
            proj_eom    = float(r.get("projectedEOM",  0) or 0)
            owners_str  = str(r.get("alert1Recipients", "") or "")

            # Safe burn = amount we can spend per day to stay within budget
            safe_burn = (remaining / days_rem) if days_rem > 0 and remaining > 0 else 0
            overrun   = max(proj_eom - budget_amt, 0)

            # Top contributing service family for this sub (current 30d)
            sub_sf       = sf_full[sf_full["subscription"] == sub_name].sort_values("curr30", ascending=False)
            top_sf_name  = sub_sf.iloc[0]["serviceFamily"] if not sub_sf.empty else None
            top_sf_curr  = sub_sf.iloc[0]["curr30"]        if not sub_sf.empty else 0
            top_sf_chg   = sub_sf.iloc[0].get("chg30")     if not sub_sf.empty else None
            top_sf_accel = sub_sf.iloc[0].get("accelPct")  if not sub_sf.empty else None
            top_sf_share = round(top_sf_curr / sub_sf["curr30"].sum() * 100, 0) if not sub_sf.empty and sub_sf["curr30"].sum() > 0 else 0

            # Build driver context string
            driver_ctx = ""
            if top_sf_name:
                chg_str   = f"{top_sf_chg:+.1f}% vs prior 30d" if top_sf_chg is not None else "no prior data"
                accel_str = (f", 7d avg is {top_sf_accel:+.0f}% vs 30d avg (accelerating)" if top_sf_accel and abs(top_sf_accel) > 10 else "")
                driver_ctx = f"Top driver: <b>{top_sf_name}</b> ({int(top_sf_share)}% of MTD spend, {chg_str}{accel_str})."

            # ── Priority: IMMEDIATE — already over budget ──────────────────────
            if status == "OVER BUDGET":
                deficit   = actual_amt - budget_amt
                body      = (
                    f"Exceeded budget by <b>${deficit:,.0f}</b>. "
                    f"Current burn of <b>${burn_rate:,.0f}/day</b> must be stopped or drastically reduced. "
                    f"Projected month-end: <b>${proj_eom:,.0f}</b> (+${overrun:,.0f} over budget)."
                )
                if owners_str:
                    body += f" Notify: {owners_str}."
                rec_items.append((0, status, sub_display, "IMMEDIATE", "rec-immediate", "🔴 Budget Exceeded", body, driver_ctx))

            # ── Priority: URGENT — critical threshold crossed ──────────────────
            elif status == "CRITICAL":
                body = (
                    f"At <b>{r.get('pctUsed', 0):.1f}%</b> of budget with <b>{int(days_rem)} days</b> left. "
                    f"Must reduce from <b>${burn_rate:,.0f}/day</b> to <b>${safe_burn:,.0f}/day</b> "
                    f"to stay within budget. Projected overrun: <b>${overrun:,.0f}</b>."
                )
                rec_items.append((1, status, sub_display, "URGENT", "rec-urgent", "🟠 Critical Threshold", body, driver_ctx))

            # ── Priority: HIGH — warning threshold or accelerating service ─────
            elif status in ("WARNING", "WATCH"):
                body = (
                    f"Projected to exceed budget by <b>${overrun:,.0f}</b> at current pace. "
                    f"Reduce daily burn from <b>${burn_rate:,.0f}</b> to <b>${safe_burn:,.0f}</b> "
                    f"to finish the month within budget."
                )
                # Escalate to HIGH if a service family is accelerating strongly
                accel_flag = top_sf_accel is not None and abs(top_sf_accel) > 20
                priority   = "HIGH" if accel_flag else "MEDIUM"
                css_class  = "rec-high" if accel_flag else "rec-medium"
                label      = "🟡 Warning / Watch" if not accel_flag else "🟡 Warning — Accelerating Spend"
                rec_items.append((2 if accel_flag else 3, status, sub_display, priority, css_class, label, body, driver_ctx))

            # ── Priority: REVIEW — ok but top-5 org burn contributor ──────────
            else:
                top5_burn = df.nlargest(5, "dailyBurnRate")["subscription"].tolist()
                if sub_name in top5_burn and total_burn > 0:
                    burn_share = round(burn_rate / total_burn * 100, 1)
                    body       = (
                        f"Status is OK but accounts for <b>{burn_share}%</b> of total org daily burn "
                        f"(<b>${burn_rate:,.0f}/day</b>). Monitor for unexpected increases."
                    )
                    rec_items.append((4, status, sub_display, "REVIEW", "rec-review", "⚪ Top Burn Contributor", body, driver_ctx))

        if not rec_items:
            st.success("All subscriptions are within budget with no accelerating trends detected.")
        else:
            rec_items.sort(key=lambda x: x[0])
            for _, status, sub_display, priority, css_class, label, body, driver_ctx in rec_items:
                priority_colors = {
                    "IMMEDIATE": "#dc2626", "URGENT": "#ea580c",
                    "HIGH": "#ca8a04",      "MEDIUM": "#2563eb", "REVIEW": "#64748b"
                }
                p_color  = priority_colors.get(priority, "#64748b")
                dc_block = f"<div class='rec-driver'>{driver_ctx}</div>" if driver_ctx else ""
                st.markdown(f"""
<div class="rec-card {css_class}">
  <div class="rec-priority" style="color:{p_color}">{priority} &mdash; {label}</div>
  <div class="rec-title">{sub_display}</div>
  <div class="rec-body">{body}</div>
  {dc_block}
</div>
""", unsafe_allow_html=True)


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="dash-footer">
  <span>Showing {len(filtered)} entries · {len(df['subscription'].unique())} subscriptions with budgets
  · {n_over} over budget · {n_watch} watch · {n_ok} ok</span>
  <span>Power BI REST API &nbsp;·&nbsp; Dataset: {DATASET_ID[:8]}...
  &nbsp;·&nbsp; Cache: 5 min &nbsp;·&nbsp; Auto-refresh: 5 min</span>
</div>
""", unsafe_allow_html=True)
