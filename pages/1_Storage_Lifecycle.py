import streamlit as st
import requests
import pandas as pd
import msal
from azure.identity import AzureCliCredential, ClientSecretCredential
import plotly.graph_objects as go
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import time
from streamlit_autorefresh import st_autorefresh

# ── Constants ─────────────────────────────────────────────────────────────────
_TB = 1 << 40   # 1 tebibyte in bytes (matches Azure Monitor byte output)

TENANT_ID    = "e240d61e-61e3-4c9e-ab90-8644b2f4d2a9"
WORKSPACE_ID = "eca3c81e-a968-42a5-899f-d8fc1a45ebec"
DATASET_ID   = "a1022686-d90e-4c03-b36d-cdafacdc3dbc"
CLIENT_ID    = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
AUTHORITY    = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES       = ["https://analysis.windows.net/powerbi/api/.default"]
TENANT_NAME  = "MedInsight Production Tenant"

# MedInsight tenant — used for Azure Monitor blob metrics
ARM_TENANT_ID = "b2e2e6d4-979f-4671-aa72-0f0c494a0173"
ARM_AUTHORITY = f"https://login.microsoftonline.com/{ARM_TENANT_ID}"
ARM_SCOPES    = ["https://management.azure.com/.default"]

TIER_COLORS = {
    "Hot":     "#f97316",
    "Cool":    "#3b82f6",
    "Cold":    "#7c3aed",
    "Archive": "#475569",
}

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
    border-radius:12px; padding:20px 28px 16px 28px; margin-bottom:20px;
    border:1px solid #bfdbfe;
}
.top-banner .dash-title { font-size:1.55rem; font-weight:700; color:#1e3a8a; line-height:1.3; }
.top-banner .dash-title span { color:#2563eb; }
.top-banner .dash-meta { display:flex; gap:18px; flex-wrap:wrap; margin-top:6px; }
.top-banner .dash-meta .m { font-size:0.73rem; color:#64748b; }
.top-banner .dash-meta .m::before { content:"● "; color:#2563eb; }

.kpi-card {
    background:#ffffff; border-radius:10px;
    padding:18px 20px; border-top:4px solid #2563eb;
    border-left:1px solid #e2e8f0; border-right:1px solid #e2e8f0; border-bottom:1px solid #e2e8f0;
    box-shadow:0 1px 4px rgba(0,0,0,0.06);
}
.kpi-card.green   { border-top-color:#16a34a; }
.kpi-card.red     { border-top-color:#dc2626; }
.kpi-card.hot     { border-top-color:#f97316; }
.kpi-card.cool    { border-top-color:#3b82f6; }
.kpi-card.cold    { border-top-color:#7c3aed; }
.kpi-card.archive { border-top-color:#475569; }
.kpi-icon  { font-size:1.4rem; margin-bottom:4px; }
.kpi-value { font-size:2.2rem; font-weight:700; color:#0f172a; line-height:1.1; }
.kpi-value.green   { color:#16a34a; }
.kpi-value.red     { color:#dc2626; }
.kpi-value.hot     { color:#f97316; }
.kpi-value.cool    { color:#3b82f6; }
.kpi-value.cold    { color:#7c3aed; }
.kpi-value.archive { color:#475569; }
.kpi-label { font-size:0.75rem; font-weight:700; color:#475569; text-transform:uppercase; letter-spacing:.06em; }
.kpi-sub   { font-size:0.71rem; color:#94a3b8; margin-top:2px; }

.section-label {
    font-size:0.95rem; font-weight:700; color:#1e293b;
    margin:18px 0 10px 0; padding-bottom:6px;
    border-bottom:2px solid #e2e8f0;
}

.tier-badge {
    display:inline-block; border-radius:4px; padding:2px 8px;
    font-size:0.7rem; font-weight:700; letter-spacing:.04em;
    margin-right:4px; color:#fff;
}
.tier-badge.hot     { background:#f97316; }
.tier-badge.cool    { background:#3b82f6; }
.tier-badge.cold    { background:#7c3aed; }
.tier-badge.archive { background:#475569; }

.blob-scan-box {
    background:#f8fafc; border:1.5px dashed #cbd5e1;
    border-radius:10px; padding:20px 24px;
    text-align:center; color:#64748b; font-size:0.85rem;
    margin:12px 0 20px 0;
}

.stDownloadButton > button {
    background:#2563eb !important; color:#fff !important;
    border:none !important; border-radius:6px !important;
    font-size:0.78rem !important; padding:7px 18px !important; font-weight:600 !important;
}
.stDownloadButton > button:hover { background:#1d4ed8 !important; }

.stButton > button {
    border-radius:6px !important; font-size:0.82rem !important;
    padding:7px 12px !important; border:1px solid #e2e8f0 !important;
    background:#ffffff !important; color:#374151 !important; font-weight:600 !important;
    text-align:left !important; justify-content:flex-start !important;
}
.stButton > button:hover { background:#eff6ff !important; color:#2563eb !important; border-color:#bfdbfe !important; }

[data-testid="stExpander"] {
    background:#ffffff !important; border-radius:8px !important;
    border:1px solid #e2e8f0 !important; margin-bottom:4px !important;
}

.dash-footer {
    font-size:0.7rem; color:#94a3b8;
    margin-top:24px; padding-top:10px;
    border-top:1px solid #e2e8f0;
    display:flex; justify-content:space-between;
}

/* Coverage matrix card — force white background on all layers */
[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stVerticalBlockBorderWrapper"] > div,
[data-testid="stVerticalBlockBorderWrapper"] > div > [data-testid="stVerticalBlock"],
[data-testid="stVerticalBlockBorderWrapper"] > div > [data-testid="stVerticalBlock"] > div {
    background-color: #ffffff !important;
}
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 12px !important;
    border: 1px solid #e2e8f0 !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important;
    padding: 4px 8px 8px 8px !important;
}

/* Center dataframe column headers */
[data-testid="stDataFrame"] th,
[data-testid="stDataFrameResizable"] th {
    text-align: center !important;
}

div[data-testid="stSegmentedControl"] { gap:0 !important; }
div[data-testid="stSegmentedControl"] > label { display:none !important; }
div[data-testid="stSegmentedControl"] button {
    border-radius:20px !important; font-size:0.78rem !important; font-weight:600 !important;
    padding:5px 18px !important; border:1.5px solid #e2e8f0 !important;
    background:#f8fafc !important; color:#475569 !important; margin:0 3px !important;
}
div[data-testid="stSegmentedControl"] button[aria-checked="true"] {
    background:#2563eb !important; border-color:#2563eb !important; color:#ffffff !important;
}
div[data-testid="stSegmentedControl"] button:hover {
    border-color:#93c5fd !important; color:#2563eb !important;
}
</style>
""", unsafe_allow_html=True)


# ── Power BI auth ─────────────────────────────────────────────────────────────
def get_token():
    # Streamlit Cloud: service principal via secrets
    # Configure in app secrets: [azure] client_id / client_secret / tenant_id
    try:
        az = st.secrets["azure"]
        cred = ClientSecretCredential(az["tenant_id"], az["client_id"], az["client_secret"])
        return cred.get_token("https://analysis.windows.net/powerbi/api/.default").token
    except (KeyError, FileNotFoundError):
        pass

    # Local dev: uses existing az login session
    try:
        cred = AzureCliCredential(tenant_id=TENANT_ID)
        return cred.get_token("https://analysis.windows.net/powerbi/api/.default").token
    except Exception as e:
        st.error(
            f"Authentication failed. Either configure **[azure]** secrets in Streamlit Cloud, "
            f"or run `az login --tenant {TENANT_ID}` locally. Error: {e}"
        )
        st.stop()


# ── ARM auth (MedInsight tenant for Azure Monitor metrics) ────────────────────
def get_arm_token():
    # Streamlit Cloud: MedInsight SP — must be in [azure_medinsight] secrets section,
    # separate from [azure] which holds the Milliman SP for Power BI.
    try:
        az = st.secrets["azure_medinsight"]
        cred = ClientSecretCredential(ARM_TENANT_ID, az["client_id"], az["client_secret"])
        return cred.get_token("https://management.azure.com/.default").token
    except (KeyError, FileNotFoundError):
        pass

    # Local dev: uses existing az login session
    try:
        cred = AzureCliCredential(tenant_id=ARM_TENANT_ID)
        return cred.get_token("https://management.azure.com/.default").token
    except Exception as e:
        st.error(f"ARM authentication failed. Run `az login --tenant {ARM_TENANT_ID}` locally. Error: {e}")
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────
def strip_prefix(col):
    return col.split("[")[-1].rstrip("]") if "[" in col else col


@st.cache_data(ttl=300)
def fetch_table(token, dax):
    t0   = time.time()
    url  = f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}/datasets/{DATASET_ID}/executeQueries"
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


def _fetch_sub_tiers(arm_token, sub_id, start_t, end_t):
    """Fetches BlobCapacity by tier for all storage accounts in one subscription."""
    hdrs = {"Authorization": f"Bearer {arm_token}"}
    rows = []
    try:
        sa_resp = requests.get(
            f"https://management.azure.com/subscriptions/{sub_id}"
            f"/providers/Microsoft.Storage/storageAccounts?api-version=2023-01-01",
            headers=hdrs, timeout=20,
        )
        if sa_resp.status_code != 200:
            return rows
        for sa in sa_resp.json().get("value", []):
            sa_id, sa_name, location = sa["id"], sa["name"], sa.get("location", "")
            m_resp = requests.get(
                f"https://management.azure.com{sa_id}/blobServices/default"
                f"/providers/microsoft.insights/metrics"
                f"?api-version=2023-10-01&metricnames=BlobCapacity"
                f"&aggregation=Average&interval=PT1H"
                f"&timespan={start_t}/{end_t}"
                f"&$filter=Tier eq '*'",
                headers=hdrs, timeout=20,
            )
            if m_resp.status_code != 200:
                continue
            tier_bytes = {}
            for ts in m_resp.json().get("value", [{}])[0].get("timeseries", []):
                tier = next(
                    (mv["value"] for mv in ts.get("metadatavalues", []) if mv["name"]["value"] == "tier"),
                    "Untiered",
                )
                pts = [d["average"] for d in ts.get("data", []) if d.get("average") is not None]
                if pts:
                    tier_bytes[tier] = tier_bytes.get(tier, 0.0) + pts[-1]
            total = sum(tier_bytes.values())
            if total > 0:
                rows.append({
                    "SubscriptionId":  sub_id,
                    "StorageAccount":  sa_name,
                    "Location":        location,
                    "Hot_TB":          round(tier_bytes.get("Hot",     0.0) / _TB, 6),
                    "Cool_TB":         round(tier_bytes.get("Cool",    0.0) / _TB, 6),
                    "Cold_TB":         round(tier_bytes.get("Cold",    0.0) / _TB, 6),
                    "Archive_TB":      round(tier_bytes.get("Archive", 0.0) / _TB, 6),
                    "Total_TB":        round(total / _TB, 6),
                })
    except Exception:
        pass
    return rows


def fetch_all_blob_tiers(arm_token, sub_ids):
    """
    Parallel fetch across all subscriptions.
    Cached in session_state for 30 min to avoid repeated ARM calls.
    """
    cache_key = "blob_tier_df"
    ts_key    = "blob_tier_ts"
    ttl       = 1800

    now = time.time()
    if (
        cache_key in st.session_state
        and ts_key in st.session_state
        and (now - st.session_state[ts_key]) < ttl
    ):
        return st.session_state[cache_key], False  # (df, is_fresh)

    end_t   = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    start_t = (datetime.utcnow() - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")

    all_rows = []
    prog     = st.progress(0, text="Fetching blob tier metrics…")
    total    = len(sub_ids)

    with ThreadPoolExecutor(max_workers=20) as executor:
        futs = {executor.submit(_fetch_sub_tiers, arm_token, sid, start_t, end_t): sid for sid in sub_ids}
        done = 0
        for fut in as_completed(futs):
            all_rows.extend(fut.result())
            done += 1
            prog.progress(done / total, text=f"Fetching blob tier metrics… {done}/{total}")

    prog.empty()
    df = pd.DataFrame(all_rows) if all_rows else pd.DataFrame(
        columns=["SubscriptionId", "StorageAccount", "Location",
                 "Hot_TB", "Cool_TB", "Cold_TB", "Archive_TB", "Total_TB"]
    )
    st.session_state[cache_key] = df
    st.session_state[ts_key]    = now
    return df, True  # (df, is_fresh)


# ── Load Power BI data ────────────────────────────────────────────────────────
token            = get_token()
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

# ── Detect columns ────────────────────────────────────────────────────────────
sub_name_col = next((c for c in subs_df.columns if "name" in c.lower()), subs_df.columns[0] if not subs_df.empty else "SubscriptionName")
sub_id_col   = next((c for c in subs_df.columns if "id" in c.lower() and "subscription" in c.lower()), None) or \
               next((c for c in subs_df.columns if "id" in c.lower()), None)

acct_name_col   = next((c for c in accts_df.columns if "account" in c.lower() and "name" in c.lower()), None) or \
                  next((c for c in accts_df.columns if "name" in c.lower()), accts_df.columns[0] if not accts_df.empty else "AccountName")
acct_sub_id_col = next((c for c in accts_df.columns if "subscription" in c.lower() and "id" in c.lower()), None) or \
                  next((c for c in accts_df.columns if "subscription" in c.lower()), None)
policy_col      = next((c for c in accts_df.columns if "policydisplay" in c.lower()), None) or \
                  next((c for c in accts_df.columns if "policy" in c.lower() and "display" in c.lower()), None) or \
                  next((c for c in accts_df.columns if "policy" in c.lower() and "name" in c.lower()), None)

# ── Build sub name lookup ─────────────────────────────────────────────────────
if not subs_df.empty and not accts_df.empty and sub_id_col and acct_sub_id_col:
    id_to_name = dict(zip(subs_df[sub_id_col].astype(str), subs_df[sub_name_col].astype(str)))
    accts_df["_SubName"]   = accts_df[acct_sub_id_col].astype(str).map(id_to_name).fillna(accts_df[acct_sub_id_col].astype(str))
    display_sub_col = "_SubName"
elif acct_sub_id_col:
    accts_df["_SubName"] = accts_df[acct_sub_id_col].astype(str)
    display_sub_col = "_SubName"
else:
    display_sub_col = None

# ── KPI values ────────────────────────────────────────────────────────────────
total_subs  = len(subs_df)  if not subs_df.empty  else 0
total_accts = len(accts_df) if not accts_df.empty else 0
with_policy = int(accts_df["HasPolicy"].sum())    if not accts_df.empty else 0
no_policy   = int((~accts_df["HasPolicy"]).sum()) if not accts_df.empty else 0
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

# ── KPI row 1 — Policy coverage ───────────────────────────────────────────────
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


# ═══════════════════════════════════════════════════════════════════════════════
# BLOB STORAGE TIER DISTRIBUTION
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
bt_title_col, bt_action_col = st.columns([7, 3])
with bt_title_col:
    st.markdown('<div class="section-label">Blob Storage Tier Distribution</div>', unsafe_allow_html=True)

# ── Collect sub IDs from semantic model for ARM queries ───────────────────────
arm_sub_ids = []
if not subs_df.empty and sub_id_col:
    arm_sub_ids = subs_df[sub_id_col].dropna().astype(str).tolist()

blob_df = st.session_state.get("blob_tier_df", pd.DataFrame())

with bt_action_col:
    st.markdown("<div style='margin-top:18px'></div>", unsafe_allow_html=True)
    blob_loaded      = not blob_df.empty
    blob_ts          = st.session_state.get("blob_tier_ts", 0)
    blob_age_min     = round((time.time() - blob_ts) / 60, 1) if blob_ts else None
    blob_cache_label = f"⟳ Refresh  (cached {blob_age_min}m ago)" if blob_loaded else "⬇ Load Blob Tier Data"

    if st.button(blob_cache_label, key="load_blob_btn"):
        arm_token = get_arm_token()
        if arm_token and arm_sub_ids:
            st.session_state["arm_token"] = arm_token   # persist for use after rerun
            st.session_state.pop("blob_tier_df", None)  # force re-fetch
            st.session_state.pop("blob_tier_ts",  None)
            st.rerun()

# ── Auto-load if ARM token available and data not yet loaded ──────────────────
if not blob_loaded and "arm_token" in st.session_state and arm_sub_ids:
    arm_token   = st.session_state["arm_token"]
    blob_df, _  = fetch_all_blob_tiers(arm_token, arm_sub_ids)
    blob_loaded = not blob_df.empty

if not blob_loaded:
    col_connect, _ = st.columns([4, 6])
    with col_connect:
        st.markdown("""
        <div class="blob-scan-box">
            🔌 <strong>Azure Monitor not connected</strong><br>
            Click <em>Load Blob Tier Data</em> above to authenticate and scan all storage accounts across subscriptions.
            Results are cached for 30 minutes.
        </div>
        """, unsafe_allow_html=True)
else:
    # ── Apply subscription filter to blob data ────────────────────────────────
    # Build sub_id → sub_name map to filter blob_df by subscription name
    id_to_name_map = {}
    name_to_id_map = {}
    if not subs_df.empty and sub_id_col:
        id_to_name_map = dict(zip(subs_df[sub_id_col].astype(str), subs_df[sub_name_col].astype(str)))
        name_to_id_map = {v: k for k, v in id_to_name_map.items()}

    blob_df["SubscriptionName"] = blob_df["SubscriptionId"].map(id_to_name_map).fillna(blob_df["SubscriptionId"])

    # Apply the same subscription filter from the filter panel
    blob_filtered = blob_df.copy()
    if sel_subs:
        selected_ids = [name_to_id_map.get(n, n) for n in sel_subs]
        blob_filtered = blob_filtered[blob_filtered["SubscriptionId"].isin(selected_ids)]

    if blob_filtered.empty:
        st.info("No blob data matches the current subscription filter.")
    else:
        # ── KPI row 2 — Blob tier totals ──────────────────────────────────────
        total_tb   = round(blob_filtered["Total_TB"].sum(),   2)
        hot_tb     = round(blob_filtered["Hot_TB"].sum(),     2)
        cool_tb    = round(blob_filtered["Cool_TB"].sum(),    2)
        cold_tb    = round(blob_filtered["Cold_TB"].sum(),    2)
        archive_tb = round(blob_filtered["Archive_TB"].sum(), 2)
        hot_pct    = round(hot_tb     / total_tb * 100, 1) if total_tb else 0
        cool_pct   = round(cool_tb    / total_tb * 100, 1) if total_tb else 0
        cold_pct   = round(cold_tb    / total_tb * 100, 1) if total_tb else 0
        archive_pct = round(archive_tb / total_tb * 100, 1) if total_tb else 0

        b0, b1, b2, b3, b4 = st.columns(5)
        with b0:
            st.markdown(f"""<div class="kpi-card">
                <div class="kpi-icon">💾</div>
                <div class="kpi-value">{total_tb:,.0f}</div>
                <div class="kpi-label">Total Blob TB</div>
                <div class="kpi-sub">{blob_filtered['StorageAccount'].nunique()} accounts · {blob_filtered['SubscriptionId'].nunique()} subs</div>
            </div>""", unsafe_allow_html=True)
        with b1:
            st.markdown(f"""<div class="kpi-card hot">
                <div class="kpi-icon">🔥</div>
                <div class="kpi-value hot">{hot_tb:,.0f}</div>
                <div class="kpi-label">Hot Tier TB</div>
                <div class="kpi-sub">{hot_pct}% of total blob</div>
            </div>""", unsafe_allow_html=True)
        with b2:
            st.markdown(f"""<div class="kpi-card cool">
                <div class="kpi-icon">❄️</div>
                <div class="kpi-value cool">{cool_tb:,.0f}</div>
                <div class="kpi-label">Cool Tier TB</div>
                <div class="kpi-sub">{cool_pct}% of total blob</div>
            </div>""", unsafe_allow_html=True)
        with b3:
            st.markdown(f"""<div class="kpi-card cold">
                <div class="kpi-icon">🧊</div>
                <div class="kpi-value cold">{cold_tb:,.0f}</div>
                <div class="kpi-label">Cold Tier TB</div>
                <div class="kpi-sub">{cold_pct}% of total blob</div>
            </div>""", unsafe_allow_html=True)
        with b4:
            st.markdown(f"""<div class="kpi-card archive">
                <div class="kpi-icon">📦</div>
                <div class="kpi-value archive">{archive_tb:,.0f}</div>
                <div class="kpi-label">Archive Tier TB</div>
                <div class="kpi-sub">{archive_pct}% of total blob</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Charts row ────────────────────────────────────────────────────────
        chart_col, donut_col = st.columns([7, 3])

        # Stacked bar: top 30 subscriptions by total TB
        with chart_col:
            sub_agg = (
                blob_filtered
                .groupby("SubscriptionName")[["Hot_TB", "Cool_TB", "Cold_TB", "Archive_TB", "Total_TB"]]
                .sum()
                .sort_values("Total_TB", ascending=True)
            )
            # Show top 30 (most by total) — trim from the top if more
            if len(sub_agg) > 30:
                sub_agg = sub_agg.tail(30)

            fig_bar = go.Figure()
            for tier, col_name, color in [
                ("Hot",     "Hot_TB",     TIER_COLORS["Hot"]),
                ("Cool",    "Cool_TB",    TIER_COLORS["Cool"]),
                ("Cold",    "Cold_TB",    TIER_COLORS["Cold"]),
                ("Archive", "Archive_TB", TIER_COLORS["Archive"]),
            ]:
                fig_bar.add_trace(go.Bar(
                    name=tier,
                    x=sub_agg[col_name],
                    y=sub_agg.index,
                    orientation="h",
                    marker_color=color,
                    hovertemplate=(
                        f"<b>%{{y}}</b><br>{tier}: %{{x:.4f}} TB<extra></extra>"
                    ),
                ))
            fig_bar.update_layout(
                barmode="stack",
                title=dict(
                    text=f"Blob TB by Subscription — Top {len(sub_agg)} (stacked by tier)",
                    font=dict(size=13, color="#1e293b"),
                    x=0,
                ),
                xaxis=dict(title="TB", gridcolor="#f1f5f9", tickformat=".2f"),
                yaxis=dict(tickfont=dict(size=10), automargin=True),
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1, font=dict(size=11),
                ),
                plot_bgcolor="#ffffff",
                paper_bgcolor="#ffffff",
                margin=dict(l=10, r=10, t=50, b=10),
                height=max(320, len(sub_agg) * 22 + 80),
            )
            st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})

        # Donut: overall tier mix
        with donut_col:
            tier_totals = {
                "Hot":     hot_tb,
                "Cool":    cool_tb,
                "Cold":    cold_tb,
                "Archive": archive_tb,
            }
            # Only plot tiers with data
            active_tiers  = {t: v for t, v in tier_totals.items() if v > 0}
            if active_tiers:
                fig_donut = go.Figure(go.Pie(
                    labels=list(active_tiers.keys()),
                    values=list(active_tiers.values()),
                    hole=0.58,
                    marker=dict(colors=[TIER_COLORS[t] for t in active_tiers]),
                    textinfo="label+percent",
                    textfont=dict(size=12),
                    hovertemplate="<b>%{label}</b><br>%{value:.3f} TB<br>%{percent}<extra></extra>",
                    sort=False,
                ))
                fig_donut.add_annotation(
                    text=f"<b>{total_tb:,.1f}</b><br>TB Total",
                    x=0.5, y=0.5, font=dict(size=14, color="#0f172a"),
                    showarrow=False, align="center",
                )
                fig_donut.update_layout(
                    title=dict(
                        text="Overall Tier Distribution",
                        font=dict(size=13, color="#1e293b"), x=0,
                    ),
                    showlegend=True,
                    legend=dict(font=dict(size=11), orientation="v"),
                    plot_bgcolor="#ffffff",
                    paper_bgcolor="#ffffff",
                    margin=dict(l=10, r=10, t=50, b=10),
                    height=360,
                )
                st.plotly_chart(fig_donut, use_container_width=True, config={"displayModeBar": False})
            else:
                st.info("No tier data available for the selected subscriptions.")

        # ── Per-subscription tier table ───────────────────────────────────────
        with st.expander("Per-Subscription Blob Tier Breakdown", expanded=False):
            sub_tier_tbl = (
                blob_filtered
                .groupby("SubscriptionName")[["Hot_TB", "Cool_TB", "Cold_TB", "Archive_TB", "Total_TB"]]
                .sum()
                .reset_index()
                .sort_values("Total_TB", ascending=False)
            )
            sub_tier_tbl.columns = [
                "Subscription", "Hot (TB)", "Cool (TB)", "Cold (TB)", "Archive (TB)", "Total (TB)"
            ]
            for col in ["Hot (TB)", "Cool (TB)", "Cold (TB)", "Archive (TB)", "Total (TB)"]:
                sub_tier_tbl[col] = sub_tier_tbl[col].round(0).astype(int)
            st.dataframe(
                sub_tier_tbl,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Hot (TB)":     st.column_config.NumberColumn(format="%d TB"),
                    "Cool (TB)":    st.column_config.NumberColumn(format="%d TB"),
                    "Cold (TB)":    st.column_config.NumberColumn(format="%d TB"),
                    "Archive (TB)": st.column_config.NumberColumn(format="%d TB"),
                    "Total (TB)":   st.column_config.NumberColumn(format="%d TB"),
                },
            )
            csv_blob = sub_tier_tbl.to_csv(index=False).encode()
            st.download_button("⬇ Export Tier CSV", csv_blob, "blob_tier_distribution.csv", "text/csv", key="exp_blob")


# ═══════════════════════════════════════════════════════════════════════════════
# SUBSCRIPTION COVERAGE MATRIX
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("<br>", unsafe_allow_html=True)

with st.container(border=True):
    mc_title, mc_export = st.columns([6, 2])
    with mc_title:
        st.markdown('<div class="section-label" style="margin-top:4px">Subscription Coverage Matrix</div>', unsafe_allow_html=True)
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

        # Pre-build per-account tier lookup for expanders
        acct_tier_lookup = {}
        if blob_loaded and not blob_df.empty:
            for _, row in blob_df.iterrows():
                acct_tier_lookup[row["StorageAccount"]] = {
                    "Hot_TB":     row["Hot_TB"],
                    "Cool_TB":    row["Cool_TB"],
                    "Cold_TB":    row["Cold_TB"],
                    "Archive_TB": row["Archive_TB"],
                    "Total_TB":   row["Total_TB"],
                }

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
                cov_color = "#16a34a" if t_cov >= 75 else ("#ea580c" if t_cov >= 50 else "#dc2626")

                r1, r2, r3, r4, r5, r6 = st.columns([5, 3, 2, 2, 2, 2])
                with r1:
                    arrow = "▼" if st.session_state[exp_key] else "▶"
                    if st.button(f"{arrow} {cov_icon}  {sub_name}", key=f"_btn_{sub_name}", use_container_width=True):
                        st.session_state[exp_key] = not st.session_state[exp_key]
                r3.markdown(f"<div style='padding-top:6px;font-weight:700;color:#0f172a'>{t_total}</div>", unsafe_allow_html=True)
                r4.markdown(f"<div style='padding-top:6px;font-weight:700;color:#16a34a'>{t_with}</div>", unsafe_allow_html=True)
                r5.markdown(f"<div style='padding-top:6px;font-weight:700;color:#dc2626'>{t_without}</div>", unsafe_allow_html=True)
                r6.markdown(f"<div style='padding-top:6px;font-weight:700;color:{cov_color}'>{t_cov}%</div>", unsafe_allow_html=True)

                if st.session_state[exp_key]:
                    with st.container():
                        acct_rows = []
                        for _, row in grp.iterrows():
                            acct_nm     = row.get(acct_name_col, "—")
                            policy_disp = row.get(policy_col, "") if policy_col else ""
                            policy_disp = policy_disp if str(policy_disp).strip() not in ("", "nan", "None") \
                                          else ("Implemented" if row["HasPolicy"] else "Not Implemented")
                            status      = "✅ Implemented" if row["HasPolicy"] else "❌ Not Implemented"
                            acct_entry  = {
                                "Storage Account": acct_nm,
                                "Policy":          policy_disp,
                                "Status":          status,
                            }
                            if acct_nm in acct_tier_lookup:
                                t = acct_tier_lookup[acct_nm]
                                acct_entry["Hot (TB)"]     = t["Hot_TB"]
                                acct_entry["Cool (TB)"]    = t["Cool_TB"]
                                acct_entry["Cold (TB)"]    = t["Cold_TB"]
                                acct_entry["Archive (TB)"] = t["Archive_TB"]
                                acct_entry["Total (TB)"]   = t["Total_TB"]
                            acct_rows.append(acct_entry)

                        if acct_rows:
                            acct_tbl = pd.DataFrame(acct_rows)
                            col_cfg  = {}
                            for tc in ["Hot (TB)", "Cool (TB)", "Cold (TB)", "Archive (TB)", "Total (TB)"]:
                                if tc in acct_tbl.columns:
                                    col_cfg[tc] = st.column_config.NumberColumn(format="%d TB")
                            st.dataframe(acct_tbl, use_container_width=True, hide_index=True, column_config=col_cfg)
            else:
                sub_row  = subs_df[subs_df[sub_name_col] == sub_name] if not subs_df.empty else pd.DataFrame()
                t_cov    = float(sub_row["CoveragePct"].values[0]) if not sub_row.empty else 0
                cov_icon = "🟢" if t_cov >= 75 else ("🟡" if t_cov >= 50 else "🔴")
                r1, _, _, _, _, r6 = st.columns([5, 3, 2, 2, 2, 2])
                r1.markdown(f"<div style='padding-top:6px;color:#64748b'>&nbsp;&nbsp;{cov_icon} {sub_name}</div>", unsafe_allow_html=True)
                r6.markdown(f"<div style='padding-top:6px;color:#64748b'>{t_cov}%</div>", unsafe_allow_html=True)

            st.markdown("<hr style='margin:2px 0;opacity:0.4;border-color:#e2e8f0;'>", unsafe_allow_html=True)


# ── Footer ────────────────────────────────────────────────────────────────────
blob_footer = ""
if blob_loaded and blob_ts:
    refreshed_at = datetime.fromtimestamp(blob_ts).strftime("%H:%M:%S")
    blob_footer  = f" · Blob metrics: {blob_df['StorageAccount'].nunique()} accounts · Last fetched: {refreshed_at}"

st.markdown(f"""
<div class="dash-footer">
  <span>Showing {len(sub_list)} subscriptions · Accounts: {total_accts} · Covered: {with_policy} · Uncovered: {no_policy}{blob_footer}</span>
  <span>Tenant: {TENANT_ID[:8]}... · Power BI REST API · Cache: 5 min · Blob cache: 30 min · Auto-refresh: 5 min</span>
</div>
""", unsafe_allow_html=True)
