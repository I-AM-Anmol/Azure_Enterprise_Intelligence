import streamlit as st

st.markdown("""
<style>
#MainMenu, footer, [data-testid="stToolbar"] { display:none !important; }
section[data-testid="stSidebar"] { background-color:#1a2744 !important; transform:translateX(0px) !important; display:block !important; visibility:visible !important; min-width:260px !important; }
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
.dash-card-icon { margin-bottom: 14px; }
.dash-card-icon svg { display: block; }
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
  <div class="landing-title">MedInsight <span>Cloud Intelligence</span></div>
  <div class="landing-sub">MedInsight Production Tenant &nbsp;·&nbsp; Select a dashboard from the sidebar or below</div>
</div>
""", unsafe_allow_html=True)

c1, c2 = st.columns(2, gap="large")

with c1:
    st.markdown("""
<div class="dash-card">
  <div class="dash-card-icon">
    <svg width="44" height="44" viewBox="0 0 44 44" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="44" height="44" rx="10" fill="#eff6ff"/>
      <!-- Database cylinder top -->
      <ellipse cx="22" cy="14" rx="10" ry="3.5" fill="#2563eb" opacity="0.85"/>
      <!-- Database body left/right sides -->
      <rect x="12" y="14" width="20" height="8" fill="#2563eb" opacity="0.7"/>
      <!-- Database cylinder mid -->
      <ellipse cx="22" cy="22" rx="10" ry="3.5" fill="#2563eb" opacity="0.85"/>
      <!-- Database body bottom -->
      <rect x="12" y="22" width="20" height="8" fill="#2563eb" opacity="0.55"/>
      <!-- Database cylinder bottom -->
      <ellipse cx="22" cy="30" rx="10" ry="3.5" fill="#2563eb"/>
      <!-- Shine on top -->
      <ellipse cx="18" cy="13" rx="3" ry="1.2" fill="white" opacity="0.35"/>
    </svg>
  </div>
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
  <div class="dash-card-icon">
    <svg width="44" height="44" viewBox="0 0 44 44" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="44" height="44" rx="10" fill="#f0fdf4"/>
      <!-- Bar chart bars -->
      <rect x="9"  y="30" width="5" height="8"  rx="1.5" fill="#16a34a" opacity="0.5"/>
      <rect x="17" y="23" width="5" height="15" rx="1.5" fill="#16a34a" opacity="0.7"/>
      <rect x="25" y="16" width="5" height="22" rx="1.5" fill="#16a34a" opacity="0.85"/>
      <!-- Trend arrow line -->
      <polyline points="9,28 17,20 25,14 35,10" stroke="#16a34a" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
      <!-- Arrow head -->
      <polyline points="30,9 35,10 34,15" stroke="#16a34a" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
    </svg>
  </div>
  <div class="dash-card-title">Azure Budget &amp; Alert Analysis</div>
  <div class="dash-card-desc">
    Track Azure spend against monthly budgets across all subscriptions.
    View daily burn rates, projected month-end spend, and alert threshold status.
  </div>
</div>
""", unsafe_allow_html=True)
    if st.button("Open Budget Analysis →", use_container_width=True, key="btn_budget"):
        st.switch_page("pages/2_Budget_Analysis.py")
