import streamlit as st

st.set_page_config(
    page_title="Azure FinOps Command Center — MedInsight",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Register pages — position="hidden" so we control the sidebar ourselves
pg = st.navigation(
    [
        st.Page("pages/0_Home.py",              title="Home",              icon="🏠", default=True),
        st.Page("pages/1_Storage_Lifecycle.py", title="Storage Lifecycle", icon="🗄️"),
        st.Page("pages/2_Budget_Analysis.py",   title="Budget Analysis",   icon="💰"),
    ],
    position="hidden",
)

# Sidebar navigation — runs on every page; uses buttons to avoid st.page_link bug in 1.57
with st.sidebar:
    st.markdown("""
<style>
.nav-label {
    font-size:0.72rem; font-weight:700; color:#4a6080;
    letter-spacing:.1em; text-transform:uppercase;
    padding:16px 4px 10px 4px;
}
div[data-testid="stSidebar"] .stButton > button {
    width:100% !important;
    background:transparent !important;
    border:none !important;
    border-radius:8px !important;
    color:#c0d0e8 !important;
    font-size:0.84rem !important;
    font-weight:500 !important;
    text-align:left !important;
    padding:9px 14px !important;
    justify-content:flex-start !important;
}
div[data-testid="stSidebar"] .stButton > button:hover {
    background:#1e2a4a !important;
    color:#60b4ff !important;
}
</style>
<div class="nav-label">Navigation</div>
""", unsafe_allow_html=True)

    if st.button("🏠  Home",               key="nav_home",    use_container_width=True):
        st.switch_page("pages/0_Home.py")
    if st.button("🗄️  Storage Lifecycle",  key="nav_storage", use_container_width=True):
        st.switch_page("pages/1_Storage_Lifecycle.py")
    if st.button("💰  Budget Analysis",    key="nav_budget",  use_container_width=True):
        st.switch_page("pages/2_Budget_Analysis.py")

    st.markdown("<hr style='border-color:#1e2d4a;margin:16px 0 8px 0;'>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:0.7rem;color:#374a60;padding:0 4px;'>MedInsight Production</div>",
                unsafe_allow_html=True)

pg.run()
