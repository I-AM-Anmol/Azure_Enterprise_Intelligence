import streamlit as st

st.set_page_config(
    page_title="Azure BI Dashboards — MedInsight",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
#MainMenu, footer, [data-testid="stToolbar"] { display:none !important; }

.landing-banner {
    background: linear-gradient(135deg, #1e2a4a 0%, #0f1117 65%);
    border-radius: 12px; padding: 32px 36px 28px 36px; margin-bottom: 32px;
    border: 1px solid #2d3249;
}
.landing-title { font-size: 2rem; font-weight: 700; color: #fff; }
.landing-title span { color: #60b4ff; }
.landing-sub { font-size: 0.88rem; color: #64748b; margin-top: 8px; }

.dash-card {
    background: #1a1d27; border-radius: 12px;
    padding: 28px 24px 20px 24px; border: 1px solid #2d3249;
    border-top: 4px solid #3b82f6; height: 100%;
}
.dash-card.green { border-top-color: #22c55e; }
.dash-card-icon { font-size: 2.2rem; margin-bottom: 14px; }
.dash-card-title { font-size: 1.1rem; font-weight: 700; color: #e2e8f0; margin-bottom: 10px; }
.dash-card-desc { font-size: 0.82rem; color: #64748b; line-height: 1.65; margin-bottom: 16px; }

[data-testid="stPageLink"] a {
    background: #22263a !important;
    border: 1px solid #2d3249 !important;
    border-radius: 8px !important;
    color: #60b4ff !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    padding: 9px 16px !important;
    text-decoration: none !important;
    display: inline-block !important;
}
[data-testid="stPageLink"] a:hover {
    background: #1e2a4a !important;
    border-color: #3b82f6 !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="landing-banner">
  <div class="landing-title">Azure BI Dashboards &mdash; <span>MedInsight</span></div>
  <div class="landing-sub">MedInsight Production Tenant &nbsp;·&nbsp; Select a dashboard from the sidebar or below</div>
</div>
""", unsafe_allow_html=True)

c1, c2 = st.columns(2, gap="large")

with c1:
    st.markdown("""
<div class="dash-card">
  <div class="dash-card-icon">🗄️</div>
  <div class="dash-card-title">Storage Lifecycle Policy Coverage</div>
  <div class="dash-card-desc">
    Monitor Azure Blob Storage lifecycle policy adoption across all subscriptions.
    Drill into each subscription to see which storage accounts are covered and which are exposed.
  </div>
</div>
""", unsafe_allow_html=True)
    st.page_link("pages/1_Storage_Lifecycle.py", label="Open Storage Lifecycle →", use_container_width=True)

with c2:
    st.markdown("""
<div class="dash-card green">
  <div class="dash-card-icon">💰</div>
  <div class="dash-card-title">Azure Budget Analysis</div>
  <div class="dash-card-desc">
    Track Azure spend against monthly budgets across all subscriptions.
    View daily burn rates, projected month-end spend, and alert threshold status.
  </div>
</div>
""", unsafe_allow_html=True)
    st.page_link("pages/2_Budget_Analysis.py", label="Open Budget Analysis →", use_container_width=True)
