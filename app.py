import streamlit as st

st.set_page_config(
    page_title="Azure FinOps Command Center — MedInsight",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Sidebar navigation — this block runs on every page
with st.sidebar:
    st.markdown("""
<style>
[data-testid="stSidebarNav"] { display: none !important; }

[data-testid="stSidebarContent"] [data-testid="stPageLink"] a {
    display: flex !important;
    align-items: center !important;
    gap: 10px !important;
    padding: 9px 14px !important;
    border-radius: 8px !important;
    color: #c0d0e8 !important;
    font-size: 0.84rem !important;
    font-weight: 500 !important;
    text-decoration: none !important;
    background: transparent !important;
    border: none !important;
    transition: background 0.15s !important;
}
[data-testid="stSidebarContent"] [data-testid="stPageLink"] a:hover {
    background: #1e2a4a !important;
    color: #60b4ff !important;
}
[data-testid="stSidebarContent"] [data-testid="stPageLink"] a[aria-current="page"] {
    background: #1e2a4a !important;
    color: #60b4ff !important;
    font-weight: 700 !important;
}
</style>

<div style="padding:16px 8px 10px 8px;">
  <div style="font-size:0.72rem;font-weight:700;color:#4a6080;letter-spacing:.1em;text-transform:uppercase;margin-bottom:10px;">
    Navigation
  </div>
</div>
""", unsafe_allow_html=True)

    st.page_link("pages/0_Home.py",              label="Home",              icon="🏠")
    st.page_link("pages/1_Storage_Lifecycle.py", label="Storage Lifecycle", icon="🗄️")
    st.page_link("pages/2_Budget_Analysis.py",   label="Budget Analysis",   icon="💰")

    st.markdown("<hr style='border-color:#1e2d4a;margin:16px 0 8px 0;'>", unsafe_allow_html=True)
    st.markdown("""
<div style="font-size:0.7rem;color:#374a60;padding:0 8px;">
  MedInsight Production Tenant
</div>
""", unsafe_allow_html=True)

# Register pages (position="hidden" suppresses the default auto-nav in sidebar)
pg = st.navigation(
    [
        st.Page("pages/0_Home.py",              title="Home",              icon="🏠", default=True),
        st.Page("pages/1_Storage_Lifecycle.py", title="Storage Lifecycle", icon="🗄️"),
        st.Page("pages/2_Budget_Analysis.py",   title="Budget Analysis",   icon="💰"),
    ],
    position="hidden",
)
pg.run()
