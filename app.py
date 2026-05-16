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

# ── CSS: scoped styles only — no global text color override ──────────────────
st.markdown("""
<style>
/* Hide default Streamlit chrome */
#MainMenu, footer, [data-testid="stToolbar"] { display:none !important; }

/* Page background */
[data-testid="stAppViewContainer"] { background:#f0f4f8 !important; }
[data-testid="stHeader"]           { background:#1e2d4a !important; }

/* Top banner */
.top-banner {
    background:linear-gradient(135deg,#1e2d4a 0%,#2a4070 100%);
    border-radius:12px; padding:20px 28px 16px 28px;
    margin-bottom:20px;
}
.top-banner .dash-title {
    font-size:1.55rem; font-weight:700; color:#ffffff !important;
    line-height:1.3;
}
.top-banner .dash-title span { color:#60b4ff !important; }
.top-banner .dash-meta {
    display:flex; gap:18px; flex-wrap:wrap; margin-top:6px;
}
.top-banner .dash-meta .m {
    font-size:0.73rem; color:#a0c0e8 !important;
}
.top-banner .dash-meta .m::before { content:"● "; color:#60b4ff; }

/* KPI cards */
.kpi-card {
    background:#ffffff; border-radius:10px;
    padding:18px 20px; border-top:4px solid #0078d4;
    box-shadow:0 2px 8px rgba(0,0,0,0.08);
}
.kpi-card.green { border-top-color:#1e8e3e; }
.kpi-card.red   { border-top-color:#d93025; }
.kpi-icon       { font-size:1.4rem; margin-bottom:4px; }
.kpi-value      { font-size:2.2rem; font-weight:700; color:#1e2d4a !important; line-height:1.1; }
.kpi-value.green { color:#1e8e3e !important; }
.kpi-value.red   { color:#d93025 !important; }
.kpi-label {
    font-size:0.75rem; font-weight:700; color:#5a6a88 !important;
    text-transform:uppercase; letter-spacing:.06em;
}
.kpi-sub { font-size:0.71rem; color:#9aabb8 !important; margin-top:2px; }

/* Section divider label */
.section-label {
    font-size:0.95rem; font-weight:700; color:#1e2d4a !important;
    margin:18px 0 10px 0; padding-bottom:6px;
    border-bottom:2px solid #dde4ef;
}

/* Column header row */
.col-header {
    font-size:0.7rem; font-weight:700; color:#7a8fa6 !important;
    text-transform:uppercase; letter-spacing:.07em;
}

/* Download buttons */
.stDownloadButton > button {
    background:#0078d4 !important; color:#fff !important;
    border:none !important; border-radius:6px !important;
    font-size:0.78rem !important; padding:7px 18px !important;
    font-weight:600 !important;
}
.stDownloadButton > button:hover { background:#106ebe !important; }

/* Filter toggle buttons */
.stButton > button {
    border-radius:20px !important; font-size:0.77rem !important;
    padding:5px 16px !important; border:1.5px solid #c0cfe0 !important;
    background:#ffffff !important; color:#1e2d4a !important;
    font-weight:600 !important;
}
.stButton > button:hover {
    background:#e8f0fb !important; color:#0078d4 !important;
    border-color:#0078d4 !important;
}

/* Expander styling */
[data-testid="stExpander"] {
    background:#ffffff !important; border-radius:8px !important;
    border:1px solid #dde4ef !important; margin-bottom:4px !important;
}
[data-testid="stExpander"] summary {
    color:#1e2d4a !important; font-weight:600 !important;
}

/* Metric inside expander */
[data-testid="stMetric"] label { color:#5a6a88 !important; font-size:0.75rem !important; }
[data-testid="stMetricValue"] { color:#1e2d4a !important; font-size:1.4rem !important; }

/* Dataframe */
[data-testid="stDataFrame"] thead th {
    background:#f0f4f8 !important; color:#5a6a88 !important;
    font-size:0.72rem !important; text-transform:uppercase !important;
}
[data-testid="stDataFrame"] tbody td { color:#1e2d4a !important; font-size:0.82rem !important; }

/* Footer */
.dash-footer {
    font-size:0.7rem; color:#9aabb8 !important;
    margin-top:24px; padding-top:10px;
    border-top:1px solid #dde4ef;
    display:flex; justify-content:space-between;
}
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
    t0  = time.time()
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
    rows    = resp.json()["results"][0]["tables"][0].get("rows", [])
    elapsed = round(time.time() - t0, 1)
    if not rows:
        return pd.DataFrame(), elapsed
    df         = pd.DataFrame(rows)
    df.columns = [strip_prefix(c) for c in df.columns]
    return df, elapsed


# ── Load data ─────────────────────────────────────────────────────────────────
token = get_token()
t_start          = time.time()
subs_df,  _      = fetch_table(token, "EVALUATE Subscriptions")
accts_df, _      = fetch_table(token, "EVALUATE StorageAccounts")
scan_time        = round(time.time() - t_start, 1)

if subs_df.empty and accts_df.empty:
    st.warning("No data returned from the semantic model.")
    st.stop()

# ── Normalise ─────────────────────────────────────────────────────────────────
if not subs_df.empty:
    subs_df["CoveragePct"] = pd.to_numeric(subs_df.get("CoveragePct", 0), errors="coerce").fillna(0)
if not accts_df.empty:
    accts_df["HasPolicy"] = accts_df.get("HasPolicy", False).astype(bool)

# ── Detect column names ───────────────────────────────────────────────────────
# Subscriptions table: find Name and ID columns
sub_name_col = next((c for c in subs_df.columns if "name" in c.lower()), subs_df.columns[0] if not subs_df.empty else "SubscriptionName")
sub_id_col   = next((c for c in subs_df.columns if "id" in c.lower() and "subscription" in c.lower()), None) or \
               next((c for c in subs_df.columns if "id" in c.lower()), None)

# StorageAccounts table
acct_name_col = next((c for c in accts_df.columns if "account" in c.lower() and "name" in c.lower()), None) or \
                next((c for c in accts_df.columns if "name" in c.lower()), accts_df.columns[0] if not accts_df.empty else "AccountName")
acct_sub_id_col = next((c for c in accts_df.columns if "subscription" in c.lower() and "id" in c.lower()), None) or \
                  next((c for c in accts_df.columns if "subscription" in c.lower()), None)
policy_col    = next((c for c in accts_df.columns if "policy" in c.lower() and "name" in c.lower()), None)

# ── Build SubscriptionName lookup and add to accts_df ────────────────────────
# Map SubscriptionId → SubscriptionName so matrix shows names not GUIDs
if not subs_df.empty and not accts_df.empty and sub_id_col and acct_sub_id_col:
    id_to_name = dict(zip(subs_df[sub_id_col].astype(str), subs_df[sub_name_col].astype(str)))
    accts_df["_SubName"] = accts_df[acct_sub_id_col].astype(str).map(id_to_name).fillna(accts_df[acct_sub_id_col].astype(str))
    display_sub_col = "_SubName"
elif acct_sub_id_col:
    # No ID→Name mapping possible, use whatever we have
    accts_df["_SubName"] = accts_df[acct_sub_id_col].astype(str)
    display_sub_col = "_SubName"
else:
    display_sub_col = None

# ── KPI values ────────────────────────────────────────────────────────────────
total_subs  = len(subs_df)  if not subs_df.empty  else 0
total_accts = len(accts_df) if not accts_df.empty else 0
with_policy = int(accts_df["HasPolicy"].sum())      if not accts_df.empty else 0
no_policy   = int((~accts_df["HasPolicy"]).sum())   if not accts_df.empty else 0
cov_pct     = round(with_policy / total_accts * 100) if total_accts else 0
user_email  = st.session_state.get("user_email", "anmol.sharma@milliman.com")
generated   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ── Top banner ────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="top-banner">
  <div class="dash-title">Azure Storage <span>Lifecycle Policy</span> Coverage</div>
  <div class="dash-meta">
    <span class="m">{TENANT_NAME}</span>
    <span class="m">{user_email}</span>
    <span class="m">Generated: {generated}</span>
    <span class="m">Scan time: {scan_time} s</span>
    <span class="m">Auto-refreshes every 5 min</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── KPI Cards ─────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-icon">🗂️</div>
        <div class="kpi-value">{total_subs}</div>
        <div class="kpi-label">Total Subscriptions</div>
        <div class="kpi-sub">have storage accounts</div>
    </div>""", unsafe_allow_html=True)
with k2:
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-icon">🗄️</div>
        <div class="kpi-value">{total_accts}</div>
        <div class="kpi-label">Total Storage Accounts</div>
        <div class="kpi-sub">Across {total_subs} subscriptions</div>
    </div>""", unsafe_allow_html=True)
with k3:
    st.markdown(f"""<div class="kpi-card green">
        <div class="kpi-icon">✅</div>
        <div class="kpi-value green">{with_policy}</div>
        <div class="kpi-label">Lifecycle Policy Implemented</div>
        <div class="kpi-sub">{cov_pct}% overall coverage</div>
    </div>""", unsafe_allow_html=True)
with k4:
    st.markdown(f"""<div class="kpi-card red">
        <div class="kpi-icon">⚠️</div>
        <div class="kpi-value red">{no_policy}</div>
        <div class="kpi-label">No Lifecycle Policy</div>
        <div class="kpi-sub">Storage accounts exposed</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Filters ───────────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Filters</div>', unsafe_allow_html=True)
fc1, fc2, fc3, fc4 = st.columns([3, 3, 3, 2])

with fc1:
    st.caption("SUBSCRIPTION NAME")
    sub_search = st.text_input("", placeholder="Search subscription name...", label_visibility="collapsed", key="sub_search")

with fc2:
    st.caption("STORAGE ACCOUNT NAME")
    acct_options = sorted(accts_df[acct_name_col].dropna().unique().tolist()) if not accts_df.empty else []
    sel_accts    = st.multiselect("", acct_options, label_visibility="collapsed", key="acct_filter", placeholder="Filter by account name...")

with fc3:
    st.caption("POLICY STATUS")
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
    st.caption(" ")
    csv_all = accts_df.to_csv(index=False).encode() if not accts_df.empty else b""
    st.download_button("⬇ Export All CSV", csv_all, "storage_lifecycle.csv", "text/csv", key="exp_all")

# ── Apply filters ─────────────────────────────────────────────────────────────
filtered = accts_df.copy() if not accts_df.empty else pd.DataFrame()

if not filtered.empty:
    if sub_search and display_sub_col:
        filtered = filtered[filtered[display_sub_col].str.contains(sub_search, case=False, na=False)]
    if sel_accts:
        filtered = filtered[filtered[acct_name_col].isin(sel_accts)]
    pf = st.session_state.get("policy_filter", "All")
    if pf == "Implemented":
        filtered = filtered[filtered["HasPolicy"] == True]
    elif pf == "Not Implemented":
        filtered = filtered[filtered["HasPolicy"] == False]

# ── Subscription Coverage Matrix ──────────────────────────────────────────────
st.markdown("---")
hc1, hc2 = st.columns([5, 2])
with hc1:
    st.markdown('<div class="section-label">Subscription Coverage Matrix</div>', unsafe_allow_html=True)
with hc2:
    if not filtered.empty:
        csv_filt = filtered.to_csv(index=False).encode()
        st.download_button("⬇ Export Filtered CSV", csv_filt, "filtered.csv", "text/csv", key="exp_filt")

# Build subscription list
if not filtered.empty and display_sub_col:
    sub_groups = filtered.groupby(display_sub_col)
    sub_list   = sorted(filtered[display_sub_col].dropna().unique().tolist())
else:
    sub_groups = None
    sub_list   = subs_df[sub_name_col].dropna().tolist() if not subs_df.empty else []

if sub_search and not (not filtered.empty and display_sub_col):
    sub_list = [s for s in sub_list if sub_search.lower() in str(s).lower()]

if not sub_list:
    st.info("No subscriptions match the current filters.")
else:
    # Column headers
    h1, h2, h3, h4, h5 = st.columns([5, 3, 2, 2, 2])
    h1.markdown("**Subscription / Storage Account**")
    h2.markdown("**Policy Name**")
    h3.markdown("**Total**")
    h4.markdown("**With Policy**")
    h5.markdown("**Coverage %**")
    st.markdown("<hr style='margin:4px 0;'>", unsafe_allow_html=True)

    for sub_name in sub_list:
        if sub_groups and sub_name in sub_groups.groups:
            grp       = sub_groups.get_group(sub_name)
            t_total   = len(grp)
            t_with    = int(grp["HasPolicy"].sum())
            t_without = t_total - t_with
            t_cov     = round(t_with / t_total * 100, 1) if t_total else 0
            cov_icon  = "🟢" if t_cov >= 75 else ("🟡" if t_cov >= 50 else "🔴")

            label = f"{cov_icon} {sub_name}  —  {t_total} accounts · ✓ {t_with} · ✗ {t_without} · {t_cov}%"
            with st.expander(label, expanded=False):
                mc1, mc2, mc3, mc4 = st.columns(4)
                mc1.metric("Total Accounts",  t_total)
                mc2.metric("With Policy",     t_with)
                mc3.metric("Without Policy",  t_without)
                mc4.metric("Coverage",        f"{t_cov}%")

                acct_rows = []
                for _, row in grp.iterrows():
                    acct_nm  = row.get(acct_name_col, "—")
                    pol_name = (row.get(policy_col, "") if policy_col else "") or ("Implemented" if row["HasPolicy"] else "Not Set")
                    status   = "✓ Implemented" if row["HasPolicy"] else "✗ Not Set"
                    acct_rows.append({"Storage Account": acct_nm, "Policy Name": pol_name, "Status": status})

                if acct_rows:
                    st.dataframe(pd.DataFrame(acct_rows), use_container_width=True, hide_index=True)
        else:
            sub_row = subs_df[subs_df[sub_name_col] == sub_name] if not subs_df.empty else pd.DataFrame()
            t_cov   = float(sub_row["CoveragePct"].values[0]) if not sub_row.empty else 0
            cov_icon = "🟢" if t_cov >= 75 else ("🟡" if t_cov >= 50 else "🔴")
            with st.expander(f"{cov_icon} {sub_name}  —  Coverage: {t_cov}%", expanded=False):
                st.caption("No storage accounts matched current filters for this subscription.")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="dash-footer">
  <span>Showing {len(sub_list)} subscriptions · Accounts: {total_accts} · Covered: {with_policy} · Uncovered: {no_policy}</span>
  <span>Tenant: {TENANT_ID[:8]}... · Power BI REST API · Cache: 5 min · Auto-refresh: 5 min</span>
</div>
""", unsafe_allow_html=True)
