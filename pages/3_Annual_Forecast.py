try:
    import truststore
    truststore.inject_into_ssl()  # Windows cert store — fixes corporate proxy SSL interception
except ImportError:
    pass

import streamlit as st
import requests
import msal
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import base64
import numpy as np
import time
from datetime import datetime
from calendar import monthrange
from azure.identity import AzureCliCredential
from streamlit_autorefresh import st_autorefresh

# ── Configuration ──────────────────────────────────────────────────────────────
TENANT_ID            = "e240d61e-61e3-4c9e-ab90-8644b2f4d2a9"
WORKSPACE_ID         = "eca3c81e-a968-42a5-899f-d8fc1a45ebec"
WORKSPACE_NAME       = "MI - Azure Cost Analysis and FinOps Dashboard"
DATASET_ID           = "410b6252-6491-4970-889e-f9f31f1fc32d"
SEMANTIC_MODEL_NAME  = "MedInsight Azure Spend Analysis"
FORECAST_YEAR        = 2026
TENANT_NAME          = "MedInsight Production · Engineering · Milliman"

st_autorefresh(interval=300000)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
#MainMenu, footer, [data-testid="stToolbar"] { display:none !important; }
section[data-testid="stSidebar"] {
  background-color:#1a2744 !important; transform:translateX(0px) !important;
  display:block !important; visibility:visible !important; min-width:260px !important;
}
[data-testid="stSidebarCollapseButton"] { display:none !important; }
[data-testid="collapsedControl"]        { display:none !important; }

.top-banner {
  background: linear-gradient(100deg, #1a3a6e 0%, #1e4d8c 60%, #2255a4 100%);
  border-radius:12px; padding:22px 32px 18px 32px; margin-bottom:20px;
  box-shadow:0 4px 18px rgba(26,58,110,0.20); position:relative; overflow:hidden;
}
.top-banner::before {
  content:""; position:absolute; left:0; top:0; bottom:0; width:5px;
  background:linear-gradient(180deg,#60a5fa 0%,#2563eb 100%);
  border-radius:12px 0 0 12px;
}
.top-banner .dash-title { font-size:1.55rem; font-weight:700; color:#fff; line-height:1.3; }
.top-banner .dash-title span { color:#60a5fa; }
.top-banner .dash-meta { display:flex; gap:0; flex-wrap:wrap; margin-top:8px; align-items:center; }
.top-banner .dash-meta .m {
  font-size:0.73rem; color:rgba(255,255,255,0.55);
  padding-right:14px; margin-right:14px; border-right:1px solid rgba(255,255,255,0.15);
}
.top-banner .dash-meta .m:last-child { border-right:none; }

.kpi-card {
  background:#fff; border-radius:10px; padding:16px 18px;
  border:1px solid #e2e8f0; border-top:4px solid #2563eb;
  box-shadow:0 1px 4px rgba(0,0,0,0.06);
}
.kpi-card.red   { border-top-color:#dc2626; }
.kpi-card.green { border-top-color:#16a34a; }
.kpi-card.ora   { border-top-color:#ea580c; }
.kpi-card.pur   { border-top-color:#7c3aed; }
.kpi-lbl { font-size:0.68rem; font-weight:700; color:#64748b; text-transform:uppercase; letter-spacing:.06em; margin-bottom:5px; }
.kpi-val { font-size:1.9rem; font-weight:700; color:#0f172a; line-height:1.1; }
.kpi-val.red { color:#dc2626; } .kpi-val.grn { color:#16a34a; }
.kpi-val.ora { color:#ea580c; } .kpi-val.blu { color:#2563eb; }
.kpi-sub { font-size:0.71rem; color:#64748b; margin-top:3px; }

.section-label {
  font-size:0.95rem; font-weight:700; color:#1e293b;
  margin:18px 0 10px 0; padding-bottom:6px; border-bottom:2px solid #e2e8f0;
}
.source-tag {
  display:inline-block; font-size:10px; font-weight:600; padding:1px 7px;
  border-radius:4px; background:#eff6ff; color:#2563eb;
  border:1px solid #bfdbfe; margin-left:6px;
}
.source-tag.grn { background:#f0fdf4; color:#15803d; border-color:#86efac; }

.fg-wrap { overflow-x:auto; border-radius:8px; border:1px solid #e2e8f0; }
table.fg { width:100%; border-collapse:collapse; font-size:12px; }
table.fg thead tr { background:#f8fafc; border-bottom:2px solid #e2e8f0; }
table.fg th { padding:9px 12px; text-align:left; font-size:11px; font-weight:600;
              text-transform:uppercase; letter-spacing:.05em; color:#64748b; white-space:nowrap; }
table.fg th.num { text-align:right; }
table.fg td { padding:7px 12px; border-bottom:1px solid #f1f5f9; }
table.fg td.num { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
table.fg tr.row-actual   td { background:#f0fdf4; }
table.fg tr.row-current  td { background:#eff6ff; font-weight:600; }
table.fg tr.row-forecast td { background:#fafafa; color:#64748b; }
table.fg tr.row-over     td { background:#fef2f2; }
table.fg tr:hover td     { background:#f8fafc; }

.mtype-actual   { background:#dcfce7; color:#15803d; border-radius:4px; padding:1px 7px; font-size:10px; font-weight:600; display:inline-block; }
.mtype-current  { background:#dbeafe; color:#1d4ed8; border-radius:4px; padding:1px 7px; font-size:10px; font-weight:600; display:inline-block; }
.mtype-forecast { background:#f1f5f9; color:#64748b;  border-radius:4px; padding:1px 7px; font-size:10px; font-weight:600; display:inline-block; }

.acc-badge { display:inline-flex; align-items:center; padding:3px 10px; border-radius:20px;
             font-size:10px; font-weight:700; letter-spacing:.04em; white-space:nowrap; }
.acc-good  { background:#dcfce7; color:#16a34a; border:1px solid #86efac; }
.acc-ok    { background:#fef9c3; color:#ca8a04; border:1px solid #fde047; }
.acc-poor  { background:#fee2e2; color:#dc2626; border:1px solid #fca5a5; }

.method-box {
  background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px;
  padding:14px 16px; font-size:11px; color:#475569; line-height:1.7; margin-top:12px;
}
.dash-footer {
  font-size:0.7rem; color:#94a3b8; margin-top:24px; padding-top:10px;
  border-top:1px solid #e2e8f0; display:flex; justify-content:space-between; flex-wrap:wrap; gap:6px;
}
.stDownloadButton > button {
  background:#2563eb !important; color:#fff !important;
  border:none !important; border-radius:6px !important;
  font-size:0.78rem !important; padding:7px 18px !important; font-weight:600 !important;
}
</style>
""", unsafe_allow_html=True)


def _msal_sp_token(tenant_id, client_id, client_secret):
    """Acquire SP token via MSAL with a shared requests session (truststore already injected)."""
    session = requests.Session()
    app = msal.ConfidentialClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=client_secret,
        http_client=session,
    )
    result = app.acquire_token_for_client(
        scopes=["https://analysis.windows.net/powerbi/api/.default"]
    )
    if "access_token" in result:
        return result["access_token"]
    raise RuntimeError(result.get("error_description", str(result)))


def get_token():
    # SP via MSAL (works through corporate proxy thanks to truststore)
    try:
        az = st.secrets["azure"]
        token = _msal_sp_token(az["tenant_id"], az["client_id"], az["client_secret"])
        return token, "Service Principal", az["tenant_id"]
    except (KeyError, FileNotFoundError):
        pass
    except Exception as sp_err:
        st.warning(f"SP auth failed: `{sp_err}` — falling back to az login")

    # Fallback: az login session (local dev)
    try:
        cred = AzureCliCredential(tenant_id=TENANT_ID)
        token = cred.get_token("https://analysis.windows.net/powerbi/api/.default").token
        return token, "Azure CLI", TENANT_ID
    except Exception:
        pass

    st.error(
        "**Auth failed — no valid credential found.**\n\n"
        "Run `az login --tenant e240d61e-61e3-4c9e-ab90-8644b2f4d2a9` in your terminal, then refresh."
    )
    st.stop()


def strip_prefix(col):
    return col.split("[")[-1].rstrip("]") if "[" in col else col


def decode_token_claims(token):
    """Decode JWT payload without signature validation for diagnostics only."""
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return {}
        payload = parts[1]
        pad = "=" * (-len(payload) % 4)
        raw = base64.urlsafe_b64decode(payload + pad)
        return json.loads(raw.decode("utf-8", errors="ignore"))
    except Exception:
        return {}


@st.cache_data(ttl=900, show_spinner=False)
def resolve_dataset(token):
    """Resolve dataset ID in workspace, preferring semantic model name."""
    url = f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}/datasets"
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)

    if resp.status_code == 401:
        raise PermissionError(
            "Power BI API 401 while listing datasets. "
            "Your account/service principal is not authorized for this workspace."
        )
    if not resp.ok:
        raise RuntimeError(f"Could not list datasets ({resp.status_code}): {resp.text[:500]}")

    items = resp.json().get("value", [])
    if not items:
        raise RuntimeError("No semantic models found in the workspace.")

    by_name = {d.get("name", "").strip().lower(): d for d in items if d.get("name")}
    by_id = {d.get("id"): d for d in items if d.get("id")}

    preferred = by_name.get(SEMANTIC_MODEL_NAME.strip().lower())
    if preferred:
        return preferred["id"], preferred.get("name", SEMANTIC_MODEL_NAME)

    if DATASET_ID in by_id:
        ds = by_id[DATASET_ID]
        return ds["id"], ds.get("name", SEMANTIC_MODEL_NAME)

    available = ", ".join(sorted(by_name.keys())[:10])
    raise RuntimeError(
        f"Semantic model '{SEMANTIC_MODEL_NAME}' not found in workspace '{WORKSPACE_NAME}'. "
        f"Available models: {available if available else 'none'}"
    )


def _pbi_query(token, dax, dataset_id, timeout=60):
    url = (
        f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}"
        f"/datasets/{dataset_id}/executeQueries"
    )
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"queries": [{"query": dax}], "serializerSettings": {"includeNulls": True}},
        timeout=timeout,
    )
    if resp.status_code == 401:
        raise PermissionError(
            "Power BI API 401 for executeQueries. Ensure this identity has access to workspace "
            f"'{WORKSPACE_NAME}' and Build permission on semantic model '{SEMANTIC_MODEL_NAME}'. "
            f"Details: {resp.text[:500]}"
        )
    if not resp.ok:
        raise RuntimeError(f"PBI API {resp.status_code}: {resp.text[:800]}")
    rows = resp.json()["results"][0]["tables"][0].get("rows", [])
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df.columns = [strip_prefix(c) for c in df.columns]
    return df


# ── DAX — monthly spend with per-series breakdown for WLS regression ──────────
# Pulls: total, internal vs client split, key categories (Databricks, VM, Storage)
_DAX_SPEND = """
EVALUATE
SUMMARIZECOLUMNS(
    'Azure_Expense_Details'[Billing Period Start Date],
    'Azure_Expense_Details'[Complete_Month],
    "total_cost",      [Azure cost],
    "internal_cost",   CALCULATE([Azure cost], 'Azure_Expense_Details'[Client Name] = "MedInsight Internal"),
    "client_cost",     CALCULATE([Azure cost], 'Azure_Expense_Details'[Client Name] <> "MedInsight Internal"),
    "db_cost",         CALCULATE([Azure cost], 'Azure_Expense_Details'[MeterCategory] = "Azure Databricks"),
    "vm_cost",         CALCULATE([Azure cost], 'Azure_Expense_Details'[MeterCategory] = "Virtual Machines"),
    "storage_cost",    CALCULATE([Azure cost], 'Azure_Expense_Details'[MeterCategory] = "Storage"),
    "list_cost",       [List cost],
    "savings",         [Savings ($)]
)
ORDER BY 'Azure_Expense_Details'[Billing Period Start Date] ASC
"""

# ── DAX — Databricks reservation KPIs (scalar row) ────────────────────────────
_DAX_DB_KPIS = """
EVALUATE
ROW(
    "db_reservation_total",     [MedInsight Azure DataBricks Reservations],
    "db_consumed",              [DataBricks Consumed],
    "db_pct_consumed",          [% DataBricks Consumed (Starting August'24)],
    "db_remaining",             [Remaining DataBricks cost],
    "db_pct_remaining",         [% Remaining DataBricks Consumption],
    "db_projected_current",     [Projected Usage at current pace],
    "db_projected_required",    [Projected Usage at Required pace],
    "db_req_per_day",           [Databrick Comsumption Required per Day],
    "db_current_avg_per_day",   [DataBrick Current Average Consumption],
    "db_next30_required",       [Databricks next 30 days required consumption (Current Date)],
    "db_risk_current",          [DataBricks Res. Current pace- Risk/NO-Risk indicator],
    "db_risk_required",         [DataBricks Res. Required pace- Risk/NO-Risk indicator],
    "db_complete_days",         [Databricks Complete Day Count],
    "db_pending_days",          [Databricks Pending day count],
    "latest_date",              [Latest Date],
    "avg_mom_6m",               [Avg.MoM % Change (6 Mth)],
    "variance_30d_pct",         [30 Days Variance (%)],
    "current_cost_30d",         [Current Cost (30 Days)],
    "prior_cost_30d",           [Prior Cost (30 Days)]
)
"""


@st.cache_data(ttl=300, show_spinner=False)
def fetch_spend_data(token, dataset_id):
    t0 = time.time()
    try:
        df = _pbi_query(token, _DAX_SPEND, dataset_id)
    except Exception as exc:
        st.warning(f"Could not query Azure_Expense_Details: {exc}")
        return pd.DataFrame(), {}, round(time.time() - t0, 1), str(exc), {}

    if df.empty:
        return pd.DataFrame(), {}, round(time.time() - t0, 1), None, {}

    df.columns = [c.lower() for c in df.columns]
    for col in ["total_cost", "internal_cost", "client_cost", "db_cost", "vm_cost",
                "storage_cost", "list_cost", "savings"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        else:
            df[col] = 0.0
    df["billing period start date"]  = pd.to_datetime(df["billing period start date"], errors="coerce", utc=True)

    is_incomplete = df["complete_month"].str.strip() == "Incomplete"
    hist_df       = df[~is_incomplete].copy()
    inc_df        = df[is_incomplete]

    hist_df["usageyear"]  = hist_df["billing period start date"].dt.year.fillna(0).astype(int)
    hist_df["usagemonth"] = hist_df["billing period start date"].dt.month.fillna(0).astype(int)
    hist_df = hist_df[hist_df["usageyear"] > 0].sort_values(["usageyear", "usagemonth"])
    hist_df["days_in_month"] = hist_df.apply(
        lambda r: monthrange(int(r["usageyear"]), int(r["usagemonth"]))[1], axis=1
    )
    hist_df["days_with_data"] = hist_df["days_in_month"]  # completed months = full data

    today = datetime.now()
    live_row = {}
    if not inc_df.empty:
        r = inc_df.iloc[0]
        dim = monthrange(today.year, today.month)[1]
        live_row["currentmtd"]    = float(r["total_cost"])
        live_row["days_in_month"] = dim
        live_row["days_with_data"]= today.day - 1 or 1
        live_row["maxdate"]       = today.strftime("%Y-%m-%d")
    elif not hist_df.empty:
        live_row["currentmtd"]    = 0.0
        live_row["days_in_month"] = 0
        live_row["days_with_data"]= 0
        live_row["maxdate"]       = str(hist_df["billing period start date"].max())[:10]

    # Fetch Databricks KPIs
    db_kpis = {}
    try:
        db_df = _pbi_query(token, _DAX_DB_KPIS, dataset_id)
        if not db_df.empty:
            db_kpis = {c.lower(): db_df.iloc[0][c] for c in db_df.columns}
    except Exception:
        pass

    return hist_df, live_row, round(time.time() - t0, 1), None, db_kpis


# ── WLS helpers ────────────────────────────────────────────────────────────────
def _wls_fit(x, y, w):
    """Weighted Least Squares: linear trend y = a + b*x with quadratic weights."""
    W = np.diag(w)
    X = np.column_stack([np.ones_like(x), x])
    beta = np.linalg.inv(X.T @ W @ X) @ (X.T @ W @ y)
    yhat = X @ beta
    res  = y - yhat
    wrmse = float(np.sqrt(np.sum(w * res**2) / np.mean(w)))
    ss_res = float(np.sum(w * (y - yhat) ** 2))
    ss_tot = float(np.sum(w * (y - np.average(y, weights=w)) ** 2))
    r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0
    return float(beta[0]), float(beta[1]), wrmse, r2


def _wls_series(values):
    """Fit WLS to a list of (non-None) monthly values. Returns (intercept, slope, rmse, r2) or None."""
    clean = [v for v in values if v is not None and v > 0]
    if len(clean) < 2:
        return None
    n = len(clean)
    x = np.arange(1, n + 1, dtype=float)
    y = np.array(clean, dtype=float)
    w = (x ** 2).astype(float)
    w /= w.sum()
    return _wls_fit(x, y, w)


# ── Forecast engine (WLS regression) ──────────────────────────────────────────
def build_forecast(
    hist_df,
    live_row,
    today,
    monthly_budget,
    target_year,
    rolling_weight=None,   # kept for signature compat, unused
    burn_weight=None,
    conf_base=None,
    conf_step=None,
    portal_current_mtd=None,
):
    curr_yr = target_year
    curr_mo = today.month if target_year == today.year else 1

    current_actual  = float(live_row.get("currentmtd", 0) or 0)
    if portal_current_mtd is not None and portal_current_mtd > 0:
        current_actual = float(portal_current_mtd)
    days_in_curr_mo = int(live_row.get("days_in_month", monthrange(curr_yr, curr_mo)[1]))
    days_with_data  = int(live_row.get("days_with_data", today.day))
    days_remaining  = days_in_curr_mo - days_with_data
    current_burn    = (current_actual / days_with_data) if days_with_data > 0 and current_actual > 0 else 0
    projected_eom   = current_actual + current_burn * days_remaining
    if projected_eom <= 0 and current_actual > 0:
        projected_eom = current_actual

    # Build per-series lookups from all completed months (across all years)
    series_keys = ["total_cost", "internal_cost", "client_cost", "db_cost", "vm_cost", "storage_cost"]
    by_ym = {k: {} for k in series_keys}
    if not hist_df.empty:
        for _, row in hist_df.iterrows():
            key = (int(row["usageyear"]), int(row["usagemonth"]))
            for k in series_keys:
                by_ym[k][key] = float(row.get(k, 0) or 0)

    # Collect ALL completed months sorted chronologically for WLS fitting
    all_ym_sorted = sorted(by_ym["total_cost"].keys())

    # WLS fit per series using ALL historical completed months
    wls_params = {}
    for k in series_keys:
        vals = [by_ym[k].get(ym, 0) for ym in all_ym_sorted]
        result = _wls_series(vals)
        wls_params[k] = result  # (intercept, slope, rmse, r2) or None

    n_hist = len(all_ym_sorted)  # number of completed months used for fitting

    def wls_predict(k, steps_from_last):
        """Predict using WLS trend: x = n_hist + steps_from_last."""
        p = wls_params[k]
        if p is None:
            # fallback: mean of available values
            vals = list(by_ym[k].values())
            return float(np.mean(vals)) if vals else monthly_budget, monthly_budget * 0.15, 0.0
        a, b, rmse, r2 = p
        pred = a + b * (n_hist + steps_from_last)
        pred = max(pred, 0)
        return pred, rmse, r2

    # Rolling avg of last 3 completed months (for banner display only)
    completed_this_yr = [by_ym["total_cost"].get((curr_yr, m)) for m in range(1, curr_mo)
                         if (curr_yr, m) in by_ym["total_cost"]]
    completed_this_yr = [v for v in completed_this_yr if v is not None]
    if len(completed_this_yr) >= 3:
        rolling_avg = sum(completed_this_yr[-3:]) / 3
    elif completed_this_yr:
        rolling_avg = sum(completed_this_yr) / len(completed_this_yr)
    else:
        rolling_avg = monthly_budget

    month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    rows = []
    steps_from_last = 1  # increments for each future month

    for m in range(1, 13):
        dim   = monthrange(curr_yr, m)[1]
        label = f"{month_names[m-1]} {curr_yr}"

        if m < curr_mo:
            actual   = by_ym["total_cost"].get((curr_yr, m))
            row_type = "actual"
            forecast = actual
            lo = hi  = (actual, actual) if actual is not None else (None, None)
            lo, hi   = lo if isinstance(lo, tuple) else (lo, hi)
            burn_day = (actual / dim) if actual else None
            accuracy = None

        elif m == curr_mo and target_year == today.year:
            actual   = current_actual
            row_type = "current"
            forecast = projected_eom
            _, rmse, _ = wls_predict("total_cost", 0)
            lo = max(0, forecast - rmse)
            hi = forecast + rmse
            burn_day = current_burn
            accuracy = None
            steps_from_last = 1  # next month is 1 step beyond current

        else:
            pred, rmse, r2 = wls_predict("total_cost", steps_from_last)
            forecast = round(pred, 2)
            actual   = None
            row_type = "forecast"
            lo = max(0, round(forecast - rmse, 2))
            hi = round(forecast + rmse, 2)
            burn_day = current_burn if current_burn > 0 else None
            accuracy = None
            steps_from_last += 1

        rows.append({
            "month_num": m, "month_name": month_names[m-1], "year": curr_yr,
            "label": label, "type": row_type,
            "actual": actual, "budget": monthly_budget,
            "forecast": forecast, "lower": lo, "upper": hi,
            "burn_day": burn_day, "days_in_month": dim, "accuracy": None,
        })

    # Back-calculate forecast accuracy vs WLS for completed months
    for i, row in enumerate(rows):
        if row["type"] != "actual" or row["actual"] is None:
            continue
        # Use WLS prediction from the state at i-1 (i.e., steps_from_last = 1)
        idx_in_hist = next(
            (j for j, ym in enumerate(all_ym_sorted) if ym == (curr_yr, row["month_num"])), None
        )
        if idx_in_hist is None or idx_in_hist < 2:
            continue
        # Fit WLS on data up to (but not including) this month
        prior_vals = [by_ym["total_cost"].get(all_ym_sorted[j], 0) for j in range(idx_in_hist)]
        r = _wls_series(prior_vals)
        if r is None:
            continue
        a, b, _, _ = r
        implied = a + b * (idx_in_hist + 1)
        implied = max(implied, 0)
        if row["actual"] > 0:
            rows[i]["accuracy"] = round(100 - abs(row["actual"] - implied) / row["actual"] * 100, 1)

    # Per-series WLS diagnostics for display
    series_diag = {}
    for k in series_keys:
        p = wls_params[k]
        if p:
            a, b, rmse, r2 = p
            series_diag[k] = {"slope": b, "rmse": rmse, "r2": r2}

    meta = {
        "monthly_budget":   monthly_budget,
        "annual_budget":    monthly_budget * 12,
        "current_actual":   current_actual,
        "current_burn":     current_burn,
        "projected_eom":    projected_eom,
        "days_remaining":   days_remaining,
        "days_with_data":   days_with_data,
        "days_in_curr_mo":  days_in_curr_mo,
        "rolling_avg":      rolling_avg,
        "completed_count":  len(completed_this_yr),
        "n_hist_months":    n_hist,
        "series_diag":      series_diag,
        # per-series WLS forecast for remaining months (Aug–Dec or whatever is future)
        "wls_series_rows":  _build_series_rows(by_ym, wls_params, all_ym_sorted, curr_yr, curr_mo,
                                               days_in_curr_mo, days_with_data, current_burn,
                                               projected_eom, month_names, n_hist),
    }
    return rows, meta


def _build_series_rows(by_ym, wls_params, all_ym_sorted, curr_yr, curr_mo,
                       days_in_curr_mo, days_with_data, current_burn, projected_eom,
                       month_names, n_hist):
    """Build per-series forecast rows for Internal, Client, VM, DB, Storage."""
    series_cfg = [
        ("internal_cost", "Internal",  "#2563eb"),
        ("client_cost",   "Client",    "#16a34a"),
        ("db_cost",       "Databricks","#7c3aed"),
        ("vm_cost",       "VM",        "#ea580c"),
        ("storage_cost",  "Storage",   "#0891b2"),
    ]
    result = {cfg[1]: [] for cfg in series_cfg}
    steps_from_last = 1

    for m in range(1, 13):
        label = f"{month_names[m-1]} {curr_yr}"
        for k, name, _ in series_cfg:
            actual = by_ym[k].get((curr_yr, m))
            if m < curr_mo and actual is not None:
                result[name].append({"label": label, "type": "actual", "value": actual})
            elif m == curr_mo:
                # Scale EOM projection by series share from latest actual month
                latest_total = max(by_ym["total_cost"].get(all_ym_sorted[-1], 1), 1) if all_ym_sorted else 1
                latest_series = by_ym[k].get(all_ym_sorted[-1], 0) if all_ym_sorted else 0
                share = latest_series / latest_total
                result[name].append({"label": label, "type": "current", "value": projected_eom * share})
            else:
                p = wls_params[k]
                if p:
                    a, b, rmse, _ = p
                    pred = max(a + b * (n_hist + steps_from_last), 0)
                else:
                    vals = list(by_ym[k].values())
                    pred = float(np.mean(vals)) if vals else 0
                    rmse = pred * 0.15
                result[name].append({"label": label, "type": "forecast", "value": round(pred, 2)})
        if m >= curr_mo:
            steps_from_last += 1

    return result


def year_end_forecast(rows):
    return sum(
        r["actual"] if r["type"] == "actual" and r["actual"] is not None
        else (r["forecast"] or 0)
        for r in rows
    )

def avg_accuracy(rows):
    vals = [r["accuracy"] for r in rows if r.get("accuracy") is not None]
    return round(sum(vals) / len(vals), 1) if vals else None


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("<div style='color:#fff;font-size:0.8rem;font-weight:700;margin-bottom:6px;'>💰 Monthly Budget</div>",
                unsafe_allow_html=True)
    monthly_budget_input = st.number_input(
        "Monthly budget ($)", min_value=0, value=480_000, step=10_000,
        format="%d", label_visibility="collapsed",
    )
    st.markdown(
        f"<div style='color:rgba(255,255,255,0.4);font-size:0.65rem;margin-top:4px;'>"
        f"Annual: ${monthly_budget_input * 12 / 1_000_000:.2f}M</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<hr style='border-color:rgba(255,255,255,0.1);margin:14px 0'>", unsafe_allow_html=True)
    st.markdown("<div style='color:#fff;font-size:0.8rem;font-weight:700;margin-bottom:6px;'>📐 Forecast Method</div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='color:rgba(255,255,255,0.7);font-size:0.72rem;line-height:1.5;margin-bottom:8px;'>"
        "<b>Weighted Least Squares (WLS)</b> regression — quadratic weights so recent months "
        "dominate. Linear trend fitted across all available completed months.<br>"
        "Confidence bands = &plusmn;RMSE of weighted residuals (data-driven, not a fixed %)."
        "</div>",
        unsafe_allow_html=True,
    )
    # WLS has no user-configurable weight parameters — settings are automatic
    # Keep variables for backward compat with build_forecast signature
    rolling_weight = 0.7
    burn_weight    = 0.3
    conf_base      = 0.15
    conf_step      = 0.02

    st.markdown("<hr style='border-color:rgba(255,255,255,0.1);margin:14px 0'>", unsafe_allow_html=True)
    st.markdown("<div style='color:#fff;font-size:0.8rem;font-weight:700;margin-bottom:6px;'>🔌 Azure Portal (Optional)</div>", unsafe_allow_html=True)
    use_portal_override = st.checkbox("Use Azure Portal current-month MTD override", value=False)
    portal_current_mtd = None
    if use_portal_override:
        portal_current_mtd = st.number_input(
            "Portal MTD spend ($)",
            min_value=0.0,
            value=0.0,
            step=1000.0,
            format="%.2f",
        )

    st.markdown("<hr style='border-color:rgba(255,255,255,0.1);margin:14px 0'>", unsafe_allow_html=True)


# ── Load data ──────────────────────────────────────────────────────────────────
token, auth_mode, auth_tenant = get_token()
token_claims = decode_token_claims(token)
token_app_id = token_claims.get("appid") or token_claims.get("azp") or "—"
token_obj_id = token_claims.get("oid") or "—"
token_upn = token_claims.get("upn") or token_claims.get("preferred_username") or "—"
today = datetime.now()

resolved_dataset_id = DATASET_ID
resolved_dataset_name = SEMANTIC_MODEL_NAME
try:
    resolved_dataset_id, resolved_dataset_name = resolve_dataset(token)
except Exception as exc:
    st.error(
        "Unable to resolve semantic model in Fabric workspace.\n\n"
        f"Workspace: **{WORKSPACE_NAME}**\n\n"
        f"Requested model: **{SEMANTIC_MODEL_NAME}**\n\n"
        f"Error: `{exc}`"
    )
    st.stop()

with st.spinner(f"Loading Azure spend data from {resolved_dataset_name}…"):
    hist_df, live_row, elapsed, query_error, db_kpis = fetch_spend_data(token, resolved_dataset_id)

with st.sidebar:
    with st.expander("Auth Diagnostics", expanded=False):
        st.caption(f"Mode: {auth_mode}")
        st.caption(f"Tenant: {auth_tenant}")
        st.caption(f"Token app id: {token_app_id}")
        st.caption(f"Token object id: {token_obj_id}")
        st.caption(f"Token principal: {token_upn}")
        st.caption(f"Workspace: {WORKSPACE_NAME}")
        st.caption(f"Model: {resolved_dataset_name}")
        st.caption(f"Model ID: {resolved_dataset_id}")
        st.caption(f"Query status: {'failed' if query_error else 'ok'}")
        if query_error:
            st.caption(f"Error: {query_error[:180]}")

if hist_df.empty and not live_row:
    st.warning(
        "No data returned from the Semantic Model.\n\n"
        f"Workspace: **{WORKSPACE_NAME}**\n\n"
        f"Dataset: **{resolved_dataset_name}**"
    )
    st.stop()

rows, meta    = build_forecast(
    hist_df,
    live_row,
    today,
    float(monthly_budget_input),
    FORECAST_YEAR,
    portal_current_mtd=portal_current_mtd,
)
yef           = year_end_forecast(rows)
acc_avg       = avg_accuracy(rows)
generated     = today.strftime("%Y-%m-%d %H:%M")
user_email    = st.session_state.get("user_email", "anmol.sharma@milliman.com")
completed_months = sum(1 for r in rows if r["type"] == "actual")
forecast_months  = sum(1 for r in rows if r["type"] == "forecast")
annual_budget    = meta["annual_budget"]
yef_over         = yef > annual_budget
over_under       = yef - annual_budget
budget_vs_yef    = round(yef / annual_budget * 100, 1) if annual_budget > 0 else 0
max_date_str     = live_row.get("maxdate", "—")


# ── Banner ─────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="top-banner">
    <div class="dash-title">Azure Spend <span>{FORECAST_YEAR} Monthly Forecast</span></div>
  <div class="dash-meta">
    <span class="m">{TENANT_NAME}</span>
        <span class="m">Workspace: {WORKSPACE_NAME}</span>
        <span class="m">Semantic model: {resolved_dataset_name}</span>
    <span class="m">{user_email}</span>
    <span class="m">Generated: {generated}</span>
    <span class="m">WLS trend across {meta['n_hist_months']} months · 3-mo avg: ${meta['rolling_avg']/1000:.1f}K/mo</span>
    <span class="m">Daily burn: ${meta['current_burn']/1000:.2f}K/day · {meta['days_remaining']}d remaining</span>
    <span class="m">Data as of: {max_date_str} · Query: {elapsed}s</span>
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px 16px;
            font-size:11px;color:#475569;display:flex;gap:20px;flex-wrap:wrap;margin-bottom:16px;">
  <span>📊 <b>Actuals</b>
        <span class="source-tag grn">Azure_Expense_Details · [Azure cost] · Complete_Month ≠ Incomplete</span>
    &nbsp;{len(hist_df)} completed months</span>
  <span>💰 <b>Current MTD</b>
    <span class="source-tag">Complete_Month = Incomplete</span>
        &nbsp;${meta['current_actual']/1000:.1f}K ({meta['days_with_data']} days){' · portal override' if use_portal_override else ''}</span>
  <span>🔥 <b>Daily burn</b>
    <span class="source-tag" style="background:#fff7ed;color:#c2410c;border-color:#fed7aa;">MTD ÷ days elapsed</span>
    &nbsp;${meta['current_burn']/1000:.2f}K/day</span>
</div>
""", unsafe_allow_html=True)


# ── KPI cards ──────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)

def acc_color(a):
    if a is None: return "blu"
    return "grn" if a >= 90 else "ora" if a >= 75 else "red"

with k1:
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-lbl">Annual Budget ({FORECAST_YEAR})</div>
        <div class="kpi-val blu">${annual_budget/1000:.0f}K</div>
        <div class="kpi-sub">${meta['monthly_budget']/1000:.1f}K/month</div>
    </div>""", unsafe_allow_html=True)

with k2:
    st.markdown(f"""<div class="kpi-card {'red' if yef_over else 'green'}">
        <div class="kpi-lbl">Year-End Forecast</div>
        <div class="kpi-val {'red' if yef_over else 'grn'}">${yef/1000:.0f}K</div>
        <div class="kpi-sub">{budget_vs_yef}% of annual budget</div>
    </div>""", unsafe_allow_html=True)

with k3:
    ou_sign = "+" if over_under > 0 else ""
    st.markdown(f"""<div class="kpi-card {'red' if over_under > 0 else 'green'}">
        <div class="kpi-lbl">Variance vs Budget</div>
        <div class="kpi-val {'red' if over_under > 0 else 'grn'}">{ou_sign}${abs(over_under)/1000:.0f}K</div>
        <div class="kpi-sub">{'Over budget pace' if over_under > 0 else 'Under budget pace'}</div>
    </div>""", unsafe_allow_html=True)

with k4:
    rest = max(meta["projected_eom"] - meta["current_actual"], 0)
    st.markdown(f"""<div class="kpi-card ora">
        <div class="kpi-lbl">Current Month EOM</div>
        <div class="kpi-val ora">${meta['projected_eom']/1000:.1f}K</div>
        <div class="kpi-sub">${meta['current_actual']/1000:.1f}K MTD + ${rest/1000:.1f}K projected</div>
    </div>""", unsafe_allow_html=True)

with k5:
    ac_disp = f"{acc_avg}%" if acc_avg is not None else "N/A"
    ac_sub  = f"avg over {completed_months} completed months" if acc_avg else "needs 2+ months of history"
    st.markdown(f"""<div class="kpi-card {'green' if (acc_avg and acc_avg>=90) else 'ora' if (acc_avg and acc_avg>=75) else 'red'}">
        <div class="kpi-lbl">Forecast Accuracy</div>
        <div class="kpi-val {acc_color(acc_avg)}">{ac_disp}</div>
        <div class="kpi-sub">{ac_sub}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("---")


# ── Chart 1 — 12-month spend bar + confidence band + budget line ───────────────
st.markdown("<div class='section-label'>📈 12-Month Spend vs Forecast vs Budget</div>", unsafe_allow_html=True)

labels   = [r["label"] for r in rows]
fc_rows  = [r for r in rows if r["type"] == "forecast"]
fc_labels= [r["label"] for r in fc_rows]

fig = go.Figure()

if fc_rows:
    fig.add_trace(go.Scatter(
        x=fc_labels + fc_labels[::-1],
        y=[r["upper"]/1000 for r in fc_rows] + [r["lower"]/1000 for r in fc_rows[::-1]],
        fill="toself", fillcolor="rgba(37,99,235,0.08)",
        line=dict(color="rgba(0,0,0,0)"), hoverinfo="skip",
        showlegend=True, name="Confidence Band (±15–35%)",
    ))

fig.add_trace(go.Scatter(
    x=labels, y=[r["budget"]/1000 for r in rows],
    mode="lines", name="Monthly Budget",
    line=dict(color="#94a3b8", width=1.5, dash="dot"),
    hovertemplate="%{x}<br>Budget: $%{y:.1f}K<extra></extra>",
))

act_x = [r["label"] for r in rows if r["type"] == "actual" and r["actual"] is not None]
act_y = [r["actual"]/1000 for r in rows if r["type"] == "actual" and r["actual"] is not None]
if act_x:
    fig.add_trace(go.Bar(x=act_x, y=act_y, name="Actual Spend",
        marker_color="#2563eb", opacity=0.88,
        hovertemplate="%{x}<br>Actual: $%{y:.1f}K<extra></extra>"))

curr_row = next((r for r in rows if r["type"] == "current"), None)
if curr_row:
    fig.add_trace(go.Bar(
        x=[curr_row["label"]], y=[curr_row["actual"]/1000],
        name="Current Month (MTD)", marker_color="#60a5fa", opacity=0.9,
        hovertemplate="%{x}<br>MTD: $%{y:.1f}K<extra></extra>"))
    rest_k = (curr_row["forecast"] - curr_row["actual"]) / 1000
    if rest_k > 0:
        fig.add_trace(go.Bar(
            x=[curr_row["label"]], y=[rest_k],
            name="Projected (rest of month)", marker_color="#bfdbfe", opacity=0.85,
            hovertemplate="%{x}<br>Projected remaining: $%{y:.1f}K<extra></extra>"))

if fc_labels:
    fig.add_trace(go.Bar(x=fc_labels, y=[r["forecast"]/1000 for r in fc_rows],
        name="Forecasted Spend", marker_color="#a5b4fc", opacity=0.65,
        hovertemplate="%{x}<br>Forecast: $%{y:.1f}K<extra></extra>"))

fig.update_layout(
    barmode="stack", plot_bgcolor="#fff", paper_bgcolor="#fff", height=380,
    margin=dict(t=20, b=40, l=60, r=20),
    legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1, font=dict(size=11)),
    xaxis=dict(showgrid=False, tickfont=dict(size=11)),
    yaxis=dict(showgrid=True, gridcolor="#f1f5f9", ticksuffix="K",
               tickfont=dict(size=11), title=dict(text="USD (thousands)", font=dict(size=10))),
    hovermode="x unified", font=dict(family="Inter, system-ui, sans-serif"),
)
st.plotly_chart(fig, use_container_width=True)


# ── Chart 2 — Daily burn + cumulative spend ────────────────────────────────────
st.markdown("<div class='section-label'>📉 Cumulative Spend Pace vs Budget (Monthly Forecast)</div>", unsafe_allow_html=True)

fig2 = make_subplots(specs=[[{"secondary_y": True}]])

burn_x, burn_y = [], []
for r in rows:
    if r["type"] == "actual" and r["actual"] is not None and r["days_in_month"]:
        burn_x.append(r["label"]); burn_y.append(r["actual"] / r["days_in_month"] * 30 / 1000)
    elif r["type"] == "current":
        burn_x.append(r["label"]); burn_y.append(meta["current_burn"] * 30 / 1000)

if burn_x:
    fig2.add_trace(go.Scatter(x=burn_x, y=burn_y, mode="lines+markers",
        name="Monthly Run-Rate at Current Pace ($K/mo)", line=dict(color="#ea580c", width=2.5),
        marker=dict(size=6), hovertemplate="%{x}<br>Run-rate: $%{y:.2f}K/mo<extra></extra>"),
        secondary_y=False)

running = 0.0
cum_x, cum_y = [], []
for r in rows:
    val = r["actual"] if r["type"] == "actual" and r["actual"] is not None else (r["forecast"] or 0)
    running += val; cum_x.append(r["label"]); cum_y.append(running / 1000)

fig2.add_trace(go.Scatter(x=cum_x, y=cum_y, mode="lines",
    name="Cumulative Spend", line=dict(color="#7c3aed", width=1.8, dash="dash"),
    hovertemplate="%{x}<br>Cumulative: $%{y:.0f}K<extra></extra>"), secondary_y=True)

cum_bgt = [(i+1) * meta["monthly_budget"] / 1000 for i in range(12)]
fig2.add_trace(go.Scatter(x=labels, y=cum_bgt, mode="lines",
    name="Budget Pace", line=dict(color="#94a3b8", width=1.5, dash="dot"),
    hovertemplate="%{x}<br>Budget pace: $%{y:.0f}K<extra></extra>"), secondary_y=True)

fig2.update_layout(
    plot_bgcolor="#fff", paper_bgcolor="#fff", height=300,
    margin=dict(t=20, b=40, l=60, r=60),
    legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1, font=dict(size=11)),
    xaxis=dict(showgrid=False, tickfont=dict(size=11)),
    hovermode="x unified", font=dict(family="Inter, system-ui, sans-serif"),
)
fig2.update_yaxes(title_text="Monthly Run-Rate ($K/mo)", showgrid=True, gridcolor="#f1f5f9",
                  ticksuffix="K", tickfont=dict(size=11), secondary_y=False)
fig2.update_yaxes(title_text="Cumulative ($K)", ticksuffix="K",
                  tickfont=dict(size=11), secondary_y=True)
st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")


# ── Chart 3 — Forecast accuracy ────────────────────────────────────────────────
st.markdown("<div class='section-label'>🎯 Forecast Accuracy by Month</div>", unsafe_allow_html=True)

acc_rows = [r for r in rows if r.get("accuracy") is not None]
if not acc_rows:
    st.info("Forecast accuracy will populate once 2+ completed months of actuals are available.")
else:
    acc_vals   = [r["accuracy"] for r in acc_rows]
    acc_colors = ["#16a34a" if a >= 90 else "#ea580c" if a >= 75 else "#dc2626" for a in acc_vals]
    fig3 = go.Figure(go.Bar(
        x=[r["label"] for r in acc_rows], y=acc_vals,
        marker_color=acc_colors,
        text=[f"{a:.1f}%" for a in acc_vals], textposition="outside",
        hovertemplate="%{x}<br>Accuracy: %{y:.1f}%<extra></extra>",
    ))
    fig3.add_hline(y=90, line_dash="dot", line_color="#16a34a",
                   annotation_text="90% target", annotation_position="bottom right")
    fig3.update_layout(
        plot_bgcolor="#fff", paper_bgcolor="#fff", height=240,
        margin=dict(t=30, b=40, l=50, r=20),
        yaxis=dict(range=[0, 110], showgrid=True, gridcolor="#f1f5f9",
                   ticksuffix="%", tickfont=dict(size=11)),
        xaxis=dict(showgrid=False, tickfont=dict(size=11)),
        showlegend=False, font=dict(family="Inter, system-ui, sans-serif"),
    )
    st.plotly_chart(fig3, use_container_width=True)

st.markdown("---")


# ── Databricks Reservation Tracker ────────────────────────────────────────────
st.markdown("<div class='section-label'>⚡ Databricks Reservation Consumption Tracker</div>", unsafe_allow_html=True)

if db_kpis:
    db_total        = float(db_kpis.get("db_reservation_total", 0) or 0)
    db_consumed     = float(db_kpis.get("db_consumed", 0) or 0)
    db_remaining    = float(db_kpis.get("db_remaining", 0) or 0)
    db_pct_consumed = float(db_kpis.get("db_pct_consumed", 0) or 0) * 100
    db_pct_remain   = float(db_kpis.get("db_pct_remaining", 0) or 0) * 100
    db_proj_curr    = float(db_kpis.get("db_projected_current", 0) or 0)
    db_proj_req     = float(db_kpis.get("db_projected_required", 0) or 0)
    db_req_day      = float(db_kpis.get("db_req_per_day", 0) or 0)
    db_avg_day      = float(db_kpis.get("db_current_avg_per_day", 0) or 0)
    db_next30       = float(db_kpis.get("db_next30_required", 0) or 0)
    db_risk_curr    = str(db_kpis.get("db_risk_current", "—") or "—")
    db_risk_req     = str(db_kpis.get("db_risk_required", "—") or "—")
    db_complete_days= int(db_kpis.get("db_complete_days", 0) or 0)
    db_pending_days = int(db_kpis.get("db_pending_days", 0) or 0)
    latest_date_str = str(db_kpis.get("latest_date", "—") or "—")
    avg_mom_6m      = float(db_kpis.get("avg_mom_6m", 0) or 0) * 100
    var_30d_pct     = float(db_kpis.get("variance_30d_pct", 0) or 0) * 100

    curr_risk_color = "#dc2626" if "Risk" in db_risk_curr and "NO" not in db_risk_curr else "#16a34a"
    curr_risk_label = "At Risk" if "Risk" in db_risk_curr and "NO" not in db_risk_curr else "On Track"
    req_risk_color  = "#dc2626" if "Risk" in db_risk_req and "NO" not in db_risk_req else "#16a34a"
    req_risk_label  = "At Risk" if "Risk" in db_risk_req and "NO" not in db_risk_req else "On Track"

    db1, db2, db3, db4 = st.columns(4)
    with db1:
        st.markdown(f"""<div class="kpi-card pur">
            <div class="kpi-lbl">Reservation Total</div>
            <div class="kpi-val blu">${db_total/1_000_000:.2f}M</div>
            <div class="kpi-sub">MedInsight allocation</div>
        </div>""", unsafe_allow_html=True)
    with db2:
        st.markdown(f"""<div class="kpi-card {'green' if db_pct_consumed >= 48 else 'ora'}">
            <div class="kpi-lbl">Consumed to Date</div>
            <div class="kpi-val {'grn' if db_pct_consumed >= 48 else 'ora'}">${db_consumed/1_000_000:.2f}M</div>
            <div class="kpi-sub">{db_pct_consumed:.1f}% of reservation · {db_complete_days} days</div>
        </div>""", unsafe_allow_html=True)
    with db3:
        st.markdown(f"""<div class="kpi-card {'red' if db_pct_remain > 52 else 'green'}">
            <div class="kpi-lbl">Remaining</div>
            <div class="kpi-val {'red' if db_pct_remain > 52 else 'grn'}">${db_remaining/1_000_000:.2f}M</div>
            <div class="kpi-sub">{db_pct_remain:.1f}% remaining · {db_pending_days} days left</div>
        </div>""", unsafe_allow_html=True)
    with db4:
        st.markdown(f"""<div class="kpi-card {'red' if curr_risk_label=='At Risk' else 'green'}">
            <div class="kpi-lbl">Consumption Pace</div>
            <div class="kpi-val" style="color:{curr_risk_color}">{curr_risk_label}</div>
            <div class="kpi-sub">Avg ${db_avg_day:,.0f}/day · Need ${db_req_day:,.0f}/day</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # Gauge: consumption progress
    db_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=db_pct_consumed,
        number={"suffix": "%", "font": {"size": 32}},
        delta={"reference": 50, "valueformat": ".1f", "suffix": "% vs 50% target"},
        title={"text": "Reservation Consumed (%)", "font": {"size": 13}},
        gauge={
            "axis": {"range": [0, 100], "ticksuffix": "%"},
            "bar": {"color": "#2563eb"},
            "steps": [
                {"range": [0, 40], "color": "#fee2e2"},
                {"range": [40, 60], "color": "#fef9c3"},
                {"range": [60, 100], "color": "#dcfce7"},
            ],
            "threshold": {
                "line": {"color": "#dc2626", "width": 3},
                "thickness": 0.75, "value": 50,
            },
        },
    ))
    db_gauge.update_layout(height=240, margin=dict(t=50, b=10, l=30, r=30),
                           paper_bgcolor="#fff", font=dict(family="Inter, system-ui, sans-serif"))

    dbc1, dbc2 = st.columns([1, 2])
    with dbc1:
        st.plotly_chart(db_gauge, use_container_width=True)

    with dbc2:
        # Projected vs required vs actual pace bar
        proj_fig = go.Figure()
        proj_fig.add_trace(go.Bar(
            x=["Consumed to Date", "Projected at Current Pace", "Required to Use All"],
            y=[db_consumed / 1_000_000, db_proj_curr / 1_000_000, db_proj_req / 1_000_000],
            marker_color=["#2563eb", "#ea580c", "#16a34a"],
            text=[f"${v/1_000_000:.2f}M" for v in [db_consumed, db_proj_curr, db_proj_req]],
            textposition="outside",
            hovertemplate="%{x}<br>$%{y:.2f}M<extra></extra>",
        ))
        proj_fig.add_hline(y=db_total / 1_000_000, line_dash="dot", line_color="#7c3aed",
                           annotation_text=f"Reservation: ${db_total/1_000_000:.2f}M",
                           annotation_position="bottom right")
        proj_fig.update_layout(
            plot_bgcolor="#fff", paper_bgcolor="#fff", height=240,
            margin=dict(t=30, b=10, l=50, r=20),
            yaxis=dict(showgrid=True, gridcolor="#f1f5f9", ticksuffix="M", tickfont=dict(size=11)),
            xaxis=dict(tickfont=dict(size=11)), showlegend=False,
            font=dict(family="Inter, system-ui, sans-serif"),
            title=dict(text="Databricks Reservation: Consumed vs Projected", font=dict(size=12, color="#1e293b")),
        )
        st.plotly_chart(proj_fig, use_container_width=True)

    st.markdown(f"""
<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:12px 16px;
            font-size:11px;color:#475569;display:flex;gap:24px;flex-wrap:wrap;">
  <span>📅 <b>Data as of:</b> {latest_date_str}</span>
  <span>📈 <b>Avg MoM growth (6m):</b> {avg_mom_6m:.1f}%</span>
  <span>📊 <b>30-day spend change:</b> {'+' if var_30d_pct>0 else ''}{var_30d_pct:.1f}%</span>
  <span>🎯 <b>Next 30d required:</b> ${db_next30/1000:.0f}K</span>
  <span>⚡ <b>Daily avg consumed:</b> ${db_avg_day:,.0f}/day</span>
  <span>⚡ <b>Daily required:</b> ${db_req_day:,.0f}/day</span>
  <span style="color:{req_risk_color}"><b>Required pace:</b> {req_risk_label}</span>
</div>
""", unsafe_allow_html=True)
else:
    st.info("Databricks reservation metrics unavailable — KPI query returned no data.")

st.markdown("---")


# ── Detail table ───────────────────────────────────────────────────────────────
st.markdown("<div class='section-label'>📋 12-Month Detail Table</div>", unsafe_allow_html=True)

def type_badge(t):
    cls   = {"actual":"mtype-actual","current":"mtype-current","forecast":"mtype-forecast"}[t]
    label = {"actual":"Actual","current":"In Progress","forecast":"Forecast"}[t]
    return f"<span class='{cls}'>{label}</span>"

def variance_html(fc, bgt):
    if fc is None or not bgt: return "<span style='color:#94a3b8'>—</span>"
    v = fc - bgt; pct = round(v / bgt * 100, 1)
    if v > 0: return f"<span style='color:#dc2626;font-weight:600'>+${v/1000:.1f}K ({pct}%)</span>"
    return f"<span style='color:#16a34a;font-weight:600'>{pct}% (${abs(v)/1000:.1f}K under)</span>"

def acc_badge_html(a):
    if a is None: return ""
    cls = "acc-good" if a >= 90 else "acc-ok" if a >= 75 else "acc-poor"
    return f"<span class='acc-badge {cls}'>{a:.1f}%</span>"

rows_html = []
for r in rows:
    if   r["type"] == "actual":  row_css = "row-actual"
    elif r["type"] == "current": row_css = "row-current"
    elif r["forecast"] and r["budget"] and r["forecast"] > r["budget"] * 1.05: row_css = "row-over"
    else:                        row_css = "row-forecast"

    actual_d   = f"${r['actual']/1000:.1f}K"   if r["actual"]   is not None else "<span style='color:#94a3b8'>—</span>"
    forecast_d = f"${r['forecast']/1000:.1f}K"  if r["forecast"] is not None else "<span style='color:#94a3b8'>—</span>"
    lo, hi     = r.get("lower"), r.get("upper")
    band_d     = f"${lo/1000:.1f}K–${hi/1000:.1f}K" if lo is not None and r["type"] != "actual" else "—"
    burn_d     = f"${r['burn_day']*1000:.0f}/day" if r["burn_day"] else "—"

    rows_html.append(f"""<tr class='{row_css}'>
  <td><b>{r['label']}</b></td><td>{type_badge(r['type'])}</td>
  <td class='num'>{actual_d}</td><td class='num'>{forecast_d}</td>
  <td class='num'>${r['budget']/1000:.1f}K</td>
  <td class='num'>{variance_html(r['forecast'], r['budget'])}</td>
  <td class='num' style='font-size:10px;color:#64748b'>{band_d}</td>
  <td class='num'>{burn_d}</td>
  <td class='num'>{acc_badge_html(r.get('accuracy'))}</td>
</tr>""")

st.markdown(f"""
<div class="fg-wrap"><table class="fg">
<thead><tr>
  <th>Month</th><th>Type</th>
  <th class="num">Actual Spend</th><th class="num">Forecast / EOM</th>
  <th class="num">Monthly Budget</th><th class="num">Forecast vs Budget</th>
  <th class="num">Confidence Band</th><th class="num">Avg Daily Burn</th>
  <th class="num">Forecast Accuracy</th>
</tr></thead>
<tbody>{"".join(rows_html)}</tbody>
</table></div>
""", unsafe_allow_html=True)

st.markdown("---")


# ── Internal vs Client split ───────────────────────────────────────────────────
st.markdown("<div class='section-label'>🏢 Internal vs Client Subscription Forecast</div>", unsafe_allow_html=True)

series_rows = meta.get("wls_series_rows", {})
series_diag = meta.get("series_diag", {})

def _r2_badge(r2):
    if r2 is None: return ""
    cls = "acc-good" if r2 >= 0.7 else "acc-ok" if r2 >= 0.4 else "acc-poor"
    return f"<span class='acc-badge {cls}'>R² {r2:.2f}</span>"

def _slope_str(k, series_diag):
    d = series_diag.get(k)
    if d is None: return ""
    s = d["slope"]
    arrow = "▲" if s > 0 else "▼"
    color = "#dc2626" if s > 0 else "#16a34a"
    return f"<span style='color:{color};font-size:10px;'>{arrow} ${abs(s)/1000:.1f}K/mo trend</span>"

ic_col, sc_col = st.columns(2)
for col_widget, series_key, series_name, color in [
    (ic_col, "internal_cost", "Internal", "#2563eb"),
    (sc_col, "client_cost",   "Client",   "#16a34a"),
]:
    with col_widget:
        s_rows = series_rows.get(series_name, [])
        diag   = series_diag.get(series_key)
        r2     = diag["r2"]   if diag else None
        rmse   = diag["rmse"] if diag else None
        slope  = diag["slope"] if diag else None

        if s_rows:
            fig_ic = go.Figure()
            act_x_ = [r["label"] for r in s_rows if r["type"] == "actual"]
            act_y_ = [r["value"]/1000 for r in s_rows if r["type"] == "actual"]
            fc_x_  = [r["label"] for r in s_rows if r["type"] in ("forecast", "current")]
            fc_y_  = [r["value"]/1000 for r in s_rows if r["type"] in ("forecast", "current")]
            if act_x_:
                fig_ic.add_trace(go.Bar(x=act_x_, y=act_y_, name="Actual",
                    marker_color=color, opacity=0.88,
                    hovertemplate="%{x}<br>Actual: $%{y:.1f}K<extra></extra>"))
            if fc_x_:
                fig_ic.add_trace(go.Bar(x=fc_x_, y=fc_y_, name="Forecast",
                    marker_color=color, opacity=0.45,
                    hovertemplate="%{x}<br>Forecast: $%{y:.1f}K<extra></extra>"))
            if rmse and fc_x_:
                fig_ic.add_trace(go.Scatter(
                    x=fc_x_ + fc_x_[::-1],
                    y=[(v + rmse/1000) for v in fc_y_] + [(max(0, v - rmse/1000)) for v in fc_y_[::-1]],
                    fill="toself", fillcolor=f"rgba(0,0,0,0.06)",
                    line=dict(color="rgba(0,0,0,0)"), hoverinfo="skip", showlegend=False))

            r2_title = f" · R² {r2:.2f}" if r2 is not None else ""
            slope_title = f" · trend {'+' if slope and slope>0 else ''}{slope/1000:.1f}K/mo" if slope else ""
            fig_ic.update_layout(
                barmode="stack", plot_bgcolor="#fff", paper_bgcolor="#fff", height=260,
                margin=dict(t=30, b=30, l=50, r=10),
                title=dict(text=f"{series_name} Subscriptions{r2_title}{slope_title}", font=dict(size=12, color="#1e293b")),
                legend=dict(orientation="h", yanchor="bottom", y=1.01, font=dict(size=10)),
                xaxis=dict(showgrid=False, tickfont=dict(size=9)),
                yaxis=dict(showgrid=True, gridcolor="#f1f5f9", ticksuffix="K", tickfont=dict(size=10)),
                font=dict(family="Inter, system-ui, sans-serif"),
            )
            st.plotly_chart(fig_ic, use_container_width=True)

# Key-category breakdown (Databricks, VM, Storage)
st.markdown("<div class='section-label' style='margin-top:4px;'>🔬 Category Forecast — Databricks · VM · Storage (WLS trends)</div>", unsafe_allow_html=True)

cat_colors = {"Databricks": "#7c3aed", "VM": "#ea580c", "Storage": "#0891b2"}
cat_keys   = {"Databricks": "db_cost", "VM": "vm_cost", "Storage": "storage_cost"}
c1, c2, c3 = st.columns(3)

for col_widget, cat_name in [(c1, "Databricks"), (c2, "VM"), (c3, "Storage")]:
    with col_widget:
        s_rows = series_rows.get(cat_name, [])
        k      = cat_keys[cat_name]
        diag   = series_diag.get(k)
        color  = cat_colors[cat_name]
        r2     = diag["r2"]    if diag else None
        rmse   = diag["rmse"]  if diag else None
        slope  = diag["slope"] if diag else None

        if s_rows:
            fig_cat = go.Figure()
            act_x_ = [r["label"] for r in s_rows if r["type"] == "actual"]
            act_y_ = [r["value"]/1000 for r in s_rows if r["type"] == "actual"]
            fc_x_  = [r["label"] for r in s_rows if r["type"] in ("forecast", "current")]
            fc_y_  = [r["value"]/1000 for r in s_rows if r["type"] in ("forecast", "current")]
            if act_x_:
                fig_cat.add_trace(go.Bar(x=act_x_, y=act_y_, name="Actual",
                    marker_color=color, opacity=0.88,
                    hovertemplate="%{x}<br>Actual: $%{y:.1f}K<extra></extra>"))
            if fc_x_:
                fig_cat.add_trace(go.Bar(x=fc_x_, y=fc_y_, name="Forecast",
                    marker_color=color, opacity=0.45,
                    hovertemplate="%{x}<br>Forecast: $%{y:.1f}K<extra></extra>"))
            r2_title = f" R²={r2:.2f}" if r2 is not None else ""
            slope_title = f" {'+' if slope and slope>0 else ''}{slope/1000:.1f}K/mo" if slope else ""
            fig_cat.update_layout(
                barmode="stack", plot_bgcolor="#fff", paper_bgcolor="#fff", height=230,
                margin=dict(t=30, b=30, l=45, r=10),
                title=dict(text=f"{cat_name}{r2_title}{slope_title}", font=dict(size=11, color="#1e293b")),
                showlegend=False,
                xaxis=dict(showgrid=False, tickfont=dict(size=8)),
                yaxis=dict(showgrid=True, gridcolor="#f1f5f9", ticksuffix="K", tickfont=dict(size=9)),
                font=dict(family="Inter, system-ui, sans-serif"),
            )
            st.plotly_chart(fig_cat, use_container_width=True)

# WLS R² summary pills
diag_items = [
    ("Total",       series_diag.get("total_cost")),
    ("Internal",    series_diag.get("internal_cost")),
    ("Client",      series_diag.get("client_cost")),
    ("Databricks",  series_diag.get("db_cost")),
    ("VM",          series_diag.get("vm_cost")),
    ("Storage",     series_diag.get("storage_cost")),
]
pills = []
for name, d in diag_items:
    if d:
        r2   = d["r2"]
        rmse = d["rmse"]
        slope = d["slope"]
        q = "acc-good" if r2 >= 0.7 else "acc-ok" if r2 >= 0.4 else "acc-poor"
        tr = f"{'+' if slope>0 else ''}{slope/1000:.1f}K/mo"
        pills.append(f"<span class='acc-badge {q}' style='margin:3px;'>{name} R²={r2:.2f} · {tr} · RMSE ${rmse/1000:.0f}K</span>")

if pills:
    st.markdown(
        "<div style='margin:8px 0 4px 0;font-size:11px;font-weight:600;color:#475569;'>WLS Model Quality</div>"
        + "".join(pills),
        unsafe_allow_html=True,
    )

st.markdown("---")


# ── Year-end summary ───────────────────────────────────────────────────────────
st.markdown("<div class='section-label'>📊 Year-End Summary</div>", unsafe_allow_html=True)

col_chart, col_stats = st.columns([3, 2])

with col_chart:
    wf_labels  = [r["label"] for r in rows] + ["Year-End Total"]
    wf_vals    = [(r["actual"] if r["type"]=="actual" and r["actual"] is not None else r["forecast"] or 0) for r in rows]
    wf_measure = ["relative"] * 12 + ["total"]
    wf_colors  = ["#2563eb" if r["type"]=="actual" else "#60a5fa" if r["type"]=="current" else "#a5b4fc" for r in rows] + ["#7c3aed"]

    fig4 = go.Figure(go.Waterfall(
        orientation="v", measure=wf_measure, x=wf_labels, y=wf_vals + [0],
        connector=dict(line=dict(color="#e2e8f0", width=1)),
        increasing=dict(marker=dict(color="#2563eb")),
        totals=dict(marker=dict(color="#7c3aed")),
        hovertemplate="%{x}<br>$%{y:,.0f}<extra></extra>",
    ))
    fig4.add_hline(y=annual_budget, line_dash="dot", line_color="#dc2626",
                   annotation_text=f"Annual Budget ${annual_budget/1000:.0f}K",
                   annotation_position="bottom right")
    fig4.update_layout(
        plot_bgcolor="#fff", paper_bgcolor="#fff", height=340,
        margin=dict(t=30, b=40, l=60, r=20),
        yaxis=dict(showgrid=True, gridcolor="#f1f5f9", tickfont=dict(size=10)),
        xaxis=dict(tickfont=dict(size=9)), showlegend=False,
        font=dict(family="Inter, system-ui, sans-serif"),
        title=dict(text="Month-by-Month Build-up to Year-End", font=dict(size=12, color="#1e293b")),
    )
    st.plotly_chart(fig4, use_container_width=True)

with col_stats:
    pace_note   = "On Track" if abs(over_under)/annual_budget < 0.05 else ("Over Pace" if yef_over else "Under Pace")
    pct_yr_done = round(completed_months / 12 * 100, 0)

    st.markdown(f"""
<div style="background:#fff;border-radius:10px;border:1px solid #e2e8f0;padding:18px 20px;">
  <div style="font-size:0.82rem;font-weight:700;color:#1e293b;margin-bottom:12px;">Year-End Forecast Summary</div>
  <table style="width:100%;font-size:12px;border-collapse:collapse;">
    <tr><td style="color:#64748b;padding:5px 0">Annual Budget</td>
        <td style="text-align:right;font-weight:600">${annual_budget/1000:.0f}K</td></tr>
    <tr style="border-top:1px solid #f1f5f9">
        <td style="color:#64748b;padding:5px 0">YE Forecast</td>
        <td style="text-align:right;font-weight:700;color:{'#dc2626' if yef_over else '#16a34a'}">${yef/1000:.0f}K</td></tr>
    <tr style="border-top:1px solid #f1f5f9">
        <td style="color:#64748b;padding:5px 0">Budget Variance</td>
        <td style="text-align:right;font-weight:600;color:{'#dc2626' if over_under>0 else '#16a34a'}">
          {'+' if over_under>0 else ''}${over_under/1000:.0f}K</td></tr>
    <tr style="border-top:1px solid #f1f5f9">
        <td style="color:#64748b;padding:5px 0">WLS history</td>
        <td style="text-align:right;font-weight:600">{meta['n_hist_months']} months</td></tr>
    <tr style="border-top:1px solid #f1f5f9">
        <td style="color:#64748b;padding:5px 0">3-mo rolling avg</td>
        <td style="text-align:right;font-weight:600">${meta['rolling_avg']/1000:.0f}K/mo</td></tr>
    <tr style="border-top:1px solid #f1f5f9">
        <td style="color:#64748b;padding:5px 0">Daily Burn Rate</td>
        <td style="text-align:right;font-weight:600">${meta['current_burn']/1000:.2f}K/day</td></tr>
    <tr style="border-top:1px solid #f1f5f9">
        <td style="color:#64748b;padding:5px 0">Months Completed</td>
        <td style="text-align:right;font-weight:600">{completed_months} of 12 ({int(pct_yr_done)}%)</td></tr>
    <tr style="border-top:1px solid #f1f5f9">
        <td style="color:#64748b;padding:5px 0">Forecast Accuracy (avg)</td>
        <td style="text-align:right;font-weight:600;color:{'#16a34a' if acc_avg and acc_avg>=90 else '#ea580c' if acc_avg and acc_avg>=75 else '#94a3b8'}">
          {str(acc_avg)+'%' if acc_avg else 'N/A'}</td></tr>
    <tr style="border-top:1px solid #f1f5f9">
        <td style="color:#64748b;padding:5px 0">Pace</td>
        <td style="text-align:right;font-weight:600">{pace_note}</td></tr>
  </table>
</div>""", unsafe_allow_html=True)

    total_diag = meta.get("series_diag", {}).get("total_cost", {})
    total_r2   = total_diag.get("r2", None) if total_diag else None
    total_rmse = total_diag.get("rmse", None) if total_diag else None
    r2_str     = f"{total_r2:.2f}" if total_r2 is not None else "N/A"
    rmse_str   = f"${total_rmse/1000:.0f}K" if total_rmse else "N/A"
    st.markdown(f"""
<div class="method-box" style="margin-top:12px;">
  <b>Data source — {resolved_dataset_name}</b><br>
  <b>Table:</b> Azure_Expense_Details · Import mode (SQL MI source)<br>
  <b>Actuals:</b> [Azure cost] measure · Complete_Month &ne; "Incomplete"<br>
  <b>Current MTD:</b> [Azure cost] where Complete_Month = "Incomplete"<br>
  <b>Daily burn:</b> MTD &divide; days elapsed in current month<br>
  <b>EOM projection:</b> MTD + burn &times; days remaining<br>
  <b>Forecast method:</b> Weighted Least Squares (WLS) regression — linear trend
    y&nbsp;=&nbsp;a&nbsp;+&nbsp;b&times;t fitted across all {meta['n_hist_months']} completed months.
    Quadratic weights w<sub>i</sub>&nbsp;=&nbsp;i&sup2; so recent months dominate.<br>
  <b>Series fitted:</b> Total, Internal, Client, Databricks (MeterCategory), VM, Storage<br>
  <b>Confidence bands:</b> &plusmn;RMSE of weighted residuals (data-driven, not fixed %).
    Total model: R&sup2;&nbsp;=&nbsp;{r2_str}, RMSE&nbsp;=&nbsp;{rmse_str}<br>
  <b>Internal vs Client:</b> Azure_Expense_Details[Client Name] = "MedInsight Internal" &rarr; Internal; all others &rarr; Client<br>
  <b>Databricks:</b> live reservation KPIs from [MedInsight Azure DataBricks Reservations] measures
</div>""", unsafe_allow_html=True)


# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="dash-footer">
  <span>{completed_months} months actual · {forecast_months} months forecast · accuracy {str(acc_avg)+'%' if acc_avg else 'N/A'}</span>
    <span>{resolved_dataset_name} · ID: {resolved_dataset_id[:8]}... · Import mode · Cache: 5 min · Auto-refresh: 5 min</span>
</div>
""", unsafe_allow_html=True)
