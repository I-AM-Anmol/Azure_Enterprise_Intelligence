import streamlit as st
import base64
from pathlib import Path

st.set_page_config(
    page_title="CloudLens — MedInsight FinOps",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Embed original logo (white text, transparent bg) as base64
_logo_path = Path(__file__).parent / "assets" / "cloudlens_logo.svg"
_logo_b64  = base64.b64encode(_logo_path.read_bytes()).decode() if _logo_path.exists() else None

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

/* ── Logo block ─────────────────────────────────────────────── */
.sb-logo-card {
    padding: 20px 14px 12px 14px;
}
.sb-logo-card img {
    width: 100%;
    max-width: 200px;
    height: auto;
    display: block;
}
.sb-divider {
    border: none;
    border-top: 1px solid #2a3f6f;
    margin: 8px 12px 4px 12px;
}

/* Reorder: UserContent (logo) sits above stSidebarNav (nav links) */
div[data-testid="stSidebarContent"] {
    display: flex !important;
    flex-direction: column !important;
}
div[data-testid="stSidebarNav"]         { order: 2 !important; }
div[data-testid="stSidebarUserContent"] { order: 1 !important; }

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
[data-testid="stSidebarNavLink"] span,
[data-testid="stSidebarNavLink"] svg {
    color: inherit !important;
}

/* ── Sidebar footer ─────────────────────────────────────────── */
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

# Inject logo into sidebar BEFORE pg.run() so it appears at top
if _logo_b64:
    with st.sidebar:
        st.markdown(
            f'<div class="sb-logo-card">'
            f'<img src="data:image/svg+xml;base64,{_logo_b64}" alt="CloudLens">'
            f'</div>'
            f'<hr class="sb-divider">',
            unsafe_allow_html=True,
        )

pg = st.navigation([
    st.Page("pages/0_Home.py",              title="Home",                    icon=":material/dashboard:", default=True),
    st.Page("pages/1_Storage_Lifecycle.py", title="Storage Lifecycle",       icon=":material/layers:"),
    st.Page("pages/2_Budget_Analysis.py",   title="Budget & Alert Analysis", icon=":material/bar_chart:"),
])

pg.run()
