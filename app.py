import streamlit as st
from pathlib import Path

st.set_page_config(
    page_title="CloudLens — MedInsight FinOps",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CloudLens SVG logo
_logo_path = Path(__file__).parent / "assets" / "cloudlens_logo_C.svg"

# st.logo() is the reliable way to pin a logo above st.navigation() links
if _logo_path.exists():
    st.logo(str(_logo_path), size="large")

# Global styles — applied on every page
st.markdown("""
<style>
/* ── Sidebar container ──────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background-color: #1a2744 !important;
    border-right: 1px solid #2a3f6f !important;
    min-width: 260px !important;
    transform: translateX(0px) !important;
    display: block !important;
    visibility: visible !important;
}
[data-testid="stSidebarCollapseButton"] { display: none !important; }
[data-testid="collapsedControl"]        { display: none !important; }

/* Push main content away from sidebar */
.main .block-container { padding-left: 1rem !important; }


/* ── Nav links ──────────────────────────────────────────────── */
[data-testid="stSidebarNavLink"] {
    border-radius: 8px !important;
    color: #e2e8f0 !important;
    padding: 10px 14px !important;
    margin: 3px 10px !important;
    transition: background 0.15s ease !important;
}
[data-testid="stSidebarNavLink"]:hover {
    background-color: #243457 !important;
    color: #93c5fd !important;
}
[data-testid="stSidebarNavLink"][aria-current="page"] {
    background-color: #2563eb !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    box-shadow: 0 2px 8px rgba(37,99,235,0.4) !important;
}
[data-testid="stSidebarNavLinkText"] {
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    display: block !important;
    color: inherit !important;
}
/* Icon color inherits from parent link */
[data-testid="stSidebarNavLink"] span,
[data-testid="stSidebarNavLink"] svg {
    color: inherit !important;
}

/* ── Sidebar footer label ───────────────────────────────────── */
.sb-footer {
    padding: 14px 16px 8px 16px;
    font-size: 0.68rem;
    color: #4a6490;
    text-align: center;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    border-top: 1px solid #2a3f6f;
    margin-top: auto;
}
</style>
""", unsafe_allow_html=True)


pg = st.navigation([
    st.Page("pages/0_Home.py",              title="Home",                    icon=":material/dashboard:",  default=True),
    st.Page("pages/1_Storage_Lifecycle.py", title="Storage Lifecycle",       icon=":material/layers:"),
    st.Page("pages/2_Budget_Analysis.py",   title="Budget & Alert Analysis", icon=":material/bar_chart:"),
])

pg.run()
