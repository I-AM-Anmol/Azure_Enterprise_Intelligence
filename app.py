import streamlit as st
import requests
import pandas as pd
import msal
from datetime import datetime
import time
from streamlit_autorefresh import st_autorefresh

TENANT_ID    = "e240d61e-61e3-4c9e-ab90-8644b2f4d2a9"
WORKSPACE_ID = "eca3c81e-a968-42a5-899f-d8fc1a45ebec"
DATASET_ID   = "a1022686-d90e-4c03-b36d-cdafacdc3dbc"
CLIENT_ID    = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
AUTHORITY    = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES       = ["https://analysis.windows.net/powerbi/api/.default"]
TENANT_NAME  = "MedInsight Production Tenant"

st.set_page_config(
    page_title="Azure Storage Lifecycle Policy Coverage",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st_autorefresh(interval=300000)

st.markdown("""
<style>
/* ── Base ── */
[data-testid="stAppViewContainer"] { background:#f0f4f8; }
[data-testid="stHeader"]           { background:#1e2d4a; }
section[data-testid="stSidebar"]   { background:#1e2d4a; }
#MainMenu, footer, [data-testid="stToolbar"] { display:none !important; }

/* ── Top banner ── */
.top-banner {
    background:linear-gradient(135deg,#1e2d4a 0%,#2a4070 100%);
    border-radius:12px; padding:20px 28px 16px 28px;
    margin-bottom:24px; display:flex;
    justify-content:space-between; align-items:flex-start;
}
.dash-title { font-size:1.55rem; font-weight:700; color:#ffffff; }
.dash-title span { color:#60b4ff; }
.dash-meta { display:flex; gap:18px; flex-wrap:wrap; margin-top:6px; }
.dash-meta .m { font-size:0.73rem; color:#a0c0e8; }
.dash-meta .m::before { content:"● "; color:#60b4ff; }

/* ── KPI cards ── */
.kpi-card {
    background:#ffffff; border-radius:10px;
    padding:18px 20px; border-top:4px solid #0078d4;
    box-shadow:0 2px 8px rgba(0,0,0,0.08);
    display:flex; flex-direction:column; gap:5px;
}
.kpi-card.green { border-top-color:#1e8e3e; }
.kpi-card.red   { border-top-color:#d93025; }
.kpi-icon  { font-size:1.4rem; }
.kpi-value { font-size:2.2rem; font-weight:700; color:#1e2d4a; line-height:1.1; }
.kpi-value.green { color:#1e8e3e; }
.kpi-value.red   { color:#d93025; }
.kpi-label { font-size:0.75rem; font-weight:700; color:#5a6a88;
    text-transform:uppercase; letter-spacing:.06em; }
.kpi-sub   { font-size:0.71rem; color:#9aabb8; }

/* ── Panel ── */
.panel {
    background:#ffffff; border-radius:10px;
    padding:18px 22px; margin-bottom:18px;
    box-shadow:0 2px 8px rgba(0,0,0,0.07);
}
.panel-title {
    font-size:0.95rem; font-weight:700; color:#1e2d4a;
    margin-bottom:14px; padding-bottom:8px;
    border-bottom:2px solid #e8eef5;
}

/* ── Filter label ── */
.filter-label {
    font-size:0.68rem; font-weight:700; color:#7a8fa6;
    text-transform:uppercase; letter-spacing:.08em; margin-bottom:3px;
}

/* ── Matrix table ── */
.matrix-table { width:100%; border-collapse:collapse; font-size:0.82rem; }
.matrix-table thead tr {
    background:#e8eef5; color:#4a5a78;
    font-size:0.7rem; font-weight:700;
    text-transform:uppercase; letter-spacing:.06em;
}
.matrix-table th { padding:10px 14px; text-align:left; border-bottom:2px solid #d0dbe8; }
.matrix-table th.num { text-align:right; }

/* Sub-rows (storage accounts) */
.matrix-table tr.sub-row { background:#f8fafd; }
.matrix-table tr.sub-row td { padding:7px 14px 7px 36px; color:#3a4a68;
    border-bottom:1px solid #eef2f7; font-size:0.79rem; }

/* Subscription rows */
.matrix-table tr.sub-header { background:#ffffff; cursor:pointer; }
.matrix-table tr.sub-header:hover { background:#f0f6ff; }
.matrix-table tr.sub-header td {
    padding:11px 14px; color:#1e2d4a; font-weight:600;
    border-bottom:1px solid #dde4ef;
}
.matrix-table td.num { text-align:right; }

/* Coverage badge */
.cov-high   { color:#1e8e3e; font-weight:700; }
.cov-medium { color:#e37400; font-weight:700; }
.cov-low    { color:#d93025; font-weight:700; }
.cov-none   { color:#9aabb8; font-weight:700; }

/* Policy pill */
.pill-yes { background:#e6f4ea; color:#1e8e3e; border-radius:12px;
    padding:2px 10px; font-size:0.7rem; font-weight:600; }
.pill-no  { background:#fce8e6; color:#d93025; border-radius:12px;
    padding:2px 10px; font-size:0.7rem; font-weight:600; }

/* ── Download buttons ── */
.stDownloadButton > button {
    background:#0078d4 !important; color:#fff !important;
    border:none !important; border-radius:6px !important;
    font-size:0.78rem !important; padding:7px 18px !important;
    font-weight:600 !important;
}
.stDownloadButton > button:hover { background:#106ebe !important; }

/* ── Toggle buttons ── */
.stButton > button {
    border-radius:20px !important; font-size:0.77rem !important;
    padding:5px 16px !important; border:1.5px solid #c0cfe0 !important;
    background:#ffffff !important; color:#4a5a78 !important;
    font-weight:600 !important;
}
.stButton > button:hover { background:#e8f0fb !important; color:#0078d4 !important;
    border-color:#0078d4 !important; }

/* ── Streamlit inputs ── */
[data-testid="stTextInput"] input {
    background:#f7fafd !important; border:1.5px solid #c8d8e8 !important;
    border-radius:7px !important; color:#1e2d4a !important;
    font-size:0.82rem !important;
}
[data-testid="stMultiSelect"] { font-size:0.82rem !important; }

/* ── Footer ── */
.dash-footer {
    display:flex; justify-content:space-between;
    font-size:0.69rem; color:#9aabb8;
    margin-top:22px; padding-top:10px;
    border-top:1px solid #dde4ef;
}

/* ── details/summary (expand rows) ── */
details > summary { list-style:none; cursor:pointer; }
details > summary::-webkit-details-marker { display:none; }
details[open] > summary .arrow { transform:rotate(90deg); display:inline-block; }
.arrow { display:inline-block; transition:transform .15s; margin-right:6px; color:#0078d4; }
</style>
""", unsafe_allow_html=True)


# ── Auth ──────────────────────────────────────────────────────────────────────
def get_token():
    if "access_token" in st.session_state:
        return st.session_state["access_token"]
    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY)
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
    st.session_state["user_email"] = result.get("id_token_claims", {}).get("preferred_username", "unknown")
    st.rerun()


def strip_prefix(col):
    return col.split("[")[-1].rstrip("]") if "[" in col else col


@st.cache_data(ttl=300)
def fetch_table(token, dax):
    t0 = time.time()
    url = f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}/datasets/{DATASET_ID}/executeQueries"
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"queries": [{"query": dax}], "serializerSettings": {"includeNulls": True}},
        timeout=30,
    )
    if resp.status_code == 401:
        del st.session_state["access_token"]
        st.warning("Session expired. Please re-authenticate.")
        st.rerun()
    resp.raise_for_status()
    rows = resp.json()["results"][0]["tables"][0].get("rows", [])
    elapsed = round(time.time() - t0, 1)
    if not rows:
        return pd.DataFrame(), elapsed
    df = pd.DataFrame(rows)
    df.columns = [strip_prefix(c) for c in df.columns]
    return df, elapsed


def cov_class(pct):
    if pct >= 75: return "cov-high"
    if pct >= 50: return "cov-medium"
    if pct > 0:   return "cov-low"
    return "cov-none"


# ── Load data ─────────────────────────────────────────────────────────────────
token = get_token()
t_start = time.time()
subs_df,  _ = fetch_table(token, "EVALUATE Subscriptions")
accts_df, _ = fetch_table(token, "EVALUATE StorageAccounts")
scan_time   = round(time.time() - t_start, 1)

if subs_df.empty and accts_df.empty:
    st.warning("No data returned from the semantic model.")
    st.stop()

# ── Normalise columns ─────────────────────────────────────────────────────────
if not subs_df.empty:
    subs_df["CoveragePct"] = pd.to_numeric(subs_df.get("CoveragePct", 0), errors="coerce").fillna(0)

if not accts_df.empty:
    accts_df["HasPolicy"] = accts_df.get("HasPolicy", False).astype(bool)

# Detect key column names (flexible — works whatever the semantic model calls them)
sub_name_col  = next((c for c in subs_df.columns  if "name" in c.lower()), subs_df.columns[0] if not subs_df.empty else "SubscriptionName")
acct_name_col = next((c for c in accts_df.columns if "account" in c.lower() and "name" in c.lower()), None) or \
                next((c for c in accts_df.columns if "name" in c.lower()), accts_df.columns[0] if not accts_df.empty else "AccountName")
acct_sub_col  = next((c for c in accts_df.columns if "subscription" in c.lower() and ("name" in c.lower())), None) or \
                next((c for c in accts_df.columns if "subscription" in c.lower()), None)
policy_col    = next((c for c in accts_df.columns if "policy" in c.lower() and "name" in c.lower()), None)

# ── KPI values ────────────────────────────────────────────────────────────────
total_subs  = len(subs_df)  if not subs_df.empty  else 0
total_accts = len(accts_df) if not accts_df.empty else 0
with_policy = int(accts_df["HasPolicy"].sum())       if not accts_df.empty else 0
no_policy   = int((~accts_df["HasPolicy"]).sum())    if not accts_df.empty else 0
cov_pct     = round(with_policy / total_accts * 100) if total_accts else 0
user_email  = st.session_state.get("user_email", "anmol.sharma@milliman.com")
generated   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ── Top banner ────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="top-banner">
  <div>
    <div class="dash-title">Azure Storage <span>Lifecycle Policy</span> Coverage</div>
    <div class="dash-meta">
      <span class="m">{TENANT_NAME}</span>
      <span class="m">{user_email}</span>
      <span class="m">Generated: {generated}</span>
      <span class="m">Scan time: {scan_time} s</span>
      <span class="m">Auto-refreshes every 5 min</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── KPI Cards ─────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(f'<div class="kpi-card"><div class="kpi-icon">🗂️</div><div class="kpi-value">{total_subs}</div><div class="kpi-label">Total Subscriptions</div><div class="kpi-sub">have storage accounts</div></div>', unsafe_allow_html=True)
with k2:
    st.markdown(f'<div class="kpi-card"><div class="kpi-icon">🗄️</div><div class="kpi-value">{total_accts}</div><div class="kpi-label">Total Storage Accounts</div><div class="kpi-sub">Across {total_subs} subscriptions</div></div>', unsafe_allow_html=True)
with k3:
    st.markdown(f'<div class="kpi-card green"><div class="kpi-icon">✅</div><div class="kpi-value green">{with_policy}</div><div class="kpi-label">Lifecycle Policy Implemented</div><div class="kpi-sub">{cov_pct}% overall coverage</div></div>', unsafe_allow_html=True)
with k4:
    st.markdown(f'<div class="kpi-card red"><div class="kpi-icon">⚠️</div><div class="kpi-value red">{no_policy}</div><div class="kpi-label">No Lifecycle Policy</div><div class="kpi-sub">Storage accounts exposed</div></div>', unsafe_allow_html=True)

st.markdown("<div style='margin-top:6px'></div>", unsafe_allow_html=True)

# ── Filters ───────────────────────────────────────────────────────────────────
st.markdown('<div class="panel">', unsafe_allow_html=True)
st.markdown('<div class="panel-title">Filters</div>', unsafe_allow_html=True)

fc1, fc2, fc3, fc4 = st.columns([3, 3, 3, 2])

with fc1:
    st.markdown('<div class="filter-label">Subscription Name</div>', unsafe_allow_html=True)
    sub_search = st.text_input("", placeholder="Search subscription...", label_visibility="collapsed", key="sub_search")

with fc2:
    st.markdown('<div class="filter-label">Storage Account Name</div>', unsafe_allow_html=True)
    acct_options = sorted(accts_df[acct_name_col].dropna().unique().tolist()) if not accts_df.empty else []
    sel_accts = st.multiselect("", acct_options, label_visibility="collapsed", key="acct_filter", placeholder="Filter by account name...")

with fc3:
    st.markdown('<div class="filter-label">Policy Status</div>', unsafe_allow_html=True)
    b1, b2, b3 = st.columns(3)
    if "policy_filter" not in st.session_state:
        st.session_state["policy_filter"] = "All"
    with b1:
        if st.button("All",               key="f_all"):  st.session_state["policy_filter"] = "All"
    with b2:
        if st.button("✓ Implemented",     key="f_impl"): st.session_state["policy_filter"] = "Implemented"
    with b3:
        if st.button("✗ Not Implemented", key="f_not"):  st.session_state["policy_filter"] = "Not Implemented"

with fc4:
    st.markdown('<div class="filter-label">&nbsp;</div>', unsafe_allow_html=True)
    csv_all = (accts_df.to_csv(index=False).encode() if not accts_df.empty else b"")
    st.download_button("⬇ Export All CSV", csv_all, "storage_lifecycle.csv", "text/csv", key="exp_all")

st.markdown('</div>', unsafe_allow_html=True)

# ── Apply filters to accounts ─────────────────────────────────────────────────
filtered_accts = accts_df.copy() if not accts_df.empty else pd.DataFrame()

if not filtered_accts.empty:
    if sub_search and acct_sub_col:
        filtered_accts = filtered_accts[filtered_accts[acct_sub_col].astype(str).str.contains(sub_search, case=False, na=False)]
    if sel_accts:
        filtered_accts = filtered_accts[filtered_accts[acct_name_col].isin(sel_accts)]
    pf = st.session_state.get("policy_filter", "All")
    if pf == "Implemented":
        filtered_accts = filtered_accts[filtered_accts["HasPolicy"] == True]
    elif pf == "Not Implemented":
        filtered_accts = filtered_accts[filtered_accts["HasPolicy"] == False]

# ── Subscription Coverage Matrix ─────────────────────────────────────────────
st.markdown("---")
hc1, hc2 = st.columns([4, 2])
with hc1:
    st.markdown("### Subscription Coverage Matrix")
with hc2:
    if not filtered_accts.empty:
        csv_filtered = filtered_accts.to_csv(index=False).encode()
        st.download_button("⬇ Export Filtered CSV", csv_filtered, "storage_lifecycle_filtered.csv", "text/csv", key="exp_filt")

# Group accounts by subscription
if not filtered_accts.empty and acct_sub_col:
    sub_groups = filtered_accts.groupby(acct_sub_col)
    sub_list   = sorted(filtered_accts[acct_sub_col].dropna().unique().tolist())
else:
    sub_groups = None
    sub_list   = subs_df[sub_name_col].dropna().tolist() if not subs_df.empty else []

# Apply subscription name search filter to sub_list
if sub_search:
    sub_list = [s for s in sub_list if sub_search.lower() in str(s).lower()]

if not sub_list:
    st.info("No subscriptions match the current filters.")
else:
    # Column header row
    h1, h2, h3, h4, h5 = st.columns([5, 3, 2, 2, 2])
    h1.markdown("<span style='font-size:0.72rem;font-weight:700;color:#7a8fa6;text-transform:uppercase;letter-spacing:.06em;'>Subscription / Storage Account</span>", unsafe_allow_html=True)
    h2.markdown("<span style='font-size:0.72rem;font-weight:700;color:#7a8fa6;text-transform:uppercase;letter-spacing:.06em;'>Policy Name</span>", unsafe_allow_html=True)
    h3.markdown("<span style='font-size:0.72rem;font-weight:700;color:#7a8fa6;text-transform:uppercase;letter-spacing:.06em;'>Total</span>", unsafe_allow_html=True)
    h4.markdown("<span style='font-size:0.72rem;font-weight:700;color:#7a8fa6;text-transform:uppercase;letter-spacing:.06em;'>With Policy</span>", unsafe_allow_html=True)
    h5.markdown("<span style='font-size:0.72rem;font-weight:700;color:#7a8fa6;text-transform:uppercase;letter-spacing:.06em;'>Coverage %</span>", unsafe_allow_html=True)
    st.markdown("<hr style='margin:4px 0 8px 0;border-color:#dde4ef;'>", unsafe_allow_html=True)

    for sub_name in sub_list:
        if sub_groups and sub_name in sub_groups.groups:
            grp       = sub_groups.get_group(sub_name)
            t_total   = len(grp)
            t_with    = int(grp["HasPolicy"].sum())
            t_without = t_total - t_with
            t_cov     = round(t_with / t_total * 100, 1) if t_total else 0

            cov_color = "#1e8e3e" if t_cov >= 75 else ("#e37400" if t_cov >= 50 else "#d93025")
            label = (
                f"**{sub_name}** &nbsp;&nbsp; "
                f"<span style='color:#5a6a88;font-size:0.8rem;'>"
                f"Total: {t_total} &nbsp;|&nbsp; "
                f"<span style='color:#1e8e3e;'>✓ {t_with}</span> &nbsp;|&nbsp; "
                f"<span style='color:#d93025;'>✗ {t_without}</span> &nbsp;|&nbsp; "
                f"<span style='color:{cov_color};font-weight:700;'>{t_cov}%</span>"
                f"</span>"
            )

            with st.expander(sub_name, expanded=False):
                # Summary bar inside expander
                sc1, sc2, sc3, sc4 = st.columns(4)
                sc1.metric("Total Accounts", t_total)
                sc2.metric("With Policy",    t_with)
                sc3.metric("Without Policy", t_without)
                sc4.metric("Coverage",       f"{t_cov}%")

                # Individual accounts table
                acct_rows = []
                for _, row in grp.iterrows():
                    acct_nm  = row.get(acct_name_col, "—")
                    pol_name = (row.get(policy_col, "") if policy_col else "") or ("Implemented" if row["HasPolicy"] else "Not Set")
                    status   = "✓ Implemented" if row["HasPolicy"] else "✗ Not Set"
                    acct_rows.append({
                        "Storage Account": acct_nm,
                        "Policy Name":     pol_name,
                        "Status":          status,
                    })

                if acct_rows:
                    acct_df_display = pd.DataFrame(acct_rows)
                    st.dataframe(acct_df_display, use_container_width=True, hide_index=True)
        else:
            # Subscription only in subs_df (no accounts matched)
            sub_row = subs_df[subs_df[sub_name_col] == sub_name] if not subs_df.empty else pd.DataFrame()
            t_cov   = float(sub_row["CoveragePct"].values[0]) if not sub_row.empty else 0
            cov_color = "#1e8e3e" if t_cov >= 75 else ("#e37400" if t_cov >= 50 else "#d93025")
            with st.expander(f"{sub_name}  —  Coverage: {t_cov}%", expanded=False):
                st.caption("No storage accounts matched current filters for this subscription.")

# ── Footer ────────────────────────────────────────────────────────────────────
covered   = with_policy
uncovered = no_policy
st.markdown(f"""
<div class="dash-footer">
  <span>Showing {len(sub_list)} subscriptions &nbsp;·&nbsp;
        Accounts: {total_accts} &nbsp;·&nbsp;
        Covered: {covered} &nbsp;·&nbsp;
        Uncovered: {uncovered}</span>
  <span>Tenant: {TENANT_ID[:8]}... &nbsp;·&nbsp; Power BI REST API &nbsp;·&nbsp; Cache: 5 min &nbsp;·&nbsp; Auto-refresh: 5 min</span>
</div>
""", unsafe_allow_html=True)
