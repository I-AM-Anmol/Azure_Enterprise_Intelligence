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

st_autorefresh(interval=300000)

# ── CSS: dark theme overrides ─────────────────────────────────────────────────
st.markdown("""
<style>
#MainMenu, footer, [data-testid="stToolbar"] { display:none !important; }
section[data-testid="stSidebar"] { transform:translateX(0px) !important; display:block !important; visibility:visible !important; min-width:240px !important; }
[data-testid="stSidebarCollapseButton"] { display:none !important; }
[data-testid="collapsedControl"] { display:none !important; }

/* Top banner */
.top-banner {
    background:linear-gradient(135deg,#0d1b3e 0%,#1a3060 100%);
    border-radius:12px; padding:20px 28px 16px 28px; margin-bottom:20px;
    border:1px solid #1e3a6e;
}
.top-banner .dash-title { font-size:1.55rem; font-weight:700; color:#ffffff; line-height:1.3; }
.top-banner .dash-title span { color:#60b4ff; }
.top-banner .dash-meta { display:flex; gap:18px; flex-wrap:wrap; margin-top:6px; }
.top-banner .dash-meta .m { font-size:0.73rem; color:#7aa8d8; }
.top-banner .dash-meta .m::before { content:"● "; color:#4da6ff; }

/* KPI cards */
.kpi-card {
    background:#131929; border-radius:10px;
    padding:18px 20px; border-top:4px solid #4da6ff;
    border-left:1px solid #1e2d4a; border-right:1px solid #1e2d4a; border-bottom:1px solid #1e2d4a;
}
.kpi-card.green { border-top-color:#2ecc71; }
.kpi-card.red   { border-top-color:#e74c3c; }
.kpi-icon  { font-size:1.4rem; margin-bottom:4px; }
.kpi-value { font-size:2.2rem; font-weight:700; color:#ffffff; line-height:1.1; }
.kpi-value.green { color:#2ecc71; }
.kpi-value.red   { color:#e74c3c; }
.kpi-label { font-size:0.75rem; font-weight:700; color:#8899bb; text-transform:uppercase; letter-spacing:.06em; }
.kpi-sub   { font-size:0.71rem; color:#4a5a78; margin-top:2px; }

/* Section label */
.section-label {
    font-size:0.95rem; font-weight:700; color:#c0d0e8;
    margin:18px 0 10px 0; padding-bottom:6px;
    border-bottom:2px solid #1e2d4a;
}

/* Buttons */
.stDownloadButton > button {
    background:#1565c0 !important; color:#fff !important;
    border:none !important; border-radius:6px !important;
    font-size:0.78rem !important; padding:7px 18px !important; font-weight:600 !important;
}
.stDownloadButton > button:hover { background:#1976d2 !important; }

.stButton > button {
    border-radius:6px !important; font-size:0.82rem !important;
    padding:7px 12px !important; border:1px solid #1e2d4a !important;
    background:#131929 !important; color:#c0d0e8 !important; font-weight:600 !important;
    text-align:left !important; justify-content:flex-start !important;
}
.stButton > button:hover { background:#1a2a45 !important; color:#4da6ff !important; border-color:#4da6ff !important; }

/* Expander */
[data-testid="stExpander"] {
    background:#131929 !important; border-radius:8px !important;
    border:1px solid #1e2d4a !important; margin-bottom:4px !important;
}

/* Footer */
.dash-footer {
    font-size:0.7rem; color:#4a5a78;
    margin-top:24px; padding-top:10px;
    border-top:1px solid #1e2d4a;
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
sub_name_col = next((c for c in subs_df.columns if "name" in c.lower()), subs_df.columns[0] if not subs_df.empty else "SubscriptionName")
sub_id_col   = next((c for c in subs_df.columns if "id" in c.lower() and "subscription" in c.lower()), None) or \
               next((c for c in subs_df.columns if "id" in c.lower()), None)

acct_name_col = next((c for c in accts_df.columns if "account" in c.lower() and "name" in c.lower()), None) or \
                next((c for c in accts_df.columns if "name" in c.lower()), accts_df.columns[0] if not accts_df.empty else "AccountName")
acct_sub_id_col = next((c for c in accts_df.columns if "subscription" in c.lower() and "id" in c.lower()), None) or \
                  next((c for c in accts_df.columns if "subscription" in c.lower()), None)
policy_col    = next((c for c in accts_df.columns if "policydisplay" in c.lower()), None) or \
                next((c for c in accts_df.columns if "policy" in c.lower() and "display" in c.lower()), None) or \
                next((c for c in accts_df.columns if "policy" in c.lower() and "name" in c.lower()), None)

# ── Build SubscriptionName lookup ─────────────────────────────────────────────
if not subs_df.empty and not accts_df.empty and sub_id_col and acct_sub_id_col:
    id_to_name = dict(zip(subs_df[sub_id_col].astype(str), subs_df[sub_name_col].astype(str)))
    accts_df["_SubName"] = accts_df[acct_sub_id_col].astype(str).map(id_to_name).fillna(accts_df[acct_sub_id_col].astype(str))
    display_sub_col = "_SubName"
elif acct_sub_id_col:
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

# ── Filter panel CSS ──────────────────────────────────────────────────────────
st.markdown("""
<style>
div[data-testid="stSegmentedControl"] { gap:0 !important; }
div[data-testid="stSegmentedControl"] > label { display:none !important; }
div[data-testid="stSegmentedControl"] button {
    border-radius:20px !important;
    font-size:0.78rem !important; font-weight:600 !important;
    padding:5px 18px !important;
    border:1.5px solid #2a3a55 !important;
    background:#0d1226 !important; color:#a0b8d8 !important;
    margin:0 3px !important;
}
div[data-testid="stSegmentedControl"] button[aria-checked="true"] {
    background:#1565c0 !important;
    border-color:#1565c0 !important;
    color:#ffffff !important;
}
div[data-testid="stSegmentedControl"] button:hover {
    border-color:#4da6ff !important; color:#4da6ff !important;
}
</style>
""", unsafe_allow_html=True)

# ── Filters ───────────────────────────────────────────────────────────────────
fr1, fr2, fr3 = st.columns(3)

with fr1:
    st.caption("SUBSCRIPTION")
    sub_options = sorted(accts_df[display_sub_col].dropna().unique().tolist()) if (not accts_df.empty and display_sub_col) else []
    sel_subs    = st.multiselect("", sub_options, label_visibility="collapsed",
                                 key="sub_filter", placeholder="Filter by subscription name...")

with fr2:
    st.caption("ACCOUNT NAME")
    acct_options = sorted(accts_df[acct_name_col].dropna().unique().tolist()) if not accts_df.empty else []
    sel_accts    = st.multiselect("", acct_options, label_visibility="collapsed",
                                  key="acct_filter", placeholder="Filter by account name...")

with fr3:
    st.caption("POLICY NAME")
    if policy_col and not accts_df.empty:
        pol_name_options = sorted(accts_df[policy_col].dropna().unique().tolist())
        pol_name_options = [p for p in pol_name_options if str(p).strip() not in ("", "nan", "None")]
    else:
        pol_name_options = []
    sel_policies = st.multiselect("", pol_name_options, label_visibility="collapsed",
                                  key="pol_filter", placeholder="Filter by policy name...")

st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)
ps1, ps2 = st.columns([2, 10])
with ps1:
    st.caption("POLICY STATUS")
with ps2:
    pf = st.segmented_control(
        "", ["All", "✓ Implemented", "✗ Not Implemented"],
        default="All", label_visibility="collapsed", key="policy_seg"
    )
    if pf is None:
        pf = "All"

if pf == "✓ Implemented":
    st.markdown('<span style="display:inline-block;background:#1e8e3e;color:#fff;border-radius:12px;padding:2px 12px;font-size:0.72rem;font-weight:600;margin-top:4px;">● Showing: ✓ Implemented only</span>', unsafe_allow_html=True)
elif pf == "✗ Not Implemented":
    st.markdown('<span style="display:inline-block;background:#c62828;color:#fff;border-radius:12px;padding:2px 12px;font-size:0.72rem;font-weight:600;margin-top:4px;">● Showing: ✗ Not Implemented only</span>', unsafe_allow_html=True)

# ── Apply filters ─────────────────────────────────────────────────────────────
filtered = accts_df.copy() if not accts_df.empty else pd.DataFrame()

if not filtered.empty:
    if sel_subs and display_sub_col:
        filtered = filtered[filtered[display_sub_col].isin(sel_subs)]
    if sel_accts:
        filtered = filtered[filtered[acct_name_col].isin(sel_accts)]
    if sel_policies and policy_col:
        filtered = filtered[filtered[policy_col].isin(sel_policies)]
    if pf == "✓ Implemented":
        filtered = filtered[filtered["HasPolicy"] == True]
    elif pf == "✗ Not Implemented":
        filtered = filtered[filtered["HasPolicy"] == False]

csv_all = filtered.to_csv(index=False).encode() if not filtered.empty else b""

# ── Subscription Coverage Matrix ──────────────────────────────────────────────
st.markdown("---")
mc_title, mc_export = st.columns([6, 2])
with mc_title:
    st.markdown('<div class="section-label">Subscription Coverage Matrix</div>', unsafe_allow_html=True)
with mc_export:
    st.download_button("⬇ Export CSV", csv_all, "storage_lifecycle_filtered.csv", "text/csv", key="exp_all")

if not filtered.empty and display_sub_col:
    sub_groups = filtered.groupby(display_sub_col)
    sub_list   = sorted(filtered[display_sub_col].dropna().unique().tolist())
else:
    sub_groups = None
    sub_list   = subs_df[sub_name_col].dropna().tolist() if not subs_df.empty else []

if not sub_list:
    st.info("No subscriptions match the current filters.")
else:
    h1, h2, h3, h4, h5, h6 = st.columns([5, 3, 2, 2, 2, 2])
    h1.markdown("**Subscription / Storage Account**")
    h2.markdown("**Policy Name**")
    h3.markdown("**Total**")
    h4.markdown("**With Policy**")
    h5.markdown("**Without Policy**")
    h6.markdown("**Coverage %**")
    st.markdown("<hr style='margin:4px 0;'>", unsafe_allow_html=True)

    for sub_name in sub_list:
        exp_key = f"_xp_{sub_name}"
        if exp_key not in st.session_state:
            st.session_state[exp_key] = False

        if sub_groups and sub_name in sub_groups.groups:
            grp       = sub_groups.get_group(sub_name)
            t_total   = len(grp)
            t_with    = int(grp["HasPolicy"].sum())
            t_without = t_total - t_with
            t_cov     = round(t_with / t_total * 100, 1) if t_total else 0
            cov_icon  = "🟢" if t_cov >= 75 else ("🟡" if t_cov >= 50 else "🔴")
            cov_color = "#2ecc71" if t_cov >= 75 else ("#f39c12" if t_cov >= 50 else "#e74c3c")

            r1, r2, r3, r4, r5, r6 = st.columns([5, 3, 2, 2, 2, 2])
            with r1:
                arrow = "▼" if st.session_state[exp_key] else "▶"
                if st.button(f"{arrow} {cov_icon}  {sub_name}", key=f"_btn_{sub_name}", use_container_width=True):
                    st.session_state[exp_key] = not st.session_state[exp_key]
            r3.markdown(f"<div style='padding-top:6px;font-weight:700;color:#e0e6f0'>{t_total}</div>", unsafe_allow_html=True)
            r4.markdown(f"<div style='padding-top:6px;font-weight:700;color:#2ecc71'>{t_with}</div>", unsafe_allow_html=True)
            r5.markdown(f"<div style='padding-top:6px;font-weight:700;color:#e74c3c'>{t_without}</div>", unsafe_allow_html=True)
            r6.markdown(f"<div style='padding-top:6px;font-weight:700;color:{cov_color}'>{t_cov}%</div>", unsafe_allow_html=True)

            if st.session_state[exp_key]:
                with st.container():
                    acct_rows = []
                    for _, row in grp.iterrows():
                        acct_nm      = row.get(acct_name_col, "—")
                        policy_disp  = row.get(policy_col, "") if policy_col else ""
                        policy_disp  = policy_disp if policy_disp and str(policy_disp).strip() not in ("", "nan", "None") else ("Implemented" if row["HasPolicy"] else "Not Implemented")
                        status       = "✅ Implemented" if row["HasPolicy"] else "❌ Not Implemented"
                        acct_rows.append({"Storage Account": acct_nm, "Policy": policy_disp, "Status": status})
                    if acct_rows:
                        st.dataframe(pd.DataFrame(acct_rows), use_container_width=True, hide_index=True)
        else:
            sub_row  = subs_df[subs_df[sub_name_col] == sub_name] if not subs_df.empty else pd.DataFrame()
            t_cov    = float(sub_row["CoveragePct"].values[0]) if not sub_row.empty else 0
            cov_icon = "🟢" if t_cov >= 75 else ("🟡" if t_cov >= 50 else "🔴")
            r1, _, _, _, _, r6 = st.columns([5, 3, 2, 2, 2, 2])
            r1.markdown(f"<div style='padding-top:6px;color:#8899bb'>&nbsp;&nbsp;{cov_icon} {sub_name}</div>", unsafe_allow_html=True)
            r6.markdown(f"<div style='padding-top:6px;color:#8899bb'>{t_cov}%</div>", unsafe_allow_html=True)

        st.markdown("<hr style='margin:2px 0;opacity:0.15;border-color:#1e2d4a;'>", unsafe_allow_html=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="dash-footer">
  <span>Showing {len(sub_list)} subscriptions · Accounts: {total_accts} · Covered: {with_policy} · Uncovered: {no_policy}</span>
  <span>Tenant: {TENANT_ID[:8]}... · Power BI REST API · Cache: 5 min · Auto-refresh: 5 min</span>
</div>
""", unsafe_allow_html=True)
