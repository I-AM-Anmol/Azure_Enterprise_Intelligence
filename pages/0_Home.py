import streamlit as st

st.markdown("""
<style>
#MainMenu, footer, [data-testid="stToolbar"] { display:none !important; }
section[data-testid="stSidebar"] { transform:translateX(0px) !important; display:block !important; visibility:visible !important; min-width:240px !important; }
[data-testid="stSidebarCollapseButton"] { display:none !important; }
[data-testid="collapsedControl"] { display:none !important; }

.landing-banner {
    background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
    border-radius: 12px; padding: 32px 36px 28px 36px; margin-bottom: 32px;
    border: 1px solid #bfdbfe;
}
.landing-title { font-size: 2rem; font-weight: 700; color: #1e3a8a; }
.landing-title span { color: #2563eb; }
.landing-sub { font-size: 0.88rem; color: #64748b; margin-top: 8px; }

.dash-card {
    background: #ffffff; border-radius: 12px;
    padding: 28px 24px 20px 24px; border: 1px solid #e2e8f0;
    border-top: 4px solid #2563eb; height: 100%;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.dash-card.green { border-top-color: #16a34a; }
.dash-card-icon { font-size: 2.2rem; margin-bottom: 14px; }
.dash-card-title { font-size: 1.1rem; font-weight: 700; color: #0f172a; margin-bottom: 10px; }
.dash-card-desc { font-size: 0.82rem; color: #64748b; line-height: 1.65; margin-bottom: 16px; }

.stButton > button {
    background: #2563eb !important;
    border: none !important;
    border-radius: 8px !important;
    color: #ffffff !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    padding: 9px 16px !important;
}
.stButton > button:hover {
    background: #1d4ed8 !important;
    color: #ffffff !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="landing-banner">
  <div class="landing-title">Azure FinOps Command Center &mdash; <span>MedInsight</span></div>
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
    if st.button("Open Storage Lifecycle →", use_container_width=True, key="btn_storage"):
        st.switch_page("pages/1_Storage_Lifecycle.py")

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
    if st.button("Open Budget Analysis →", use_container_width=True, key="btn_budget"):
        st.switch_page("pages/2_Budget_Analysis.py")
