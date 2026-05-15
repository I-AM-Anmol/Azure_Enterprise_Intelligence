import streamlit as st
import requests
import pandas as pd
import msal
import plotly.express as px

TENANT_ID    = "e240d61e-61e3-4c9e-ab90-8644b2f4d2a9"
WORKSPACE_ID = "eca3c81e-a968-42a5-899f-d8fc1a45ebec"
DATASET_ID   = "a1022686-d90e-4c03-b36d-cdafacdc3dbc"
CLIENT_ID    = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
AUTHORITY    = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES       = ["https://analysis.windows.net/powerbi/api/.default"]

st.set_page_config(page_title="Storage Lifecycle Dashboard", layout="wide")


def get_token():
    if "access_token" in st.session_state:
        return st.session_state["access_token"]

    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY)
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        st.error("Failed to start device flow.")
        st.stop()

    st.info(f"**Sign in required**\n\nGo to: {flow['verification_uri']}\n\nEnter code: `{flow['user_code']}`")
    with st.spinner("Waiting for authentication..."):
        result = app.acquire_token_by_device_flow(flow)

    if "access_token" not in result:
        st.error(f"Authentication failed: {result.get('error_description', 'Unknown error')}")
        st.stop()

    st.session_state["access_token"] = result["access_token"]
    st.rerun()


def strip_prefix(col: str) -> str:
    return col.split("[")[-1].rstrip("]") if "[" in col else col


@st.cache_data(ttl=300)
def fetch_table(token: str, dax: str) -> pd.DataFrame:
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
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df.columns = [strip_prefix(c) for c in df.columns]
    return df


def coverage_tier(pct: float) -> str:
    if pct >= 75:
        return "High"
    elif pct >= 50:
        return "Medium"
    elif pct > 0:
        return "Low"
    return "None"


token = get_token()

subs_df = fetch_table(token, "EVALUATE Subscriptions")
accts_df = fetch_table(token, "EVALUATE StorageAccounts")

if subs_df.empty or accts_df.empty:
    st.warning("No data returned from the semantic model.")
    st.stop()

# Normalise types
subs_df["CoveragePct"] = pd.to_numeric(subs_df.get("CoveragePct", 0), errors="coerce").fillna(0)
subs_df["CoverageTier"] = subs_df["CoveragePct"].apply(coverage_tier)
accts_df["HasPolicy"] = accts_df.get("HasPolicy", False).astype(bool)

# ── Row 1: KPIs ───────────────────────────────────────────────────────────────
st.title("Storage Lifecycle Dashboard")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Subscriptions", len(subs_df))
c2.metric("Storage Accounts", len(accts_df))
c3.metric("With Policy", int(accts_df["HasPolicy"].sum()))
c4.metric("Without Policy", int((~accts_df["HasPolicy"]).sum()))
avg_cov = subs_df["CoveragePct"].mean()
c5.metric("Overall Coverage", f"{avg_cov:.1f}%")

st.divider()

# ── Row 2: Charts ─────────────────────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    tier_counts = subs_df["CoverageTier"].value_counts().reset_index()
    tier_counts.columns = ["Tier", "Count"]
    color_map = {"High": "#2ecc71", "Medium": "#f39c12", "Low": "#e74c3c", "None": "#95a5a6"}
    fig_donut = px.pie(
        tier_counts, names="Tier", values="Count",
        title="Coverage Tier Distribution",
        hole=0.45,
        color="Tier", color_discrete_map=color_map,
    )
    st.plotly_chart(fig_donut, use_container_width=True)

with col_right:
    bar_df = subs_df.sort_values("CoveragePct", ascending=True)
    name_col = next((c for c in bar_df.columns if "name" in c.lower() or "id" in c.lower()), bar_df.columns[0])
    fig_bar = px.bar(
        bar_df, x="CoveragePct", y=name_col,
        orientation="h",
        title="Coverage % per Subscription",
        color="CoveragePct",
        color_continuous_scale=["#e74c3c", "#f39c12", "#2ecc71"],
        range_color=[0, 100],
        labels={"CoveragePct": "Coverage %", name_col: "Subscription"},
    )
    fig_bar.update_layout(coloraxis_showscale=False, yaxis_title="")
    st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# ── Row 3: Accounts without policy ───────────────────────────────────────────
st.subheader("Storage Accounts Without Lifecycle Policy")

no_policy = accts_df[~accts_df["HasPolicy"]].copy()

filter_cols = st.columns(2)
sub_options = sorted(no_policy["SubscriptionId"].dropna().unique()) if "SubscriptionId" in no_policy.columns else []
loc_options = sorted(no_policy["Location"].dropna().unique()) if "Location" in no_policy.columns else []

with filter_cols[0]:
    sel_subs = st.multiselect("Subscription", sub_options)
with filter_cols[1]:
    sel_locs = st.multiselect("Location", loc_options)

filtered = no_policy.copy()
if sel_subs:
    filtered = filtered[filtered["SubscriptionId"].isin(sel_subs)]
if sel_locs:
    filtered = filtered[filtered["Location"].isin(sel_locs)]

display_cols = [c for c in ["AccountName", "SubscriptionId", "ResourceGroup", "Location", "Kind", "SKU"] if c in filtered.columns]
st.dataframe(filtered[display_cols] if display_cols else filtered, use_container_width=True)

st.divider()

# ── Row 4: Full subscriptions table ──────────────────────────────────────────
with st.expander("All Subscriptions"):
    show_cols = [c for c in subs_df.columns if c != "CoverageTier"]
    display_subs = subs_df[show_cols].copy()
    if "CoveragePct" in display_subs.columns:
        display_subs["CoveragePct"] = display_subs["CoveragePct"].apply(lambda x: f"{x:.1f}%")
    display_subs["CoverageTier"] = subs_df["CoverageTier"]
    st.dataframe(display_subs, use_container_width=True)

st.caption("Data source: StorageLifecyclePBI semantic model · Cached 5 min")
