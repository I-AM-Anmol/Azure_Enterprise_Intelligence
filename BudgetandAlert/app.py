import streamlit as st
import requests
import pandas as pd
import msal
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
TENANT_NAME  = "MedInsight Production"

st.set_page_config(page_title="Azure Budget Analysis", layout="wide", initial_sidebar_state="collapsed")
st_autorefresh(interval=300000)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
#MainMenu, footer, [data-testid="stToolbar"] { display:none !important; }

.top-banner {
    background:linear-gradient(135deg,#1e2a4a 0%,#0f1117 65%);
    border-radius:12px; padding:22px 28px 18px 28px; margin-bottom:20px;
    border:1px solid #2d3249;
}
.top-banner .dash-title { font-size:1.55rem; font-weight:700; color:#fff; line-height:1.3; }
.top-banner .dash-title span { color:#60b4ff; }
.top-banner .dash-meta { display:flex; gap:18px; flex-wrap:wrap; margin-top:6px; }
.top-banner .dash-meta .m { font-size:0.73rem; color:#64748b; }
.top-banner .dash-meta .m::before { content:"● "; color:#4da6ff; }

.kpi-card {
    background:#1a1d27; border-radius:10px;
    padding:16px 18px; border-top:4px solid #3b82f6;
    border-left:1px solid #2d3249; border-right:1px solid #2d3249; border-bottom:1px solid #2d3249;
}
.kpi-card.red   { border-top-color:#ef4444; }
.kpi-card.green { border-top-color:#22c55e; }
.kpi-card.ora   { border-top-color:#f97316; }
.kpi-lbl  { font-size:0.7rem; font-weight:700; color:#64748b; text-transform:uppercase; letter-spacing:.06em; margin-bottom:5px; }
.kpi-val  { font-size:2rem; font-weight:700; color:#fff; line-height:1.1; }
.kpi-val.red  { color:#ef4444; }
.kpi-val.grn  { color:#22c55e; }
.kpi-val.ora  { color:#f97316; }
.kpi-val.blu  { color:#3b82f6; }
.kpi-sub  { font-size:0.71rem; color:#64748b; margin-top:3px; }

.mb-wrap { margin:16px 0 6px 0; }
.mb-lbl  { display:flex; justify-content:space-between; font-size:0.72rem; color:#64748b; margin-bottom:5px; }
.mb-track { height:8px; background:#22263a; border-radius:4px; position:relative; overflow:visible; }
.mb-day   { height:100%; border-radius:4px; background:#2d3249; position:absolute; top:0; left:0; }
.mb-spend { height:100%; border-radius:4px; background:#3b82f6; opacity:.85; position:absolute; top:0; left:0; }
.mb-proj  { position:absolute; top:-3px; height:14px; width:2px; background:#f97316; border-radius:1px; }

.spill-row { display:flex; gap:8px; flex-wrap:wrap; margin:10px 0 4px 0; }
.spill {
    display:inline-flex; align-items:center; gap:6px;
    background:#1a1d27; border:1px solid #2d3249; border-radius:20px;
    padding:5px 13px; font-size:12px; color:#e2e8f0;
}
.dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
.sc-num { font-weight:700; font-size:14px; }

.section-label {
    font-size:0.95rem; font-weight:700; color:#c0d0e8;
    margin:18px 0 10px 0; padding-bottom:6px;
    border-bottom:2px solid #2d3249;
}

.stDownloadButton > button {
    background:#1565c0 !important; color:#fff !important;
    border:none !important; border-radius:6px !important;
    font-size:0.78rem !important; padding:7px 18px !important; font-weight:600 !important;
}
.stDownloadButton > button:hover { background:#1976d2 !important; }

/* Segmented control pill styling */
div[data-testid="stSegmentedControl"] { gap:0 !important; }
div[data-testid="stSegmentedControl"] > label { display:none !important; }
div[data-testid="stSegmentedControl"] button {
    border-radius:20px !important;
    font-size:0.78rem !important; font-weight:600 !important;
    padding:5px 18px !important;
    border:1.5px solid #2d3249 !important;
    background:#0f1117 !important; color:#94a3b8 !important;
    margin:0 3px !important;
}
div[data-testid="stSegmentedControl"] button[aria-checked="true"] {
    background:#1565c0 !important; border-color:#1565c0 !important; color:#fff !important;
}
div[data-testid="stSegmentedControl"] button:hover {
    border-color:#3b82f6 !important; color:#3b82f6 !important;
}

/* Budget table */
.bgt-wrap { overflow-x:auto; margin-top:8px; border-radius:8px; border:1px solid #2d3249; }
table.bgt { width:100%; border-collapse:collapse; font-size:12px; }
table.bgt thead tr { background:#1a1d27; border-bottom:2px solid #2d3249; }
table.bgt th { padding:9px 11px; text-align:left; font-size:11px; font-weight:600;
               text-transform:uppercase; letter-spacing:.05em; color:#64748b; white-space:nowrap; }
table.bgt th.num { text-align:right; }
table.bgt td { padding:7px 11px; border-bottom:1px solid rgba(45,50,73,.5); vertical-align:middle; color:#e2e8f0; }
table.bgt td.num { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
table.bgt tr.row-over td { background:rgba(239,68,68,.07); }
table.bgt tr.row-watch td { background:rgba(249,115,22,.045); }
table.bgt tr:hover td { background:rgba(255,255,255,.025); }

.sn  { font-weight:600; color:#e2e8f0; }
.sf  { font-size:10px; color:#64748b; margin-top:1px; }
.stn { font-size:10px; color:#3b82f6; margin-top:2px; opacity:.8; }
.bn  { font-size:11px; color:#64748b; font-family:monospace; background:#22263a;
       padding:2px 6px; border-radius:4px; white-space:nowrap; }

/* Progress bar */
.bw  { min-width:150px; }
.bt  { height:10px; background:#22263a; border-radius:5px; position:relative; overflow:visible; margin-bottom:3px; }
.bpj { height:100%; border-radius:5px; position:absolute; top:0; left:0; }
.bfl { height:100%; border-radius:5px; position:absolute; top:0; left:0; min-width:2px; }
.bl  { position:absolute; top:-3px; height:16px; width:2px; border-radius:1px; z-index:3; }
.bb  { background:#94a3b8; }
.ba1 { background:#f97316; }
.ba2 { background:#ef4444; }
.blbl { display:flex; justify-content:space-between; font-size:10px; color:#64748b; }

.ac  { line-height:1.55; }
.ap  { font-size:12px; font-weight:600; white-space:nowrap; }
.aa  { font-size:11px; color:#64748b; font-weight:400; }
.ag  { font-size:11px; }
.pos { color:#22c55e; } .neg { color:#ef4444; } .dys { color:#64748b; font-size:10px; margin-left:3px; }

.proj-over { color:#f97316; font-weight:600; }
.proj-tag  { font-size:10px; color:#ef4444; margin-left:3px; }
.proj-ok   { color:#e2e8f0; }
.na        { color:#64748b; }
.ow        { font-size:11px; color:#64748b; line-height:1.7; white-space:nowrap; }

.badge { display:inline-flex; align-items:center; padding:3px 8px; border-radius:20px;
         font-size:10px; font-weight:700; letter-spacing:.04em; text-transform:uppercase; white-space:nowrap; }
.badge-over  { background:rgba(239,68,68,.2);  color:#ef4444; border:1px solid rgba(239,68,68,.4); }
.badge-crit  { background:rgba(249,115,22,.2); color:#f97316; border:1px solid rgba(249,115,22,.4); }
.badge-warn  { background:rgba(234,179,8,.2);  color:#eab308; border:1px solid rgba(234,179,8,.4);  }
.badge-watch { background:rgba(251,146,60,.2); color:#fb923c; border:1px solid rgba(251,146,60,.4); }
.badge-ok    { background:rgba(34,197,94,.1);  color:#22c55e; border:1px solid rgba(34,197,94,.3);  }

.dash-footer {
    font-size:0.7rem; color:#4a5a78;
    margin-top:24px; padding-top:10px;
    border-top:1px solid #2d3249;
    display:flex; justify-content:space-between;
}
</style>
""", unsafe_allow_html=True)


# ── Auth ──────────────────────────────────────────────────────────────────────
def get_token():
    if "access_token" in st.session_state:
        return st.session_state["access_token"]
    app  = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY)
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        st.error("Failed to start device flow.")
        st.stop()
    st.info(f"**Sign in required** — Go to: {flow['verification_uri']}  |  Code: `{flow['user_code']}`")
    with st.spinner("Waiting for authentication..."):
        result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        st.error(f"Authentication failed: {result.get('error_description', 'Unknown error')}")
        st.stop()
    st.session_state["access_token"] = result["access_token"]
    st.session_state["user_email"]   = result.get("id_token_claims", {}).get("preferred_username", "unknown")
    st.rerun()


def strip_prefix(col):
    return col.split("[")[-1].rstrip("]") if "[" in col else col


@st.cache_data(ttl=300)
def fetch_budget_data(token):
    t0  = time.time()
    url = (
        f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}"
        f"/datasets/{DATASET_ID}/executeQueries"
    )
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"queries": [{"query": "EVALUATE BudgetData"}], "serializerSettings": {"includeNulls": True}},
        timeout=30,
    )
    if resp.status_code == 401:
        del st.session_state["access_token"]
        st.warning("Session expired — please re-authenticate.")
        st.rerun()
    resp.raise_for_status()
    rows    = resp.json()["results"][0]["tables"][0].get("rows", [])
    elapsed = round(time.time() - t0, 1)
    if not rows:
        return pd.DataFrame(), elapsed
    df         = pd.DataFrame(rows)
    df.columns = [strip_prefix(c) for c in df.columns]
    return df, elapsed


# ── Load & normalise data ─────────────────────────────────────────────────────
token     = get_token()
df, elapsed = fetch_budget_data(token)

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

# Derived display status — maps CRITICAL/WARNING through; adds WATCH for OK+projected-over
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

user_email  = st.session_state.get("user_email", "anmol.sharma@milliman.com")
generated   = datetime.now().strftime("%Y-%m-%d %H:%M")

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
    <span style="color:#e2e8f0">Today: Day {day_num} ({int(day_pct)}%)</span>
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


# ── Build HTML table ──────────────────────────────────────────────────────────
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

    # Progress bar
    bc     = bar_color(pct)
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

    # Alert cells
    if a1pct and not math.isnan(a1pct):
        a1_cell = f"<div class='ac'><div class='ap'>{int(a1pct)}% <span class='aa'>(${int(a1amt or 0)})</span></div><div class='ag'>{fmt_gap(a1gap, a1days)}</div></div>"
    else:
        a1_cell = "<span class='na'>No alerts set</span>"

    if a2pct and not math.isnan(a2pct):
        a2_cell = f"<div class='ac'><div class='ap'>{int(a2pct)}% <span class='aa'>(${int(a2amt or 0)})</span></div><div class='ag'>{fmt_gap(a2gap, a2days)}</div></div>"
    else:
        a2_cell = "<span class='na'>No alerts set</span>"

    # Projected cell
    if proj > budget:
        proj_cell = f"<span class='proj-over'>${int(proj)}</span> <span class='proj-tag'>+${int(proj-budget)} over</span>"
    else:
        proj_cell = f"<span class='proj-ok'>${int(proj)}</span>"

    # Remaining cell
    rem_cell = (f"<span class='neg'>${int(abs(rem))} deficit</span>"
                if rem < 0 else f"<span class='pos'>${int(rem)}</span>")

    # Owner cell
    owner_html = "".join(f"<div class='ow'>{o}</div>" for o in owners) if owners else "<span class='na'>—</span>"

    # Sub cell
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

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="dash-footer">
  <span>Showing {len(filtered)} entries · {len(df['subscription'].unique())} subscriptions with budgets
  · {n_over} over budget · {n_watch} watch · {n_ok} ok</span>
  <span>Power BI REST API &nbsp;·&nbsp; Dataset: {DATASET_ID[:8]}...
  &nbsp;·&nbsp; Cache: 5 min &nbsp;·&nbsp; Auto-refresh: 5 min</span>
</div>
""", unsafe_allow_html=True)
