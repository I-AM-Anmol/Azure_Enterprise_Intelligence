import streamlit as st
import requests
import pandas as pd
import msal
from datetime import datetime
import time

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

st.markdown("""
<style>
/* ── Global dark theme ── */
[data-testid="stAppViewContainer"] { background:#0a0e1a; }
[data-testid="stHeader"] { background:#0a0e1a; }
section[data-testid="stSidebar"] { background:#0d1226; }
body, .stMarkdown, p, span, div { color:#e0e6f0; }

/* ── Hide default streamlit chrome ── */
#MainMenu, footer, [data-testid="stToolbar"] { display:none !important; }

/* ── Top header bar ── */
.dash-header {
    display:flex; align-items:center; justify-content:space-between;
    padding:18px 4px 6px 4px;
}
.dash-title { font-size:1.6rem; font-weight:700; color:#ffffff; }
.dash-title span.blue  { color:#4da6ff; }
.dash-title span.green { color:#4da6ff; }
.dash-meta {
    display:flex; gap:20px; align-items:center;
    font-size:0.75rem; color:#8899bb; margin-top:4px;
}
.dash-meta .dot::before { content:"• "; color:#4da6ff; }

/* ── KPI cards ── */
.kpi-row { display:flex; gap:16px; margin:20px 0 24px 0; }
.kpi-card {
    flex:1; background:#131929; border-radius:10px;
    padding:20px 22px; border-top:3px solid #4da6ff;
    display:flex; flex-direction:column; gap:6px;
}
.kpi-card.green  { border-top-color:#2ecc71; }
.kpi-card.red    { border-top-color:#e74c3c; }
.kpi-icon { font-size:1.5rem; margin-bottom:2px; }
.kpi-value { font-size:2.4rem; font-weight:700; color:#ffffff; line-height:1; }
.kpi-value.green { color:#2ecc71; }
.kpi-value.red   { color:#e74c3c; }
.kpi-label { font-size:0.78rem; font-weight:600; color:#a0b0cc; text-transform:uppercase; letter-spacing:.06em; }
.kpi-sub   { font-size:0.72rem; color:#5a6a88; }

/* ── Filter bar ── */
.filter-bar {
    background:#131929; border-radius:10px;
    padding:14px 20px; display:flex; align-items:center;
    gap:28px; margin-bottom:20px; flex-wrap:wrap;
}
.filter-label { font-size:0.7rem; font-weight:600; color:#6a7a99;
    text-transform:uppercase; letter-spacing:.08em; margin-bottom:2px; }

/* ── Section header ── */
.section-header {
    display:flex; justify-content:space-between; align-items:center;
    margin-bottom:12px;
}
.section-title { font-size:1.05rem; font-weight:600; color:#ffffff; }
.section-hint  { font-size:0.72rem; color:#5a6a88; }

/* ── Table styling ── */
[data-testid="stDataFrame"] { background:#131929 !important; border-radius:8px; }
[data-testid="stDataFrame"] th {
    background:#1a2540 !important; color:#8899bb !important;
    font-size:0.72rem !important; text-transform:uppercase !important;
    letter-spacing:.06em !important;
}
[data-testid="stDataFrame"] td { color:#d0daf0 !important; font-size:0.82rem !important; }

/* ── Export buttons ── */
.stDownloadButton > button {
    background:#1565c0 !important; color:#fff !important;
    border:none !important; border-radius:6px !important;
    font-size:0.78rem !important; padding:6px 16px !important;
}
.stDownloadButton > button:hover { background:#1976d2 !important; }

/* ── Toggle button group ── */
div[data-testid="stHorizontalBlock"] .stButton > button {
    border-radius:20px !important; font-size:0.78rem !important;
    padding:4px 16px !important; border:1px solid #2a3a55 !important;
    background:#0d1226 !important; color:#8899bb !important;
}
div[data-testid="stHorizontalBlock"] .stButton > button:hover {
    background:#1a2a45 !important; color:#fff !important;
}

/* ── Footer ── */
.dash-footer {
    display:flex; justify-content:space-between;
    font-size:0.7rem; color:#4a5a78;
    margin-top:28px; padding-top:12px;
    border-top:1px solid #1a2540;
}

/* ── Divider ── */
hr { border-color:#1a2540 !important; margin:8px 0 !important; }

/* Input fields dark */
input[type="text"] { background:#0d1226 !important; color:#e0e6f0 !important;
    border:1px solid #2a3a55 !important; border-radius:6px !important; }
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


# ── Load data ─────────────────────────────────────────────────────────────────
token = get_token()
t_start = time.time()
subs_df, t1 = fetch_table(token, "EVALUATE Subscriptions")
accts_df, t2 = fetch_table(token, "EVALUATE StorageAccounts")
scan_time = round(time.time() - t_start, 1)

if subs_df.empty and accts_df.empty:
    st.warning("No data returned from the semantic model.")
    st.stop()

# Normalise
if not subs_df.empty:
    subs_df["CoveragePct"] = pd.to_numeric(subs_df.get("CoveragePct", 0), errors="coerce").fillna(0)
if not accts_df.empty:
    accts_df["HasPolicy"] = accts_df.get("HasPolicy", False).astype(bool)

user_email = st.session_state.get("user_email", "anmol.sharma@milliman.com")
generated  = datetime.now().strftime("%Y-%m-%d %H:%M:%S (local)")

# ── KPI values ────────────────────────────────────────────────────────────────
total_subs   = len(subs_df) if not subs_df.empty else 0
total_accts  = len(accts_df) if not accts_df.empty else 0
with_policy  = int(accts_df["HasPolicy"].sum()) if not accts_df.empty else 0
no_policy    = int((~accts_df["HasPolicy"]).sum()) if not accts_df.empty else 0

# ── Header ────────────────────────────────────────────────────────────────────
col_title, col_export = st.columns([5, 1])
with col_title:
    st.markdown(f"""
    <div class="dash-title">
        Azure Storage <span class="blue">Lifecycle Policy</span> Coverage
    </div>
    <div class="dash-meta">
        <span class="dot">{TENANT_NAME}</span>
        <span class="dot">{user_email}</span>
        <span class="dot">Generated: {generated}</span>
        <span class="dot">Scan time: {scan_time} s</span>
    </div>
    """, unsafe_allow_html=True)

# ── KPI Cards ─────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)

with k1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-icon">🗂️</div>
        <div class="kpi-value">{total_subs}</div>
        <div class="kpi-label">Total Subscriptions</div>
        <div class="kpi-sub">have storage accounts</div>
    </div>""", unsafe_allow_html=True)

with k2:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-icon">🗄️</div>
        <div class="kpi-value">{total_accts}</div>
        <div class="kpi-label">Total Storage Accounts</div>
        <div class="kpi-sub">Across {total_subs} subscriptions</div>
    </div>""", unsafe_allow_html=True)

with k3:
    st.markdown(f"""
    <div class="kpi-card green">
        <div class="kpi-icon">✅</div>
        <div class="kpi-value green">{with_policy}</div>
        <div class="kpi-label">Lifecycle Policy Implemented</div>
        <div class="kpi-sub">{round(with_policy/total_accts*100) if total_accts else 0}% overall coverage</div>
    </div>""", unsafe_allow_html=True)

with k4:
    st.markdown(f"""
    <div class="kpi-card red">
        <div class="kpi-icon">⚠️</div>
        <div class="kpi-value red">{no_policy}</div>
        <div class="kpi-label">No Lifecycle Policy</div>
        <div class="kpi-sub">Storage accounts exposed</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)

# ── Build subscription coverage matrix ───────────────────────────────────────
if not subs_df.empty and not accts_df.empty:
    sub_name_col = next((c for c in subs_df.columns if "name" in c.lower()), subs_df.columns[0])
    sub_id_col   = next((c for c in accts_df.columns if "subscriptionid" in c.lower() or "subscription_id" in c.lower()), None)

    if sub_id_col:
        matrix = (
            accts_df.groupby(sub_id_col)
            .agg(
                TotalAccounts=("HasPolicy", "count"),
                WithPolicy=("HasPolicy", "sum"),
            )
            .reset_index()
        )
        matrix["WithoutPolicy"] = matrix["TotalAccounts"] - matrix["WithPolicy"]
        matrix["CoveragePct"]   = (matrix["WithPolicy"] / matrix["TotalAccounts"] * 100).round(1)
        matrix.rename(columns={sub_id_col: "SubscriptionName"}, inplace=True)
    else:
        matrix = subs_df[[sub_name_col, "CoveragePct"]].copy()
        matrix.rename(columns={sub_name_col: "SubscriptionName"}, inplace=True)
        matrix["TotalAccounts"]  = "-"
        matrix["WithPolicy"]     = "-"
        matrix["WithoutPolicy"]  = "-"
else:
    matrix = pd.DataFrame(columns=["SubscriptionName", "TotalAccounts", "WithPolicy", "WithoutPolicy", "CoveragePct"])

# ── Filter bar ────────────────────────────────────────────────────────────────
st.markdown('<div style="background:#131929;border-radius:10px;padding:14px 20px;margin-bottom:20px;">', unsafe_allow_html=True)
f1, f2, f3 = st.columns([3, 3, 2])

with f1:
    st.markdown('<div class="filter-label">Subscription</div>', unsafe_allow_html=True)
    search = st.text_input("", placeholder="Search subscription name...", label_visibility="collapsed", key="sub_search")

with f2:
    st.markdown('<div class="filter-label">Policy Status</div>', unsafe_allow_html=True)
    b1, b2, b3 = st.columns(3)
    if "policy_filter" not in st.session_state:
        st.session_state["policy_filter"] = "All"
    with b1:
        if st.button("All", key="f_all"):
            st.session_state["policy_filter"] = "All"
    with b2:
        if st.button("✓ Implemented", key="f_impl"):
            st.session_state["policy_filter"] = "Implemented"
    with b3:
        if st.button("✗ Not Implemented", key="f_not"):
            st.session_state["policy_filter"] = "Not Implemented"

with f3:
    st.markdown('<div class="filter-label">&nbsp;</div>', unsafe_allow_html=True)
    csv_all = subs_df.to_csv(index=False).encode()
    st.download_button("⬇ Export All CSV", csv_all, "storage_lifecycle_all.csv", "text/csv", key="exp_all")

st.markdown('</div>', unsafe_allow_html=True)

# Apply filters
filtered_matrix = matrix.copy()
if search:
    filtered_matrix = filtered_matrix[
        filtered_matrix["SubscriptionName"].astype(str).str.contains(search, case=False, na=False)
    ]
policy_filter = st.session_state.get("policy_filter", "All")
if policy_filter == "Implemented" and "WithPolicy" in filtered_matrix.columns:
    filtered_matrix = filtered_matrix[pd.to_numeric(filtered_matrix["WithPolicy"], errors="coerce") > 0]
elif policy_filter == "Not Implemented" and "WithoutPolicy" in filtered_matrix.columns:
    filtered_matrix = filtered_matrix[pd.to_numeric(filtered_matrix["WithoutPolicy"], errors="coerce") > 0]

# ── Subscription Coverage Matrix ──────────────────────────────────────────────
hdr1, hdr2 = st.columns([4, 2])
with hdr1:
    st.markdown('<div class="section-title">Subscription Coverage Matrix</div>', unsafe_allow_html=True)
with hdr2:
    st.markdown('<div style="text-align:right;font-size:0.72rem;color:#5a6a88;">Click ▶ to expand and view individual storage accounts</div>', unsafe_allow_html=True)

display_cols = [c for c in ["SubscriptionName", "TotalAccounts", "WithPolicy", "WithoutPolicy", "CoveragePct"] if c in filtered_matrix.columns]
display_df = filtered_matrix[display_cols].rename(columns={
    "SubscriptionName": "SUBSCRIPTION NAME",
    "TotalAccounts":    "TOTAL ACCOUNTS",
    "WithPolicy":       "WITH POLICY",
    "WithoutPolicy":    "WITHOUT POLICY",
    "CoveragePct":      "% COVERAGE",
})

st.dataframe(display_df, use_container_width=True, hide_index=True, height=320)

# ── Footer ────────────────────────────────────────────────────────────────────
covered   = with_policy
uncovered = no_policy
st.markdown(f"""
<div class="dash-footer">
    <span>Showing {len(filtered_matrix)} subscriptions &nbsp;·&nbsp; Accounts: {total_accts} &nbsp;·&nbsp; Covered: {covered} &nbsp;·&nbsp; Uncovered: {uncovered}</span>
    <span>Tenant: {TENANT_ID[:8]}... &nbsp;·&nbsp; Azure Management API &nbsp;·&nbsp; Cached 5 min</span>
</div>
""", unsafe_allow_html=True)

# ── Filtered export ───────────────────────────────────────────────────────────
with st.expander("Export filtered data"):
    csv_filtered = display_df.to_csv(index=False).encode()
    st.download_button("⬇ Export Filtered CSV", csv_filtered, "storage_lifecycle_filtered.csv", "text/csv", key="exp_filtered")

    if not accts_df.empty:
        st.markdown("**Individual Storage Accounts**")
        acct_display = accts_df.copy()
        st.dataframe(acct_display, use_container_width=True, hide_index=True)
