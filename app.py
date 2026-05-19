import streamlit as st

st.set_page_config(
    page_title="Azure BI Dashboards — MedInsight",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="expanded",
)

pg = st.navigation([
    st.Page("pages/0_Home.py",              title="Home",               icon="🏠", default=True),
    st.Page("pages/1_Storage_Lifecycle.py", title="Storage Lifecycle",  icon="🗄️"),
    st.Page("pages/2_Budget_Analysis.py",   title="Budget Analysis",    icon="💰"),
])
pg.run()
