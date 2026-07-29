"""
Clinical No-Show Prediction Dashboard
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Streamlit app that:
  1. Trains a no-show prediction model on historical data
  2. Scores all upcoming scheduled appointments
  3. Stratifies risk into Low/Medium/High tiers
  4. Displays actionable operational dashboard for clinic coordinators

Run:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, classification_report
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
DATA_DIR = r"C:\Users\anmol.sharma\Desktop\2026 Hackathon work"
AVG_APPOINTMENT_REVENUE = 250  # USD lost per no-show
TODAY = pd.Timestamp("2026-07-29")

st.set_page_config(
    page_title="Clinical No-Show Prediction",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    appt = pd.read_csv(f"{DATA_DIR}/staging_appointment.csv", low_memory=False)
    pat  = pd.read_csv(f"{DATA_DIR}/staging_patient.csv", low_memory=False)

    # deduplicate patient rows — keep latest updated_at per patient_id
    pat = pat.sort_values("updated_at", ascending=False).drop_duplicates(
        subset=["patient_id"], keep="first"
    ).reset_index(drop=True)

    # merge
    df = appt.merge(pat, on="patient_id", how="left", suffixes=("", "_pat"))

    # parse dates (normalize all to tz-naive)
    df["appointment_date_parsed"] = pd.to_datetime(
        df["appointment_date"].replace("-", pd.NaT), errors="coerce", utc=True
    ).dt.tz_localize(None)
    df["created_date_parsed"] = pd.to_datetime(
        df["created_date"], errors="coerce", utc=True
    ).dt.tz_localize(None)

    # derived features
    df["lead_days"] = (
        df["appointment_date_parsed"] - df["created_date_parsed"]
    ).dt.days.clip(lower=0)

    df["day_of_week"] = df["appointment_date_parsed"].dt.dayofweek  # 0=Mon
    df["day_name"]    = df["appointment_date_parsed"].dt.day_name()

    # hour from appointment_time (HHMM integer)
    df["appointment_time_int"] = pd.to_numeric(df["appointment_time"], errors="coerce")
    df["hour"] = (df["appointment_time_int"] // 100).clip(lower=0, upper=23)

    # patient age
    dob = pd.to_datetime(df["date_of_birth"], errors="coerce", utc=True).dt.tz_localize(None)
    age_days = (df["appointment_date_parsed"] - dob).dt.days
    df["patient_age"] = pd.to_numeric(age_days / 365.25, errors="coerce").fillna(40).astype(int)

    # past no-show ratio per patient (rolling up to that row)
    df = df.sort_values(["patient_id", "appointment_date_parsed"]).reset_index(drop=True)
    df["is_noshow"] = (df["status"] == "No Show").astype(int)

    # cumulative history (shifted so current row doesn't include itself)
    df["cum_appts"]   = df.groupby("patient_id")["is_noshow"].cumcount()
    df["cum_noshows"] = df.groupby("patient_id")["is_noshow"].cumsum().shift(1).fillna(0)
    df["cum_appts"]   = df["cum_appts"].clip(lower=1)
    df["past_noshow_ratio"] = df["cum_noshows"] / df["cum_appts"]

    return df


df = load_data()

# ─────────────────────────────────────────────────────────────────────────────
# BUILD ML MODEL
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource
def train_model(_df):
    """Train gradient boosting on historical in-person appointments."""
    train_mask = (
        (_df["prediction_eligible"] == True) &
        (_df["status"].isin(["Completed", "No Show"]))
    )
    train_df = _df[train_mask].copy()

    features = [
        "lead_days", "day_of_week", "hour", "patient_age",
        "past_noshow_ratio", "distance_to_clinic_miles",
        "sms_reminder_enrolled", "insurance_encoded",
        "category_encoded",
    ]

    # encode categoricals
    train_df["insurance_encoded"] = train_df["insurance_type"].map(
        {"Private": 0, "Medicare": 1, "Medicaid": 2, "Self-Pay": 3}
    ).fillna(0).astype(int)

    train_df["category_encoded"] = train_df["appointment_category"].astype("category").cat.codes

    train_df["sms_reminder_enrolled"] = train_df["sms_reminder_enrolled"].map(
        {True: 1, False: 0, "True": 1, "False": 0}
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

    model = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.1,
        subsample=0.8,
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_pred_proba = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_pred_proba)

    # feature importances
    feat_imp = dict(zip(features, model.feature_importances_))

    return model, features, auc, feat_imp


# prepare encoding mappings (needed for scoring)
df["insurance_encoded"] = df["insurance_type"].map(
    {"Private": 0, "Medicare": 1, "Medicaid": 2, "Self-Pay": 3}
).fillna(0).astype(int)

df["category_encoded"] = df["appointment_category"].astype("category").cat.codes

df["sms_reminder_enrolled"] = df["sms_reminder_enrolled"].map(
    {True: 1, False: 0, "True": 1, "False": 0}
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
    (df["prediction_eligible"].isin([True, "True"])) &
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
        bins=[0, 0.30, 0.70, 1.0],
        labels=["Low Risk", "Medium Risk", "High Risk"],
        include_lowest=True,
    )
else:
    upcoming["noshow_probability"] = []
    upcoming["noshow_pct"] = []
    upcoming["risk_tier"] = []

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/color/96/hospital-3.png", width=60)
    st.title("No-Show Predictor")
    st.caption("Clinical Appointment Intelligence")
    st.divider()

    st.metric("Model AUC Score", f"{auc_score:.3f}")
    st.metric("Total Upcoming Appts", f"{len(upcoming):,}")

    st.divider()
    st.subheader("Filter")

    date_range = st.date_input(
        "Appointment date range",
        value=(TODAY.date(), (TODAY + timedelta(days=30)).date()),
        min_value=TODAY.date(),
        max_value=pd.Timestamp("2026-12-31").date(),
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

# apply filters
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
st.title("🏥 Clinical No-Show Prediction Dashboard")
st.caption(f"As of {TODAY.strftime('%B %d, %Y')} • Model trained on {len(df[df['status'].isin(['Completed','No Show'])]):,} historical visits")

# ── KPI ROW ────────────────────────────────────────────────────────────────────
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

n_high = len(filtered[filtered["risk_tier"] == "High Risk"])
n_med  = len(filtered[filtered["risk_tier"] == "Medium Risk"])
n_low  = len(filtered[filtered["risk_tier"] == "Low Risk"])
est_noshows = n_high * 0.78 + n_med * 0.48 + n_low * 0.15
est_cost    = est_noshows * AVG_APPOINTMENT_REVENUE

kpi1.metric("🔴 High Risk", f"{n_high}", help="No-show probability > 70%")
kpi2.metric("🟡 Medium Risk", f"{n_med}", help="No-show probability 30-70%")
kpi3.metric("🟢 Low Risk", f"{n_low}", help="No-show probability < 30%")
kpi4.metric("💰 Est. Revenue at Risk", f"${est_cost:,.0f}", help=f"Based on ${AVG_APPOINTMENT_REVENUE}/missed appt")

st.divider()

# ── RISK STRATIFICATION WORKFLOW ───────────────────────────────────────────────
st.subheader("Risk Stratification & Recommended Actions")

col_low, col_med, col_high = st.columns(3)

with col_low:
    st.markdown("""
    <div style="background-color:#4CAF50; padding:15px; border-radius:8px; color:white; text-align:center;">
        <h3 style="margin:0; color:white;">🟢 Low Risk</h3>
        <p style="margin:5px 0; font-size:24px; font-weight:bold;">&lt; 30%</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f"**{n_low} appointments** → Send standard 24hr SMS confirmation")

with col_med:
    st.markdown("""
    <div style="background-color:#FF9800; padding:15px; border-radius:8px; color:white; text-align:center;">
        <h3 style="margin:0; color:white;">🟡 Medium Risk</h3>
        <p style="margin:5px 0; font-size:24px; font-weight:bold;">30% – 70%</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f"**{n_med} appointments** → Interactive SMS/Email requiring CONFIRM or CANCEL")

with col_high:
    st.markdown("""
    <div style="background-color:#F44336; padding:15px; border-radius:8px; color:white; text-align:center;">
        <h3 style="margin:0; color:white;">🔴 High Risk</h3>
        <p style="margin:5px 0; font-size:24px; font-weight:bold;">&gt; 70%</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f"**{n_high} appointments** → Manual staff callback + waitlist overbooking")

st.divider()

# ── WEEKLY / DAILY APPOINTMENT COUNTS ──────────────────────────────────────────
st.subheader("📅 Appointment Volume — Weekly & Daily")

tab_weekly, tab_daily = st.tabs(["Weekly View", "Daily View"])

with tab_weekly:
    weekly = filtered.copy()
    weekly["week"] = weekly["appointment_date_parsed"].dt.isocalendar().week
    weekly["year_week"] = weekly["appointment_date_parsed"].dt.strftime("%Y-W%U")
    week_summary = weekly.groupby("year_week").agg(
        total_booked=("appointment_id", "count"),
        high_risk=("risk_tier", lambda x: (x == "High Risk").sum()),
        medium_risk=("risk_tier", lambda x: (x == "Medium Risk").sum()),
        low_risk=("risk_tier", lambda x: (x == "Low Risk").sum()),
    ).reset_index()
    st.dataframe(week_summary, use_container_width=True, hide_index=True)

    # chart
    chart_data = week_summary.melt(
        id_vars=["year_week"],
        value_vars=["high_risk", "medium_risk", "low_risk"],
        var_name="Risk Tier", value_name="Count"
    )
    st.bar_chart(
        chart_data.pivot(index="year_week", columns="Risk Tier", values="Count").fillna(0),
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
    total_upcoming = len(filtered)
    expected_noshows = int(est_noshows)
    total_loss = expected_noshows * AVG_APPOINTMENT_REVENUE

    st.metric("Predicted No-Shows (filtered period)", f"{expected_noshows}")
    st.metric("Estimated Revenue Loss", f"${total_loss:,.0f}")
    st.metric("Avg. Revenue per Appointment", f"${AVG_APPOINTMENT_REVENUE}")

with col_b:
    st.markdown("##### Savings With Risk-Based Intervention")
    # assume interventions reduce no-show by:
    # High risk: 40% reduction (manual calls)
    # Medium risk: 25% reduction (interactive SMS)
    # Low risk: 10% reduction (standard SMS)
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
    (df["prediction_eligible"].isin([True, "True"])) &
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
st.caption(
    "Built for Hackathon 2026 — Infinity Nexus Team | "
    f"Data: {len(df):,} appointment records, {df['patient_id'].nunique():,} unique patients | "
    f"Model: GradientBoosting (AUC={auc_score:.3f})"
)
