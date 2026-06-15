# # Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "84677723-0231-4f98-b71a-14879da990b8",
# META       "default_lakehouse_name": "MedInsight_Azure_FinOps_Intelligence",
# META       "default_lakehouse_workspace_id": "eca3c81e-a968-42a5-899f-d8fc1a45ebec",
# META       "known_lakehouses": [
# META         {
# META           "id": "84677723-0231-4f98-b71a-14879da990b8"
# META         }
# META       ]
# META     }
# META   }
# META }

# CELL ********************

"""
Azure Budget & Cost Analysis — Fabric Notebook Edition v2
Adds SpendByService table: 60-day daily cost by ServiceFamily + MeterCategory per subscription.

Changes from v1:
  - _service_cost_query_with_retry(): new function, queries 60 days of daily spend
    grouped by ServiceFamily + MeterCategory, writes SpendByService Delta table.
  - All existing BudgetData logic is unchanged.
"""

import json
import os
import time
import math
import threading
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta

logging.getLogger("azure.identity").setLevel(logging.CRITICAL)
logging.getLogger("azure.core").setLevel(logging.CRITICAL)

# ── Configuration ─────────────────────────────────────────────────────────────

TENANT_NAMES = {
    "b2e2e6d4-979f-4671-aa72-0f0c494a0173": "MedInsight Production",
    "e240d61e-61e3-4c9e-ab90-8644b2f4d2a9": "Milliman Inc.",
    "ff6598a3-6053-498d-a3b0-54295c0ce494": "MedInsight Engineering",
}

WORKSPACE_ID       = "eca3c81e-a968-42a5-899f-d8fc1a45ebec"
LAKEHOUSE_ID       = "84677723-0231-4f98-b71a-14879da990b8"
OUTPUT_FILE        = "BudgetData.json"
OUTPUT_FILE_SVC    = "SpendByService.json"   # NEW

MAX_WORKERS        = 50

SERVICE_PRINCIPALS = {
    "b2e2e6d4-979f-4671-aa72-0f0c494a0173": {
        "client_id":     os.getenv("AZURE_CLIENT_ID_PROD",     "37b785ce-3326-45f3-a251-28202711dd6f"),
        "client_secret": os.getenv("AZURE_CLIENT_SECRET_PROD", ""),
    },
    "ff6598a3-6053-498d-a3b0-54295c0ce494": {
        "client_id":     os.getenv("AZURE_CLIENT_ID_ENG",     "c498ca52-2eb4-45e5-ac49-6f503661baca"),
        "client_secret": os.getenv("AZURE_CLIENT_SECRET_ENG", ""),
    },
    "e240d61e-61e3-4c9e-ab90-8644b2f4d2a9": {
        "client_id":     os.getenv("AZURE_CLIENT_ID_MILLIMAN",     ""),
        "client_secret": os.getenv("AZURE_CLIENT_SECRET_MILLIMAN", ""),
    },
}

TENANT_TOKENS = {
    "b2e2e6d4-979f-4671-aa72-0f0c494a0173": "",
    "ff6598a3-6053-498d-a3b0-54295c0ce494": "",
    "e240d61e-61e3-4c9e-ab90-8644b2f4d2a9": "",
}

# ── Authentication (unchanged) ─────────────────────────────────────────────────

def resolve_tokens() -> dict:
    all_tenant_ids = set(TENANT_TOKENS) | set(SERVICE_PRINCIPALS)
    resolved = {}
    for tenant_id in all_tenant_ids:
        name   = TENANT_NAMES.get(tenant_id, tenant_id)
        pasted = TENANT_TOKENS.get(tenant_id, "")
        if pasted and pasted.strip():
            resolved[tenant_id] = pasted.strip()
            print(f"  [Auth] {name}: using pasted token")
            continue
        sp = SERVICE_PRINCIPALS.get(tenant_id, {})
        if sp.get("client_id") and sp.get("client_secret"):
            try:
                from azure.identity import ClientSecretCredential
                cred  = ClientSecretCredential(tenant_id=tenant_id, client_id=sp["client_id"], client_secret=sp["client_secret"])
                token = cred.get_token("https://management.azure.com/.default").token
                resolved[tenant_id] = token
                print(f"  [Auth] {name}: token via service principal")
                continue
            except Exception as e:
                print(f"  [Auth] {name}: SP auth failed — {e}")
        try:
            from azure.identity import DefaultAzureCredential
            cred  = DefaultAzureCredential()
            token = cred.get_token("https://management.azure.com/.default", tenant_id=tenant_id).token
            resolved[tenant_id] = token
            print(f"  [Auth] {name}: token via DefaultAzureCredential")
        except Exception as e:
            print(f"  [Auth] {name}: SKIPPED — {e}")
    if not resolved:
        raise RuntimeError("No tokens available.")
    return resolved


def get_storage_token() -> str:
    for name in ("notebookutils", "mssparkutils"):
        try:
            import importlib
            nu    = importlib.import_module(name)
            token = nu.credentials.getToken("https://storage.azure.com/")
            print(f"  [Auth] Storage token via {name}")
            return token
        except (ImportError, Exception):
            pass
    try:
        from azure.identity import DefaultAzureCredential
        token = DefaultAzureCredential().get_token("https://storage.azure.com/.default").token
        print("  [Auth] Storage token via DefaultAzureCredential")
        return token
    except Exception as e:
        raise RuntimeError(f"Cannot get storage token: {e}")


# ── Subscriptions (unchanged) ──────────────────────────────────────────────────

def get_subscriptions_for_tenant(token: str, tenant_id: str) -> list:
    subs = []
    url  = "https://management.azure.com/subscriptions?api-version=2022-12-01"
    hdrs = {"Authorization": f"Bearer {token}"}
    while url:
        resp = requests.get(url, headers=hdrs, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        for s in data.get("value", []):
            if s.get("state") == "Enabled":
                subs.append({"id": s["subscriptionId"], "name": s.get("displayName", s["subscriptionId"]), "tenantId": tenant_id})
        url = data.get("nextLink")
    return subs


# ── Thread-local session (unchanged) ──────────────────────────────────────────

_tls = threading.local()

def _session(token: str) -> requests.Session:
    if not hasattr(_tls, "sess") or getattr(_tls, "token", None) != token:
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        _tls.sess  = s
        _tls.token = token
    return _tls.sess


# ── Budget total cost query (unchanged) ───────────────────────────────────────

def _cost_query_with_retry(sub_id: str, token: str, max_attempts: int = 5) -> float:
    url  = (
        f"https://management.azure.com/subscriptions/{sub_id}"
        f"/providers/Microsoft.CostManagement/query?api-version=2023-11-01"
    )
    body = json.dumps({
        "type":      "ActualCost",
        "timeframe": "MonthToDate",
        "dataset": {"granularity": "None", "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}}},
    })
    for attempt in range(1, max_attempts + 1):
        try:
            sess = _session(token)
            resp = sess.post(url, data=body, timeout=60)
            if resp.status_code == 429:
                if attempt == max_attempts:
                    return 0.0
                wait = int(resp.headers.get("Retry-After", 30))
                time.sleep(wait)
                continue
            resp.raise_for_status()
            rows = resp.json().get("properties", {}).get("rows", [])
            return float(rows[0][0]) if rows else 0.0
        except requests.exceptions.HTTPError:
            return 0.0
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            if hasattr(_tls, "sess"):
                del _tls.sess
            if attempt == max_attempts:
                return 0.0
            time.sleep(5 * attempt)
    return 0.0


# ── NEW: 60-day daily cost by ServiceFamily + MeterCategory ───────────────────

def _service_cost_query_with_retry(sub_id: str, sub_name: str, tenant_name: str,
                                    token: str, max_attempts: int = 5) -> list:
    """
    Queries 60 days of daily spend grouped by ServiceFamily + MeterCategory.
    Returns a list of row dicts ready to be written to SpendByService Delta table.

    Azure Cost Management returns columns in the order defined by aggregation +
    grouping. For this query the column order is:
      [0] Cost (float)
      [1] UsageDate (int, YYYYMMDD)
      [2] ServiceFamily (str)
      [3] MeterCategory (str)
    """
    today     = datetime.now(timezone.utc).date()
    date_from = (today - timedelta(days=59)).strftime("%Y-%m-%dT00:00:00Z")
    date_to   = today.strftime("%Y-%m-%dT23:59:59Z")

    url  = (
        f"https://management.azure.com/subscriptions/{sub_id}"
        f"/providers/Microsoft.CostManagement/query?api-version=2023-11-01"
    )
    body = json.dumps({
        "type":      "ActualCost",
        "timeframe": "Custom",
        "timePeriod": {"from": date_from, "to": date_to},
        "dataset": {
            "granularity": "Daily",
            "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
            "grouping": [
                {"type": "Dimension", "name": "ServiceFamily"},
                {"type": "Dimension", "name": "MeterCategory"},
            ],
        },
    })

    for attempt in range(1, max_attempts + 1):
        try:
            sess = _session(token)
            resp = sess.post(url, data=body, timeout=90)
            if resp.status_code == 429:
                if attempt == max_attempts:
                    return []
                wait = int(resp.headers.get("Retry-After", 30))
                time.sleep(wait)
                continue
            if resp.status_code in (400, 401, 403, 404):
                return []
            resp.raise_for_status()

            data = resp.json().get("properties", {})
            rows = data.get("rows", [])

            generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            result = []
            for row in rows:
                cost          = float(row[0]) if row[0] is not None else 0.0
                usage_date_i  = int(row[1])   # YYYYMMDD integer
                service_family = str(row[2] or "Unknown")
                meter_category = str(row[3] or "Unknown")
                usage_date_str = (
                    f"{str(usage_date_i)[:4]}-"
                    f"{str(usage_date_i)[4:6]}-"
                    f"{str(usage_date_i)[6:8]}"
                )
                result.append({
                    "subscription":    sub_name,
                    "subscriptionId":  sub_id,
                    "tenantName":      tenant_name,
                    "usageDate":       usage_date_str,
                    "serviceFamily":   service_family,
                    "meterCategory":   meter_category,
                    "cost":            round(cost, 4),
                    "generatedAt":     generated_at,
                })
            return result

        except requests.exceptions.HTTPError:
            return []
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            if hasattr(_tls, "sess"):
                del _tls.sess
            if attempt == max_attempts:
                return []
            time.sleep(5 * attempt)
    return []


# ── Budget fetch (unchanged) ───────────────────────────────────────────────────

def _fetch_budget(sub: dict, token: str) -> tuple:
    sub_id = sub["id"]
    try:
        resp = _session(token).get(
            f"https://management.azure.com/subscriptions/{sub_id}"
            f"/providers/Microsoft.Consumption/budgets?api-version=2021-10-01",
            timeout=30,
        )
        resp.raise_for_status()
        return sub_id, resp.json().get("value", [])
    except Exception:
        return sub_id, []


def get_all_budgets_parallel(subs: list, tokens: dict, workers: int = 50) -> dict:
    result = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_fetch_budget, sub, tokens[sub["tenantId"]]): sub["id"]
            for sub in subs if sub["tenantId"] in tokens
        }
        for future in as_completed(futures):
            sub_id, budgets = future.result()
            if budgets:
                result[sub_id.lower()] = budgets
    return result


# ── Budget row computation (unchanged) ────────────────────────────────────────

def compute_budget_rows(sub: dict, budgets: list, actual_cost: float,
                        days_passed: int, days_in_month: int, days_remaining: int) -> list:
    sub_name     = sub["name"]
    tenant_name  = TENANT_NAMES.get(sub["tenantId"], sub["tenantId"])
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []

    for budget in budgets:
        props      = budget.get("properties", {})
        amount     = float(props.get("amount", 0))
        daily_burn = actual_cost / days_passed if days_passed > 0 else 0.0
        projected  = round(daily_burn * days_in_month, 0)

        thresholds = []
        for notif in props.get("notifications", {}).values():
            pct    = float(notif.get("threshold", 0))
            emails = notif.get("contactEmails", [])
            thresholds.append({"pct": pct, "amt": round(amount * pct / 100, 0), "emails": "; ".join(emails)})
        thresholds.sort(key=lambda x: x["pct"])

        t1 = thresholds[0] if len(thresholds) >= 1 else None
        t2 = thresholds[1] if len(thresholds) >= 2 else None

        pct_used = round((actual_cost / amount) * 100, 1) if amount > 0 else 0.0

        t2_pct = t2["pct"] if t2 else 90
        t1_pct = t1["pct"] if t1 else 80
        if actual_cost > amount:
            status = "OVER BUDGET"
        elif pct_used >= t2_pct:
            status = "CRITICAL"
        elif pct_used >= t1_pct:
            status = "WARNING"
        else:
            status = "OK"

        def gap_and_days(t):
            if not t:
                return None, None
            gap  = round(t["amt"] - actual_cost, 0)
            days = round(gap / daily_burn, 0) if daily_burn > 0 and gap > 0 else (0 if gap <= 0 else None)
            return gap, days

        a1_gap, a1_days = gap_and_days(t1)
        a2_gap, a2_days = gap_and_days(t2)

        rows.append({
            "subscription":     sub_name,
            "tenantName":       tenant_name,
            "budgetName":       budget.get("name", ""),
            "budgetAmount":     round(amount, 2),
            "actualSpend":      round(actual_cost, 2),
            "pctUsed":          pct_used,
            "remainingUSD":     round(amount - actual_cost, 2),
            "dailyBurnRate":    round(daily_burn, 2),
            "projectedEOM":     projected,
            "daysRemaining":    days_remaining,
            "alert1Pct":        t1["pct"]    if t1 else None,
            "alert1Threshold":  t1["amt"]    if t1 else None,
            "alert1GapUSD":     a1_gap,
            "alert1DaysAway":   a1_days,
            "alert1Recipients": t1["emails"] if t1 else "",
            "alert2Pct":        t2["pct"]    if t2 else None,
            "alert2Threshold":  t2["amt"]    if t2 else None,
            "alert2GapUSD":     a2_gap,
            "alert2DaysAway":   a2_days,
            "status":           status,
            "generatedAt":      generated_at,
        })
    return rows


# ── Write helpers ──────────────────────────────────────────────────────────────

def write_to_lakehouse(json_str: str, stor_token: str, filename: str = OUTPUT_FILE) -> None:
    default_path = f"/lakehouse/default/Files/{filename}"
    try:
        if os.path.isdir("/lakehouse/default"):
            os.makedirs("/lakehouse/default/Files", exist_ok=True)
            with open(default_path, "w", encoding="utf-8") as f:
                f.write(json_str)
            print(f"  Written via local mount: {default_path}")
            return
    except Exception as e:
        print(f"  [Write] Local mount failed: {e}")

    abfss = (
        f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com"
        f"/{LAKEHOUSE_ID}/Files/{filename}"
    )
    for mod_name in ("notebookutils", "mssparkutils"):
        try:
            import importlib
            nu = importlib.import_module(mod_name)
            nu.fs.put(abfss, json_str, overwrite=True)
            print(f"  Written via {mod_name}.fs.put: {abfss}")
            return
        except (ImportError, Exception):
            pass

    base_url = (
        f"https://onelake.dfs.fabric.microsoft.com"
        f"/{WORKSPACE_ID}/{LAKEHOUSE_ID}/Files/{filename}"
    )
    h          = {"Authorization": f"Bearer {stor_token}", "x-ms-version": "2021-06-08"}
    file_bytes = json_str.encode("utf-8")
    requests.put(f"{base_url}?resource=file", headers=h, timeout=30).raise_for_status()
    requests.patch(
        f"{base_url}?action=append&position=0",
        headers={**h, "Content-Type": "application/octet-stream"},
        data=file_bytes, timeout=60,
    ).raise_for_status()
    requests.patch(
        f"{base_url}?action=flush&position={len(file_bytes)}",
        headers={**h, "Content-Length": "0"}, timeout=30,
    ).raise_for_status()
    print(f"  Written via OneLake DFS API: {len(file_bytes):,} bytes")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    start = time.time()
    ts    = lambda: f"{time.time() - start:.1f}s"

    today          = datetime.now()
    days_in_month  = (datetime(today.year, today.month % 12 + 1, 1) - datetime(today.year, today.month, 1)).days \
                     if today.month < 12 else 31
    days_passed    = today.day
    days_remaining = days_in_month - days_passed

    print("=" * 64)
    print("  Azure Budget & Cost Analyzer — Fabric Edition v2")
    print(f"  {today.strftime('%Y-%m-%d %H:%M')}  |  Day {days_passed}/{days_in_month}  ({days_remaining} days remaining)")
    print("=" * 64)

    print(f"\n[{ts()}] STEP 1/5 — Authenticating...")
    tokens = resolve_tokens()

    print(f"\n[{ts()}] STEP 2/5 — Discovering subscriptions...")
    all_subs = []
    for tid, tok in tokens.items():
        try:
            subs = get_subscriptions_for_tenant(tok, tid)
            print(f"  {TENANT_NAMES.get(tid, tid)}: {len(subs)} enabled subscriptions")
            all_subs.extend(subs)
        except Exception as e:
            print(f"  {TENANT_NAMES.get(tid, tid)}: FAILED — {e}")
    print(f"  Total: {len(all_subs)} subscriptions across {len(tokens)} tenant(s)")

    print(f"\n[{ts()}] STEP 3/5 — Fetching budgets (50 parallel workers)...")
    stor_executor = ThreadPoolExecutor(max_workers=1)
    stor_future   = stor_executor.submit(get_storage_token)

    budgets_by_sub = get_all_budgets_parallel(all_subs, tokens, workers=50)
    print(f"  {len(budgets_by_sub)} subscriptions have budgets  [{ts()}]")

    print(f"\n[{ts()}] STEP 3b/5 — Fetching actual MTD costs (8 workers)...")
    costs_by_sub = {}
    for tid, tok in tokens.items():
        tenant_label  = TENANT_NAMES.get(tid, tid)
        budgeted_subs = [s for s in all_subs if s["tenantId"] == tid and s["id"].lower() in budgets_by_sub]
        print(f"  {tenant_label}: querying {len(budgeted_subs)} budgeted subs...")
        with ThreadPoolExecutor(max_workers=8) as pool:
            futs = {pool.submit(_cost_query_with_retry, s["id"], tok): s["id"] for s in budgeted_subs}
            for fut in as_completed(futs):
                sid = futs[fut]
                try:
                    costs_by_sub[sid.lower()] = fut.result()
                except Exception as e:
                    print(f"  [Cost] {sid}: unhandled exception — {e}")
                    costs_by_sub[sid.lower()] = 0.0
        print(f"  {tenant_label}: done  [{ts()}]")

    # ── NEW STEP: 60-day daily spend by ServiceFamily + MeterCategory ─────────
    # Only runs for budgeted subscriptions to keep API call count manageable.
    # Uses 4 workers (lower than budget query) — this query is heavier per call.
    print(f"\n[{ts()}] STEP 4/5 — Fetching 60-day service breakdown (4 workers)...")
    all_service_rows = []
    for tid, tok in tokens.items():
        tenant_label  = TENANT_NAMES.get(tid, tid)
        budgeted_subs = [s for s in all_subs if s["tenantId"] == tid and s["id"].lower() in budgets_by_sub]
        print(f"  {tenant_label}: querying service breakdown for {len(budgeted_subs)} subs...")
        with ThreadPoolExecutor(max_workers=4) as pool:
            futs = {
                pool.submit(
                    _service_cost_query_with_retry,
                    s["id"], s["name"], TENANT_NAMES.get(tid, tid), tok
                ): s["id"]
                for s in budgeted_subs
            }
            for fut in as_completed(futs):
                sid = futs[fut]
                try:
                    rows = fut.result()
                    all_service_rows.extend(rows)
                except Exception as e:
                    print(f"  [SvcBreakdown] {sid}: unhandled exception — {e}")
        print(f"  {tenant_label}: done  [{ts()}]")
    print(f"  Total service breakdown rows: {len(all_service_rows):,}")

    # ── Build BudgetData rows (unchanged logic) ────────────────────────────────
    sub_map  = {s["id"].lower(): s for s in all_subs}
    all_rows = []
    for sub_id_lower, budgets in budgets_by_sub.items():
        sub = sub_map.get(sub_id_lower)
        if not sub:
            continue
        actual_cost = costs_by_sub.get(sub_id_lower, 0.0)
        all_rows.extend(compute_budget_rows(sub, budgets, actual_cost, days_passed, days_in_month, days_remaining))

    budgeted_count = len(budgets_by_sub)
    all_rows.sort(key=lambda r: r["pctUsed"], reverse=True)

    over = sum(1 for r in all_rows if r["status"] == "OVER BUDGET")
    crit = sum(1 for r in all_rows if r["status"] == "CRITICAL")
    warn = sum(1 for r in all_rows if r["status"] == "WARNING")
    ok   = sum(1 for r in all_rows if r["status"] == "OK")
    print(f"\n  Status: {over} OVER BUDGET  |  {crit} CRITICAL  |  {warn} WARNING  |  {ok} OK")

    # ── Write both tables ──────────────────────────────────────────────────────
    print(f"\n[{ts()}] STEP 5/5 — Writing to Fabric Lakehouse...")
    stor_token = stor_future.result()
    stor_executor.shutdown(wait=False)

    budget_json = json.dumps(all_rows, ensure_ascii=False, separators=(",", ":"))
    write_to_lakehouse(budget_json, stor_token, OUTPUT_FILE)

    service_json = json.dumps(all_service_rows, ensure_ascii=False, separators=(",", ":"))
    write_to_lakehouse(service_json, stor_token, OUTPUT_FILE_SVC)

    elapsed = round(time.time() - start, 1)
    print(f"""
{"=" * 64}
  COMPLETE — {elapsed}s
{"=" * 64}
  Subscriptions scanned       : {len(all_subs):>6,}
  Subscriptions budgeted      : {budgeted_count:>6,}
  Total budget rows           : {len(all_rows):>6,}
  OVER BUDGET                 : {over:>6,}
  CRITICAL                    : {crit:>6,}
  WARNING                     : {warn:>6,}
  OK                          : {ok:>6,}
  Service breakdown rows      : {len(all_service_rows):>6,}
{"=" * 64}
  Output 1: Files/{OUTPUT_FILE}
  Output 2: Files/{OUTPUT_FILE_SVC}
{"=" * 64}""")


try:
    main()
except Exception as e:
    print(f"BudgetAnalyzer v2 failed: {e}")
    raise


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Register both tables as Delta tables in the Lakehouse semantic model.
# Run this cell after the main() cell completes.

WORKSPACE_ID = "eca3c81e-a968-42a5-899f-d8fc1a45ebec"
LAKEHOUSE_ID = "84677723-0231-4f98-b71a-14879da990b8"

# BudgetData (unchanged)
budget_path = f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{LAKEHOUSE_ID}/Files/BudgetData.json"
df_budget = spark.read.option("multiLine", "true").json(budget_path)
df_budget.write.format("delta").mode("overwrite").saveAsTable("BudgetData")
print(f"BudgetData — {df_budget.count()} rows written")

# SpendByService (new)
svc_path = f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{LAKEHOUSE_ID}/Files/SpendByService.json"
df_svc = spark.read.option("multiLine", "true").json(svc_path)
df_svc.write.format("delta").mode("overwrite").saveAsTable("SpendByService")
print(f"SpendByService — {df_svc.count()} rows written")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
