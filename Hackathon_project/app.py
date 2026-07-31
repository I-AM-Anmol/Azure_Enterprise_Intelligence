"""
Clinical No-Show Prediction Dashboard
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Streamlit app that:
  1. Connects to Power BI semantic model via Service Principal
  2. Pulls appointment + patient data using DAX queries
  3. Trains a no-show prediction model on historical data
  4. Scores upcoming scheduled appointments
  5. Displays actionable operational dashboard for clinic coordinators

Run:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
import os
import json
from datetime import datetime, timedelta
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
AVG_APPOINTMENT_REVENUE = 250  # USD lost per no-show
TODAY = pd.Timestamp.now().normalize()

# Power BI connection settings (from Streamlit secrets or env vars)
TENANT_ID     = st.secrets.get("azure", {}).get("tenant_id", os.getenv("TENANT_ID", ""))
CLIENT_ID     = st.secrets.get("azure", {}).get("client_id", os.getenv("CLIENT_ID", ""))
CLIENT_SECRET = st.secrets.get("azure", {}).get("client_secret", os.getenv("CLIENT_SECRET", ""))
WORKSPACE_NAME = "Clinical No-Show Prediction - Infinity Nexus"
DATASET_NAME   = "Appointment and Patient data"

# AI Chatbot (Groq - free tier, runs Llama models)
GROQ_API_KEY = st.secrets.get("groq", {}).get("api_key", os.getenv("GROQ_API_KEY", ""))

# Power Automate webhook for email notifications
POWER_AUTOMATE_URL = st.secrets.get("power_automate", {}).get("webhook_url", os.getenv("POWER_AUTOMATE_URL", ""))

st.set_page_config(
    page_title="Clinical No-Show Prediction",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM DARK THEME CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Global font */
html, body, [class*="css"] {
    font-family: 'Segoe UI', sans-serif;
}

/* Header bar — dark navy like Siemens top nav */
header[data-testid="stHeader"] {
    background-color: #1B2A4A !important;
}

/* Metric cards */
[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-left: 4px solid #00B8A9;
    border-radius: 8px;
    padding: 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
[data-testid="stMetric"] label {
    color: #64748B !important;
    font-size: 0.85rem !important;
}
[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: #1B2A4A !important;
    font-weight: 700 !important;
}

/* Buttons — teal */
.stButton > button {
    background-color: #00B8A9 !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 6px !important;
    padding: 0.6rem 1.2rem !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 2px 6px rgba(0,184,169,0.25) !important;
}
.stButton > button:hover {
    background-color: #009688 !important;
    box-shadow: 0 4px 12px rgba(0,184,169,0.4) !important;
    transform: translateY(-1px) !important;
}
.stButton > button:disabled {
    background-color: #E2E8F0 !important;
    color: #94A3B8 !important;
    box-shadow: none !important;
}

/* Sidebar — dark navy */
[data-testid="stSidebar"] {
    background-color: #1B2A4A !important;
    border-right: none;
}
[data-testid="stSidebar"] * {
    color: #E2E8F0 !important;
}
[data-testid="stSidebar"] [data-testid="stMetric"] {
    background: #243352 !important;
    border: 1px solid #34495E !important;
    border-left: 4px solid #00B8A9 !important;
}
[data-testid="stSidebar"] [data-testid="stMetric"] label {
    color: #94A3B8 !important;
}
[data-testid="stSidebar"] [data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] .stButton > button {
    background-color: #00B8A9 !important;
    color: #FFFFFF !important;
}
/* Sidebar inputs — visible text on dark background */
[data-testid="stSidebar"] [data-baseweb="input"] input,
[data-testid="stSidebar"] [data-baseweb="select"] span,
[data-testid="stSidebar"] [data-baseweb="select"] div,
[data-testid="stSidebar"] .stDateInput input,
[data-testid="stSidebar"] .stMultiSelect span,
[data-testid="stSidebar"] [data-testid="stMultiSelect"] span {
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] [data-baseweb="input"],
[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background-color: #243352 !important;
    border-color: #3D5A80 !important;
}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stSubheader,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span {
    color: #E2E8F0 !important;
}
[data-testid="stSidebar"] [data-baseweb="tag"] {
    background-color: #00B8A9 !important;
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] [data-baseweb="tag"] span {
    color: #FFFFFF !important;
}

/* Dataframes */
[data-testid="stDataFrame"] {
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    overflow: hidden;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
}
.stTabs [data-baseweb="tab"] {
    background-color: #F1F5F9;
    border-radius: 6px 6px 0 0;
    color: #64748B;
    padding: 8px 16px;
}
.stTabs [aria-selected="true"] {
    background-color: #1B2A4A !important;
    color: #FFFFFF !important;
}

/* Dividers */
hr {
    border-color: #E2E8F0 !important;
}

/* Headers — dark navy */
h1, h2, h3 {
    color: #1B2A4A !important;
    font-weight: 700 !important;
}

/* Captions */
.stCaption, [data-testid="stCaption"] {
    color: #64748B !important;
}

/* Expanders */
.streamlit-expanderHeader {
    background-color: #F1F5F9 !important;
    border-radius: 6px !important;
    color: #1B2A4A !important;
}
/* Sidebar expander (chatbot) */
[data-testid="stSidebar"] .streamlit-expanderHeader,
[data-testid="stSidebar"] [data-testid="stExpander"] summary {
    background-color: #243352 !important;
    border: 1px solid #3D5A80 !important;
    border-radius: 6px !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary span,
[data-testid="stSidebar"] [data-testid="stExpander"] summary p {
    color: #FFFFFF !important;
    font-weight: 600 !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
    background-color: #1F3155 !important;
    border: 1px solid #3D5A80 !important;
    border-top: none !important;
    border-radius: 0 0 6px 6px !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] .stCaption,
[data-testid="stSidebar"] [data-testid="stExpander"] p {
    color: #B0C4DE !important;
}
[data-testid="stSidebar"] [data-testid="stChatMessage"] {
    background-color: #243352 !important;
    border: 1px solid #3D5A80 !important;
    border-radius: 8px !important;
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] [data-testid="stChatMessage"] p,
[data-testid="stSidebar"] [data-testid="stChatMessage"] span {
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] [data-testid="stChatInput"] input,
[data-testid="stSidebar"] [data-testid="stChatInput"] textarea {
    background-color: #FFFFFF !important;
    color: #1B2A4A !important;
    border: 2px solid #00B8A9 !important;
    border-radius: 8px !important;
    font-size: 0.95rem !important;
}
[data-testid="stSidebar"] [data-testid="stChatInput"] input::placeholder,
[data-testid="stSidebar"] [data-testid="stChatInput"] textarea::placeholder {
    color: #64748B !important;
    opacity: 1 !important;
}
[data-testid="stSidebar"] [data-testid="stChatInput"] button {
    background-color: #00B8A9 !important;
    color: #FFFFFF !important;
}

/* Multiselect and inputs */
[data-baseweb="select"], [data-baseweb="input"] {
    border-color: #E2E8F0 !important;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# POWER BI AUTHENTICATION & DAX QUERY ENGINE
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def get_access_token():
    """Get Azure AD token for Power BI API using Service Principal."""
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "https://analysis.windows.net/powerbi/api/.default",
    }
    response = requests.post(url, data=payload)
    if response.status_code != 200:
        try:
            err_msg = response.json().get("error_description", response.text)
        except Exception:
            err_msg = response.text or f"HTTP {response.status_code} (empty response)"
        st.error(f"Authentication failed: {err_msg}")
        st.info("Please configure TENANT_ID, CLIENT_ID, and CLIENT_SECRET in Streamlit Cloud Secrets (Settings → Secrets).")
        st.stop()
    return response.json()["access_token"]


@st.cache_data(ttl=3600)
def get_dataset_id(_token):
    """Resolve workspace and dataset IDs from names."""
    headers = {"Authorization": f"Bearer {_token}"}

    # Get workspace (group) ID
    groups_url = "https://api.powerbi.com/v1.0/myorg/groups"
    resp = requests.get(groups_url, headers=headers)
    if resp.status_code != 200:
        st.error(f"Failed to list workspaces: {resp.text}")
        st.stop()

    groups = resp.json().get("value", [])
    workspace = next((g for g in groups if g["name"].strip() == WORKSPACE_NAME), None)
    if not workspace:
        st.error(f"Workspace '{WORKSPACE_NAME}' not found. Available: {[g['name'] for g in groups]}")
        st.stop()
    workspace_id = workspace["id"]

    # Get dataset ID
    datasets_url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets"
    resp = requests.get(datasets_url, headers=headers)
    if resp.status_code != 200:
        st.error(f"Failed to list datasets: {resp.text}")
        st.stop()

    datasets = resp.json().get("value", [])
    dataset = next((d for d in datasets if d["name"].strip() == DATASET_NAME), None)
    if not dataset:
        st.error(f"Dataset '{DATASET_NAME}' not found. Available: {[d['name'] for d in datasets]}")
        st.stop()

    return workspace_id, dataset["id"]


def execute_dax(token, workspace_id, dataset_id, dax_query):
    """Execute a DAX query against the semantic model and return a DataFrame."""
    url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/executeQueries"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = {
        "queries": [{"query": dax_query}],
        "serializerSettings": {"includeNulls": True},
    }
    resp = requests.post(url, headers=headers, json=body)
    if resp.status_code != 200:
        st.error(f"DAX query failed: {resp.text}")
        return pd.DataFrame()

    result = resp.json()
    rows = result["results"][0]["tables"][0]["rows"]
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# LOAD DATA FROM SEMANTIC MODEL
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=600)
def load_data():
    """Pull appointment and patient data from the Power BI semantic model."""

    token = get_access_token()
    workspace_id, dataset_id = get_dataset_id(token)

    # DAX: Get all appointments with prediction-relevant columns
    appt_dax = """
    EVALUATE
    SELECTCOLUMNS(
        staging_appointment,
        "appointment_id", [appointment_id],
        "patient_id", [patient_id],
        "appointment_date", [appointment_date],
        "appointment_time", [appointment_time],
        "appointment_duration", [appointment_duration],
        "created_date", [created_date],
        "status", [status],
        "appointment_category", [appointment_category],
        "appointment_subcategory", [appointment_subcategory],
        "reason_for_visit", [reason_for_visit],
        "cancellation_reason", [cancellation_reason],
        "department_id", [department_id],
        "requires_in_person", [requires_in_person],
        "prediction_eligible", [prediction_eligible]
    )
    """

    # DAX: Get patient demographics + model features
    patient_dax = """
    EVALUATE
    SELECTCOLUMNS(
        staging_patient,
        "patient_id", [patient_id],
        "first_name", [first_name],
        "last_name", [last_name],
        "date_of_birth", [date_of_birth],
        "gender", [gender],
        "sex", [sex],
        "race", [race],
        "ethnicity", [ethnicity],
        "primary_language", [primary_language],
        "city", [city],
        "state", [state],
        "zip_code", [zip_code],
        "insurance_type", [insurance_type],
        "sms_reminder_enrolled", [sms_reminder_enrolled],
        "distance_to_clinic_miles", [distance_to_clinic_miles],
        "preferred_communication_method", [preferred_communication_method]
    )
    """

    appt = execute_dax(token, workspace_id, dataset_id, appt_dax)
    pat  = execute_dax(token, workspace_id, dataset_id, patient_dax)

    if appt.empty or pat.empty:
        st.error("Failed to load data from semantic model.")
        st.stop()

    # Clean column names (DAX may prefix with table name)
    appt.columns = [c.split("[")[-1].rstrip("]") if "[" in c else c for c in appt.columns]
    pat.columns  = [c.split("[")[-1].rstrip("]") if "[" in c else c for c in pat.columns]

    # Deduplicate patients — keep one row per patient_id
    pat = pat.drop_duplicates(subset=["patient_id"], keep="first").reset_index(drop=True)

    # Merge
    df = appt.merge(pat, on="patient_id", how="left", suffixes=("", "_pat"))

    # Parse dates (normalize all to tz-naive)
    df["appointment_date_parsed"] = pd.to_datetime(
        df["appointment_date"], errors="coerce", utc=True
    ).dt.tz_localize(None)
    df["created_date_parsed"] = pd.to_datetime(
        df["created_date"], errors="coerce", utc=True
    ).dt.tz_localize(None)

    # Derived features
    df["lead_days"] = (
        df["appointment_date_parsed"] - df["created_date_parsed"]
    ).dt.days.clip(lower=0)

    df["day_of_week"] = df["appointment_date_parsed"].dt.dayofweek
    df["day_name"]    = df["appointment_date_parsed"].dt.day_name()

    df["appointment_time_int"] = pd.to_numeric(df["appointment_time"], errors="coerce")
    df["hour"] = (df["appointment_time_int"] // 100).clip(lower=0, upper=23)

    # Patient age
    dob = pd.to_datetime(df["date_of_birth"], errors="coerce", utc=True).dt.tz_localize(None)
    age_days = (df["appointment_date_parsed"] - dob).dt.days
    df["patient_age"] = pd.to_numeric(age_days / 365.25, errors="coerce").fillna(40).astype(int)

    # Past no-show ratio (cumulative, shifted)
    df = df.sort_values(["patient_id", "appointment_date_parsed"]).reset_index(drop=True)
    df["is_noshow"] = (df["status"] == "No Show").astype(int)
    df["cum_appts"]   = df.groupby("patient_id")["is_noshow"].cumcount().clip(lower=1)
    df["cum_noshows"] = df.groupby("patient_id")["is_noshow"].cumsum().shift(1).fillna(0)
    df["past_noshow_ratio"] = df["cum_noshows"] / df["cum_appts"]

    # Encode sms early so engineered features can use it
    df["sms_reminder_enrolled"] = df["sms_reminder_enrolled"].map(
        {True: 1, False: 0, "True": 1, "False": 0, "true": 1, "false": 0}
    ).fillna(0).astype(int)

    # Additional engineered features for better accuracy
    df["is_morning"] = (df["hour"] < 12).astype(int)
    df["is_monday"] = (df["day_of_week"] == 0).astype(int)
    df["is_friday"] = (df["day_of_week"] == 4).astype(int)
    df["long_lead"] = (df["lead_days"] > 14).astype(int)
    df["short_lead"] = (df["lead_days"] <= 2).astype(int)
    df["far_distance"] = (pd.to_numeric(df["distance_to_clinic_miles"], errors="coerce").fillna(15) > 20).astype(int)
    df["is_self_pay"] = (df["insurance_type"] == "Self-Pay").astype(int)
    df["no_sms"] = (1 - df["sms_reminder_enrolled"]).astype(int)
    df["total_past_appts"] = df.groupby("patient_id").cumcount()
    df["age_bucket"] = pd.cut(df["patient_age"], bins=[0, 25, 40, 60, 100], labels=[0, 1, 2, 3]).astype(float).fillna(1)
    df["risk_combo"] = df["past_noshow_ratio"] * df["lead_days"]

    return df


df = load_data()

# ─────────────────────────────────────────────────────────────────────────────
# BUILD ML MODEL
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource
def train_model(_df):
    """Train gradient boosting on historical in-person appointments."""
    train_mask = (
        (_df["prediction_eligible"].isin([True, "True", "true", 1, "1"])) &
        (_df["status"].isin(["Completed", "No Show"]))
    )
    train_df = _df[train_mask].copy()

    features = [
        "past_noshow_ratio", "risk_combo", "lead_days",
        "distance_to_clinic_miles", "patient_age",
        "total_past_appts", "hour", "day_of_week",
        "category_encoded", "insurance_encoded",
        "no_sms", "is_self_pay", "far_distance",
    ]

    # Encode categoricals
    train_df["insurance_encoded"] = train_df["insurance_type"].map(
        {"Private": 0, "Medicare": 1, "Medicaid": 2, "Self-Pay": 3}
    ).fillna(0).astype(int)

    train_df["category_encoded"] = train_df["appointment_category"].astype("category").cat.codes

    train_df["sms_reminder_enrolled"] = train_df["sms_reminder_enrolled"].map(
        {True: 1, False: 0, "True": 1, "False": 0, "true": 1, "false": 0}
    ).fillna(0).astype(int)

    train_df["distance_to_clinic_miles"] = pd.to_numeric(
        train_df["distance_to_clinic_miles"], errors="coerce"
    ).fillna(15)

    for f in features:
        train_df[f] = pd.to_numeric(train_df[f], errors="coerce").fillna(0)

    X = train_df[features]
    y = train_df["is_noshow"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = XGBClassifier(
        n_estimators=500, max_depth=6, learning_rate=0.05,
        subsample=0.85, colsample_bytree=0.7,
        min_child_weight=3, gamma=0.05,
        reg_alpha=0.1, reg_lambda=1.5,
        scale_pos_weight=len(y[y==0]) / max(len(y[y==1]), 1),
        eval_metric="auc", use_label_encoder=False,
        random_state=42, verbosity=0,
    )
    model.fit(X_train, y_train)

    y_pred_proba = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_pred_proba)
    feat_imp = dict(zip(features, model.feature_importances_))

    return model, features, auc, feat_imp


# Prepare encoding columns
df["insurance_encoded"] = df["insurance_type"].map(
    {"Private": 0, "Medicare": 1, "Medicaid": 2, "Self-Pay": 3}
).fillna(0).astype(int)

df["category_encoded"] = df["appointment_category"].astype("category").cat.codes

df["sms_reminder_enrolled"] = df["sms_reminder_enrolled"].map(
    {True: 1, False: 0, "True": 1, "False": 0, "true": 1, "false": 0}
).fillna(0).astype(int)

df["distance_to_clinic_miles"] = pd.to_numeric(
    df["distance_to_clinic_miles"], errors="coerce"
).fillna(15)

model, features, auc_score, feat_imp = train_model(df)

# ─────────────────────────────────────────────────────────────────────────────
# SCORE UPCOMING APPOINTMENTS
# ─────────────────────────────────────────────────────────────────────────────
scheduled_mask = (
    (df["status"] == "Scheduled") &
    (df["prediction_eligible"].isin([True, "True", "true", 1, "1"])) &
    (df["appointment_date_parsed"] >= TODAY)
)
upcoming = df[scheduled_mask].copy()

for f in features:
    upcoming[f] = pd.to_numeric(upcoming[f], errors="coerce").fillna(0)

if len(upcoming) > 0:
    upcoming["noshow_probability"] = model.predict_proba(upcoming[features])[:, 1]
    upcoming["noshow_pct"] = (upcoming["noshow_probability"] * 100).round(1)
    upcoming["risk_tier"] = pd.cut(
        upcoming["noshow_probability"],
        bins=[0, 0.30, 0.60, 1.0],
        labels=["Low Risk", "Medium Risk", "High Risk"],
        include_lowest=True,
    )
else:
    upcoming["noshow_probability"] = []
    upcoming["noshow_pct"] = []
    upcoming["risk_tier"] = []

# ─────────────────────────────────────────────────────────────────────────────
# POWER AUTOMATE HELPER FUNCTION
# ─────────────────────────────────────────────────────────────────────────────
def send_noshow_reminders(high_risk_df, webhook_url):
    """Send high-risk patient details to Power Automate for email notifications."""
    patients = []
    for _, row in high_risk_df.iterrows():
        patients.append({
            "patient_name": f"{row.get('first_name', '')} {row.get('last_name', '')}".strip(),
            "patient_email": "anmol.sharma@milliman.com",
            "appointment_date": pd.to_datetime(row["appointment_date_parsed"]).strftime("%B %d, %Y"),
            "appointment_time": str(row.get("appointment_time_int", "TBD")),
            "category": row.get("appointment_category", "General"),
            "reason": row.get("reason_for_visit", "Routine Visit"),
            "risk_score": round(float(row.get("noshow_pct", 0)), 1),
            "clinic_name": "Infinity Nexus Clinical Center",
        })

    payload = {"patients": patients, "total_count": len(patients), "sent_at": datetime.now().isoformat()}
    try:
        resp = requests.post(webhook_url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
        if resp.status_code in (200, 202, 204):
            return True, len(patients)
        else:
            return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return False, str(e)

# CHATBOT HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────
def get_data_summary(df_full, df_upcoming, df_filtered):
    """Build a concise data context for the chatbot."""
    total_appts = len(df_full)
    total_patients = df_full["patient_id"].nunique()
    upcoming_count = len(df_upcoming)
    hist_noshow_rate = df_full[df_full["status"].isin(["Completed", "No Show"])]["is_noshow"].mean() * 100

    high = len(df_filtered[df_filtered["risk_tier"] == "High Risk"]) if "risk_tier" in df_filtered.columns else 0
    med = len(df_filtered[df_filtered["risk_tier"] == "Medium Risk"]) if "risk_tier" in df_filtered.columns else 0
    low = len(df_filtered[df_filtered["risk_tier"] == "Low Risk"]) if "risk_tier" in df_filtered.columns else 0

    top_noshow_days = df_full[df_full["is_noshow"] == 1]["day_name"].value_counts().head(3).to_dict()
    top_noshow_categories = df_full[df_full["is_noshow"] == 1]["appointment_category"].value_counts().head(5).to_dict()
    avg_distance_high = df_filtered[df_filtered["risk_tier"] == "High Risk"]["distance_to_clinic_miles"].mean() if high > 0 else 0
    avg_distance_low = df_filtered[df_filtered["risk_tier"] == "Low Risk"]["distance_to_clinic_miles"].mean() if low > 0 else 0

    insurance_noshow = df_full[df_full["status"].isin(["Completed", "No Show"])].groupby("insurance_type")["is_noshow"].mean().to_dict()

    # Build patient-level detail for high and medium risk
    patient_details = ""
    if "noshow_pct" in df_filtered.columns and len(df_filtered) > 0:
        risk_df = df_filtered.sort_values("noshow_probability", ascending=False).head(50)
        rows = []
        for _, r in risk_df.iterrows():
            name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()
            date = pd.to_datetime(r.get("appointment_date_parsed")).strftime("%Y-%m-%d") if pd.notna(r.get("appointment_date_parsed")) else "N/A"
            cat = r.get("appointment_category", "N/A")
            reason = r.get("reason_for_visit", "N/A")
            risk_pct = r.get("noshow_pct", 0)
            tier = r.get("risk_tier", "N/A")
            insurance = r.get("insurance_type", "N/A")
            distance = r.get("distance_to_clinic_miles", 0)
            rows.append(f"  - {name} | Date: {date} | Category: {cat} | Reason: {reason} | Risk: {risk_pct}% ({tier}) | Insurance: {insurance} | Distance: {distance} mi")
        patient_details = "\n".join(rows)

    return f"""CLINICAL NO-SHOW PREDICTION DATA SUMMARY:
- Total historical appointments: {total_appts:,}
- Total unique patients: {total_patients:,}
- Upcoming scheduled appointments: {upcoming_count:,}
- Historical no-show rate: {hist_noshow_rate:.1f}%
- Model AUC: {auc_score:.3f}
- Current risk distribution: High={high}, Medium={med}, Low={low}
- Estimated revenue at risk: ${(high*0.78 + med*0.48 + low*0.15) * AVG_APPOINTMENT_REVENUE:,.0f}
- Top no-show days: {top_noshow_days}
- Top no-show categories: {top_noshow_categories}
- Avg distance (High Risk): {avg_distance_high:.1f} miles
- Avg distance (Low Risk): {avg_distance_low:.1f} miles
- No-show rate by insurance: {json.dumps({k: f'{v*100:.1f}%' for k,v in insurance_noshow.items()})}
- Average appointment revenue: ${AVG_APPOINTMENT_REVENUE}
- Risk thresholds: Low <30%, Medium 30-70%, High >70%
- Intervention strategy: High Risk = manual callback + overbooking, Medium = interactive SMS/Email, Low = standard 24hr SMS
- Key model features (by importance): {json.dumps({k: f'{v:.3f}' for k,v in sorted(feat_imp.items(), key=lambda x: -x[1])[:5]})}

UPCOMING APPOINTMENTS (Top 50 by risk, highest first):
{patient_details}
"""


def ask_groq(question, data_context):
    """Send a question to Groq API (Llama 3.1 8B) and return the response."""
    url = "https://api.groq.com/openai/v1/chat/completions"

    system_prompt = f"""You are a clinical operations AI assistant embedded in a No-Show Prediction Dashboard.
You help healthcare coordinators understand patient no-show patterns, risk predictions, and operational strategies.

Answer questions based on the data below. Be concise, actionable, and specific. Use numbers from the data.
If asked about a specific patient or scenario not in the summary, explain what data you'd need.
Format responses with bullet points or short paragraphs for readability.

{data_context}"""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        "temperature": 0.3,
        "max_tokens": 1024,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code == 200:
            result = resp.json()
            return result["choices"][0]["message"]["content"]
        else:
            return f"Error from Groq API: {resp.status_code} — {resp.text[:200]}"
    except Exception as e:
        return f"Failed to reach Groq API: {str(e)}"


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
import base64

_LOGO_SVG_RAW = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="100 50 200 110" width="80" height="44"><path d="M120 100 C120 60, 180 60, 200 100 C220 140, 280 140, 280 100 C280 60, 220 60, 200 100 C180 140, 120 140, 120 100 Z" fill="none" stroke="#00B8A9" stroke-width="6" stroke-linecap="round"/><circle cx="200" cy="100" r="12" fill="#00B8A9"/><circle cx="200" cy="100" r="6" fill="#FFFFFF"/><line x1="200" y1="88" x2="200" y2="70" stroke="#00B8A9" stroke-width="2" opacity="0.6"/><line x1="200" y1="112" x2="200" y2="130" stroke="#00B8A9" stroke-width="2" opacity="0.6"/><line x1="188" y1="96" x2="175" y2="83" stroke="#00B8A9" stroke-width="2" opacity="0.6"/><line x1="212" y1="96" x2="225" y2="83" stroke="#00B8A9" stroke-width="2" opacity="0.6"/><line x1="188" y1="104" x2="175" y2="117" stroke="#00B8A9" stroke-width="2" opacity="0.6"/><line x1="212" y1="104" x2="225" y2="117" stroke="#00B8A9" stroke-width="2" opacity="0.6"/><circle cx="200" cy="70" r="3" fill="#00B8A9" opacity="0.6"/><circle cx="200" cy="130" r="3" fill="#00B8A9" opacity="0.6"/><circle cx="175" cy="83" r="3" fill="#00B8A9" opacity="0.6"/><circle cx="225" cy="83" r="3" fill="#00B8A9" opacity="0.6"/><circle cx="175" cy="117" r="3" fill="#00B8A9" opacity="0.6"/><circle cx="225" cy="117" r="3" fill="#00B8A9" opacity="0.6"/></svg>"""
LOGO_B64 = base64.b64encode(_LOGO_SVG_RAW.encode()).decode()

with st.sidebar:
    st.markdown(f"""
    <div style="text-align:center; padding:15px 0;">
        <img src="data:image/svg+xml;base64,{LOGO_B64}" width="80" height="44" alt="Infinity Nexus"/>
        <h2 style="margin:5px 0 0; color:#00B8A9 !important; font-weight:700;">No-Show Predictor</h2>
        <p style="margin:0; color:#94A3B8 !important; font-size:0.85rem;">Clinical Appointment Intelligence</p>
    </div>
    """, unsafe_allow_html=True)

    # Refresh & Chatbot — right under the title
    if st.button("🔄 Refresh Data from Model", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    if GROQ_API_KEY:
        with st.expander("🤖 **No-Show Intelligence Assistant**", expanded=False):
            st.caption("Ask about no-show patterns, risks, or recommendations")

            if "chat_history" not in st.session_state:
                st.session_state.chat_history = []

            chat_container = st.container(height=400)
            with chat_container:
                for msg in st.session_state.chat_history:
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])

            if prompt := st.chat_input("Ask a question...", key="sidebar_chat"):
                st.session_state.chat_history.append({"role": "user", "content": prompt})
                with chat_container:
                    with st.chat_message("user"):
                        st.markdown(prompt)
                    with st.chat_message("assistant"):
                        with st.spinner("Analyzing..."):
                            data_context = get_data_summary(df, upcoming, upcoming)
                            response = ask_groq(prompt, data_context)
                            st.markdown(response)
                st.session_state.chat_history.append({"role": "assistant", "content": response})

            if st.session_state.chat_history:
                if st.button("🗑️ Clear Chat", use_container_width=True):
                    st.session_state.chat_history = []
                    st.rerun()
    else:
        st.info("💡 Add Groq API key to enable AI chatbot.")

    st.divider()

    st.metric("Model AUC Score", f"{auc_score*100:.1f}%")
    st.metric("Total Upcoming Appts", f"{len(upcoming):,}")
    st.caption(f"Data source: Power BI Semantic Model")
    st.caption(f"Workspace: {WORKSPACE_NAME}")

    st.divider()
    st.subheader("Filter")

    min_date = TODAY.date()
    max_date = (TODAY + timedelta(days=180)).date()
    date_range = st.date_input(
        "Appointment date range",
        value=(min_date, (TODAY + timedelta(days=30)).date()),
        min_value=min_date,
        max_value=max_date,
    )

    risk_filter = st.multiselect(
        "Risk tier",
        options=["Low Risk", "Medium Risk", "High Risk"],
        default=["Low Risk", "Medium Risk", "High Risk"],
    )

    category_filter = st.multiselect(
        "Appointment category",
        options=sorted(upcoming["appointment_category"].dropna().unique()),
        default=[],
    )

    st.divider()
    st.subheader("Model Features")
    imp_df = pd.DataFrame(
        sorted(feat_imp.items(), key=lambda x: -x[1]),
        columns=["Feature", "Importance"]
    )
    st.dataframe(imp_df, hide_index=True, use_container_width=True)


# Apply filters
filtered = upcoming.copy()
if date_range and len(date_range) == 2:
    filtered = filtered[
        (filtered["appointment_date_parsed"].dt.date >= date_range[0]) &
        (filtered["appointment_date_parsed"].dt.date <= date_range[1])
    ]
if risk_filter:
    filtered = filtered[filtered["risk_tier"].isin(risk_filter)]
if category_filter:
    filtered = filtered[filtered["appointment_category"].isin(category_filter)]


# ─────────────────────────────────────────────────────────────────────────────
# MAIN DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(f"""
<h1 style="margin-bottom:0; color:#1B2A4A !important; border-bottom:3px solid #00B8A9; padding-bottom:10px;">
    <img src="data:image/svg+xml;base64,{LOGO_B64}" width="36" height="20" style="vertical-align:middle; margin-right:8px;" alt=""/> Clinical No-Show Prediction Dashboard
</h1>
""", unsafe_allow_html=True)
st.caption(
    f"Live from Power BI Semantic Model • "
    f"As of {TODAY.strftime('%B %d, %Y')} • "
    f"Model trained on {len(df[df['status'].isin(['Completed','No Show'])]):,} historical visits"
)

# ── KPI ROW ────────────────────────────────────────────────────────────────────
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

n_high = len(filtered[filtered["risk_tier"] == "High Risk"])
n_med  = len(filtered[filtered["risk_tier"] == "Medium Risk"])
n_low  = len(filtered[filtered["risk_tier"] == "Low Risk"])
est_noshows = n_high * 0.78 + n_med * 0.48 + n_low * 0.15
est_cost    = est_noshows * AVG_APPOINTMENT_REVENUE

kpi1.metric("🔴 High Risk", f"{n_high}", help="No-show probability > 60%")
kpi2.metric("🟡 Medium Risk", f"{n_med}", help="No-show probability 30-60%")
kpi3.metric("🟢 Low Risk", f"{n_low}", help="No-show probability < 30%")
kpi4.metric("💰 Est. Revenue at Risk", f"${est_cost:,.0f}", help=f"Based on ${AVG_APPOINTMENT_REVENUE}/missed appt")

st.divider()

# ── RISK STRATIFICATION WORKFLOW ───────────────────────────────────────────────
st.subheader("Risk Stratification & Recommended Actions")

col_low, col_med, col_high = st.columns(3)

with col_low:
    st.markdown("""
    <div style="background:linear-gradient(135deg, #2E7D32, #43A047); padding:20px; border-radius:10px; color:white; text-align:center; box-shadow:0 4px 12px rgba(46,125,50,0.3);">
        <h3 style="margin:0; color:#FFFFFF; font-size:1rem; opacity:0.9;">🟢 Low Risk</h3>
        <p style="margin:8px 0 0; font-size:28px; font-weight:bold; color:#FFFFFF;">&lt; 30%</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f"**{n_low} appointments** → Standard 24hr SMS confirmation")

with col_med:
    st.markdown("""
    <div style="background:linear-gradient(135deg, #E65100, #F57C00); padding:20px; border-radius:10px; color:white; text-align:center; box-shadow:0 4px 12px rgba(230,81,0,0.3);">
        <h3 style="margin:0; color:#FFFFFF; font-size:1rem; opacity:0.9;">🟡 Medium Risk</h3>
        <p style="margin:8px 0 0; font-size:28px; font-weight:bold; color:#FFFFFF;">30% – 60%</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f"**{n_med} appointments** → Interactive SMS/Email: CONFIRM or CANCEL")

with col_high:
    st.markdown("""
    <div style="background:linear-gradient(135deg, #C62828, #E53935); padding:20px; border-radius:10px; color:white; text-align:center; box-shadow:0 4px 12px rgba(198,40,40,0.3);">
        <h3 style="margin:0; color:#FFFFFF; font-size:1rem; opacity:0.9;">🔴 High Risk</h3>
        <p style="margin:8px 0 0; font-size:28px; font-weight:bold; color:#FFFFFF;">&gt; 60%</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f"**{n_high} appointments** → Manual staff callback + waitlist overbooking")
    send_disabled = (n_high == 0) or (not POWER_AUTOMATE_URL)
    tooltip = "Configure Power Automate webhook URL in secrets" if not POWER_AUTOMATE_URL else f"Send reminder emails to {n_high} high-risk patients"
    if st.button(f"📧 Send Reminders ({n_high})", disabled=send_disabled, help=tooltip, use_container_width=True):
        high_risk_patients = filtered[filtered["risk_tier"] == "High Risk"]
        with st.spinner("Sending to Power Automate..."):
            success, result = send_noshow_reminders(high_risk_patients, POWER_AUTOMATE_URL)
        if success:
            st.success(f"✅ Reminders sent for {result} patients!")
        else:
            st.error(f"❌ Failed: {result}")

st.divider()

# ── WEEKLY / DAILY APPOINTMENT COUNTS ──────────────────────────────────────────
st.subheader("📅 Appointment Volume — Weekly & Daily")

tab_weekly, tab_daily = st.tabs(["Weekly View", "Daily View"])

with tab_weekly:
    weekly = filtered.copy()
    weekly["year_week"] = weekly["appointment_date_parsed"].dt.strftime("%Y-W%U")
    week_summary = weekly.groupby("year_week").agg(
        total_booked=("appointment_id", "count"),
        high_risk=("risk_tier", lambda x: (x == "High Risk").sum()),
        medium_risk=("risk_tier", lambda x: (x == "Medium Risk").sum()),
        low_risk=("risk_tier", lambda x: (x == "Low Risk").sum()),
    ).reset_index()
    st.dataframe(week_summary, use_container_width=True, hide_index=True)

    st.bar_chart(
        week_summary.set_index("year_week")[["high_risk", "medium_risk", "low_risk"]],
        color=["#F44336", "#FF9800", "#4CAF50"],
    )

with tab_daily:
    daily = filtered.copy()
    daily["date"] = daily["appointment_date_parsed"].dt.date
    day_summary = daily.groupby("date").agg(
        total_booked=("appointment_id", "count"),
        high_risk=("risk_tier", lambda x: (x == "High Risk").sum()),
        medium_risk=("risk_tier", lambda x: (x == "Medium Risk").sum()),
        low_risk=("risk_tier", lambda x: (x == "Low Risk").sum()),
    ).reset_index()
    day_summary = day_summary.sort_values("date").head(30)
    st.dataframe(day_summary, use_container_width=True, hide_index=True)

    st.bar_chart(
        day_summary.set_index("date")[["high_risk", "medium_risk", "low_risk"]],
        color=["#F44336", "#FF9800", "#4CAF50"],
    )

st.divider()

# ── DETAILED APPOINTMENT TABLE ─────────────────────────────────────────────────
st.subheader("📋 Upcoming Appointments — Risk Scored")

display_df = filtered[[
    "appointment_date_parsed", "appointment_time_int",
    "patient_id", "first_name", "last_name",
    "patient_age", "reason_for_visit",
    "appointment_category", "appointment_subcategory",
    "insurance_type", "distance_to_clinic_miles",
    "sms_reminder_enrolled", "past_noshow_ratio",
    "lead_days", "day_name",
    "noshow_pct", "risk_tier",
]].copy()

display_df.columns = [
    "Date", "Time (HHMM)", "Patient ID", "First Name", "Last Name",
    "Age", "Reason / Condition", "Category", "Subcategory",
    "Insurance", "Distance (mi)", "SMS Enrolled", "Past No-Show %",
    "Lead Days", "Day", "No-Show Prob %", "Risk Tier",
]

display_df["Past No-Show %"] = (display_df["Past No-Show %"] * 100).round(1)
display_df["Date"] = pd.to_datetime(display_df["Date"]).dt.strftime("%Y-%m-%d")
display_df["SMS Enrolled"] = display_df["SMS Enrolled"].map({1: "Yes", 0: "No"})
display_df = display_df.sort_values("No-Show Prob %", ascending=False)

def color_risk(val):
    if val == "High Risk":
        return "background-color: #FFCDD2; color: #B71C1C"
    elif val == "Medium Risk":
        return "background-color: #FFF3E0; color: #E65100"
    else:
        return "background-color: #E8F5E9; color: #1B5E20"

styled = display_df.style.map(color_risk, subset=["Risk Tier"])
st.dataframe(styled, use_container_width=True, hide_index=True, height=500)

st.divider()

# ── COST IMPACT ANALYSIS ──────────────────────────────────────────────────────
st.subheader("💰 No-Show Cost Impact Analysis")

col_a, col_b = st.columns(2)

with col_a:
    st.markdown("##### Estimated Losses Without Intervention")
    expected_noshows = int(est_noshows)
    total_loss = expected_noshows * AVG_APPOINTMENT_REVENUE

    st.metric("Predicted No-Shows (filtered period)", f"{expected_noshows}")
    st.metric("Estimated Revenue Loss", f"${total_loss:,.0f}")
    st.metric("Avg. Revenue per Appointment", f"${AVG_APPOINTMENT_REVENUE}")

with col_b:
    st.markdown("##### Savings With Risk-Based Intervention")
    saved_high = n_high * 0.78 * 0.40 * AVG_APPOINTMENT_REVENUE
    saved_med  = n_med  * 0.48 * 0.25 * AVG_APPOINTMENT_REVENUE
    saved_low  = n_low  * 0.15 * 0.10 * AVG_APPOINTMENT_REVENUE
    total_saved = saved_high + saved_med + saved_low

    st.metric("Recoverable Revenue", f"${total_saved:,.0f}",
              delta=f"{total_saved/max(total_loss,1)*100:.0f}% of loss recoverable")
    st.metric("High-Risk Callbacks Impact", f"${saved_high:,.0f}")
    st.metric("Medium-Risk SMS Impact", f"${saved_med:,.0f}")

st.divider()

# ── HISTORICAL NO-SHOW TRENDS ──────────────────────────────────────────────────
st.subheader("📈 Historical No-Show Rate Trend")

hist = df[
    (df["status"].isin(["Completed", "No Show"])) &
    (df["prediction_eligible"].isin([True, "True", "true", 1, "1"])) &
    (df["appointment_date_parsed"].notna())
].copy()
hist["year_month"] = hist["appointment_date_parsed"].dt.to_period("M").astype(str)

monthly_stats = hist.groupby("year_month").agg(
    total=("appointment_id", "count"),
    no_shows=("is_noshow", "sum"),
).reset_index()
monthly_stats["noshow_rate"] = (monthly_stats["no_shows"] / monthly_stats["total"] * 100).round(1)

st.line_chart(monthly_stats.set_index("year_month")["noshow_rate"], y_label="No-Show Rate (%)")

# ── RISK FACTORS BREAKDOWN ─────────────────────────────────────────────────────
st.subheader("🔍 Risk Factor Breakdown — High Risk Appointments")

if n_high > 0:
    high_risk_df = filtered[filtered["risk_tier"] == "High Risk"]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**By Insurance Type**")
        ins_dist = high_risk_df["insurance_type"].value_counts()
        st.bar_chart(ins_dist)

    with col2:
        st.markdown("**By Day of Week**")
        dow_dist = high_risk_df["day_name"].value_counts()
        st.bar_chart(dow_dist)

    with col3:
        st.markdown("**By Appointment Category**")
        cat_dist = high_risk_df["appointment_category"].value_counts()
        st.bar_chart(cat_dist)

    st.markdown("**Distance Distribution (High Risk vs Low Risk)**")
    dist_comparison = pd.DataFrame({
        "High Risk": high_risk_df["distance_to_clinic_miles"].describe(),
        "Low Risk": filtered[filtered["risk_tier"] == "Low Risk"]["distance_to_clinic_miles"].describe(),
    })
    st.dataframe(dist_comparison.T, use_container_width=True)
else:
    st.info("No high-risk appointments in the selected filter range.")





# ── FOOTER ─────────────────────────────────────────────────────────────────────
st.divider()
st.markdown(f"""
<div style="text-align:center; padding:20px 0; font-size:0.8rem;">
    <p style="margin:0; color:#1B2A4A;">Built for <span style="color:#00B8A9; font-weight:600;">Hackathon 2026</span> — <span style="color:#00B8A9; font-weight:600;">Infinity Nexus Team</span></p>
    <p style="margin:4px 0 0; color:#64748B;">
        {len(df):,} appointment records • {df['patient_id'].nunique():,} unique patients •
        XGBoost (AUC={auc_score:.3f}) • Power BI Semantic Model
    </p>
</div>
""", unsafe_allow_html=True)
