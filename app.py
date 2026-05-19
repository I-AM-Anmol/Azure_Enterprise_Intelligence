import streamlit as st

st.set_page_config(
    page_title="Azure FinOps Command Center — MedInsight",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Global styles — applied on every page
st.markdown("""
<style>
/* Sidebar background — distinct from main page */
section[data-testid="stSidebar"] {
    background-color: #0d1226 !important;
    border-right: 1px solid #1e2d4a !important;
    min-width: 220px !important;
}

/* Hide the collapse button — sidebar always stays open */
[data-testid="stSidebarCollapseButton"] {
    display: none !important;
}
[data-testid="collapsedControl"] {
    display: none !important;
}

/* Nav links in sidebar */
[data-testid="stSidebarNavLink"] {
    border-radius: 8px !important;
    color: #c0d0e8 !important;
}
[data-testid="stSidebarNavLink"]:hover {
    background-color: #1e2a4a !important;
    color: #60b4ff !important;
}
[data-testid="stSidebarNavLink"][aria-current="page"] {
    background-color: #1e2a4a !important;
    color: #60b4ff !important;
    font-weight: 700 !important;
}
[data-testid="stSidebarNavLinkText"] {
    font-size: 0.85rem !important;
}
</style>
""", unsafe_allow_html=True)

pg = st.navigation([
    st.Page("pages/0_Home.py",              title="Home",              icon="🏠", default=True),
    st.Page("pages/1_Storage_Lifecycle.py", title="Storage Lifecycle", icon="🗄️"),
    st.Page("pages/2_Budget_Analysis.py",   title="Budget Analysis",   icon="💰"),
])

pg.run()
