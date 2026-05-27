# Fabric notebook source

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
Azure Budget & Cost Analysis — Fabric Notebook Edition

─── HOW TO RUN IN FABRIC ────────────────────────────────────────────────────
This notebook queries subscriptions across three Azure tenants.

MedInsight Production authenticates automatically via service principal.
Fill in CLIENT_ID and CLIENT_SECRET in SERVICE_PRINCIPALS below.

MedInsight Engineering — reader access via DefaultAzureCredential (az login).
Fill in SP creds if available, or leave blank to use DefaultAzureCredential.

Milliman tenant (optional) — either fill in its SP creds too, or paste a
token into TENANT_TOKENS, or leave blank to skip.

Standalone local usage:
    pip install requests azure-identity
    python BudgetAnalyzer.py
─────────────────────────────────────────────────────────────────────────────
"""

import json
import os
import time
import math
import threading
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

# Suppress azure-identity verbose credential chain errors (expected in Fabric)
logging.getLogger("azure.identity").setLevel(logging.CRITICAL)
logging.getLogger("azure.core").setLevel(logging.CRITICAL)

# ── Configuration ─────────────────────────────────────────────────────────────

# Tenant display names
TENANT_NAMES = {
    "b2e2e6d4-979f-4671-aa72-0f0c494a0173": "MedInsight Production",
    "e240d61e-61e3-4c9e-ab90-8644b2f4d2a9": "Milliman Inc.",
    "ff6598a3-6053-498d-a3b0-54295c0ce494": "MedInsight Engineering",
}

# OneLake target — update LAKEHOUSE_ID after creating your Lakehouse in Fabric
WORKSPACE_ID = "eca3c81e-a968-42a5-899f-d8fc1a45ebec"
LAKEHOUSE_ID = "84677723-0231-4f98-b71a-14879da990b8"   # Azure_Storage_enumeration Lakehouse
OUTPUT_FILE  = "BudgetData.json"

MAX_WORKERS  = 50    # increased — budget list API is lenient; cost queries only run for budgeted subs

# ── SERVICE PRINCIPAL CONFIGURATION ──────────────────────────────────────────
# Set CLIENT_ID + CLIENT_SECRET (or CERTIFICATE_PATH) for each tenant that has
# an SP. Leave CLIENT_SECRET as "" to skip SP auth for that tenant.

SERVICE_PRINCIPALS = {
    "b2e2e6d4-979f-4671-aa72-0f0c494a0173": {   # MedInsight Production
        "client_id":     "37b785ce-3326-45f3-a251-28202711dd6f",
        "client_secret": os.getenv("AZURE_CLIENT_SECRET", ""),   # Use environment variable
    },
    "ff6598a3-6053-498d-a3b0-54295c0ce494": {   # MedInsight Engineering (reader via az login / DefaultAzureCredential)
        "client_id":     "",
        "client_secret": "",
    },
    "e240d61e-61e3-4c9e-ab90-8644b2f4d2a9": {   # Milliman Inc. (optional)
        "client_id":     "",
        "client_secret": "",
    },
}

# ── FALLBACK: manual token paste ──────────────────────────────────────────────
# Only needed if you are NOT using service principals above.
# Leave as "" to use SP creds or DefaultAzureCredential.

TENANT_TOKENS = {
    "b2e2e6d4-979f-4671-aa72-0f0c494a0173": "",   # MedInsight Production
    "ff6598a3-6053-498d-a3b0-54295c0ce494": "",   # MedInsight Engineering (optional override)
    "e240d61e-61e3-4c9e-ab90-8644b2f4d2a9": "",   # Milliman Inc. (optional)
}

# ── Authentication ─────────────────────────────────────────────────────────────

def resolve_tokens() -> dict:
    """
    Returns {tenant_id: token} for all configured tenants.
    Priority: pasted token → service principal → DefaultAzureCredential.
    """
    all_tenant_ids = set(TENANT_TOKENS) | set(SERVICE_PRINCIPALS)
    resolved = {}

    for tenant_id in all_tenant_ids:
        name = TENANT_NAMES.get(tenant_id, tenant_id)

        # 1 — pasted token (manual override, highest priority)
        pasted = TENANT_TOKENS.get(tenant_id, "")
        if pasted and pasted.strip():
            resolved[tenant_id] = pasted.strip()
            print(f"  [Auth] {name}: using pasted token")
            continue

        # 2 — service principal (ClientSecretCredential)
        sp = SERVICE_PRINCIPALS.get(tenant_id, {})
        if sp.get("client_id") and sp.get("client_secret"):
            try:
                from azure.identity import ClientSecretCredential
                cred  = ClientSecretCredential(
                    tenant_id=tenant_id,
                    client_id=sp["client_id"],
                    client_secret=sp["client_secret"],
                )
                token = cred.get_token("https://management.azure.com/.default").token
                resolved[tenant_id] = token
                print(f"  [Auth] {name}: token via service principal")
                continue
            except Exception as e:
                print(f"  [Auth] {name}: SP auth failed — {e}")

        # 3 — DefaultAzureCredential (works locally with az login)
        try:
            from azure.identity import DefaultAzureCredential
            cred  = DefaultAzureCredential()
            token = cred.get_token(
                "https://management.azure.com/.default",
                tenant_id=tenant_id,
            ).token
            resolved[tenant_id] = token
            print(f"  [Auth] {name}: token via DefaultAzureCredential")
        except Exception as e:
            print(f"  [Auth] {name}: SKIPPED — {e}")

    if not resolved:
        raise RuntimeError(
            "No tokens available. Fill in SERVICE_PRINCIPALS, paste tokens into "
            "TENANT_TOKENS, or run locally with az login."
        )
    return resolved


def get_storage_token() -> str:
    """OneLake / storage token — Milliman tenant, so notebookutils works."""
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


# ── Step 1: Discover subscriptions per tenant ─────────────────────────────────

def get_subscriptions_for_tenant(token: str, tenant_id: str) -> list:
    """Returns list of {id, name, tenantId} for all enabled subs in this tenant."""
    subs = []
    url  = "https://management.azure.com/subscriptions?api-version=2022-12-01"
    hdrs = {"Authorization": f"Bearer {token}"}
    while url:
        resp = requests.get(url, headers=hdrs, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        for s in data.get("value", []):
            if s.get("state") == "Enabled":
                subs.append({
                    "id":       s["subscriptionId"],
                    "name":     s.get("displayName", s["subscriptionId"]),
                    "tenantId": tenant_id,
                })
        url = data.get("nextLink")
    return subs


# ── Step 2: Budget + Cost query ───────────────────────────────────────────────

_tls = threading.local()

def _session(token: str) -> requests.Session:
    if not hasattr(_tls, "sess") or getattr(_tls, "token", None) != token:
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        _tls.sess  = s
        _tls.token = token
    return _tls.sess


def _cost_query_with_retry(sub_id: str, token: str, max_attempts: int = 5) -> float:
    """Per-subscription MTD actual cost from Cost Management API."""
    url  = (
        f"https://management.azure.com/subscriptions/{sub_id}"
        f"/providers/Microsoft.CostManagement/query?api-version=2023-11-01"
    )
    body = json.dumps({
        "type": "ActualCost",
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
                retry_after = int(resp.headers.get("Retry-After", 0))
                # FIX: respect the full Retry-After value — capping at 30s caused all retries
                # to fire too early, exhausting all attempts and returning 0.0 for ~200 subs.
                wait = retry_after if retry_after > 0 else 30
                time.sleep(wait)
                continue
            resp.raise_for_status()
            rows = resp.json().get("properties", {}).get("rows", [])
            return float(rows[0][0]) if rows else 0.0
        except requests.exceptions.HTTPError as e:
            # 4xx/5xx — retrying won't help, return immediately
            print(f"  [Cost] {sub_id} HTTP {e.response.status_code if e.response is not None else '?'}: giving up")
            return 0.0
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            if hasattr(_tls, "sess"):
                del _tls.sess
            if attempt == max_attempts:
                return 0.0
            time.sleep(5 * attempt)
    return 0.0


def _fetch_budget(sub: dict, token: str) -> tuple:
    """Returns (sub_id, budgets_list). Uses thread-local session for connection pooling."""
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
    """Returns {sub_id_lower: [budget_dicts]} for all subs that have at least one budget."""
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


# ── FIX: actual_cost now comes from Cost Management API (matches Azure portal) ──
def compute_budget_rows(sub: dict, budgets: list, actual_cost: float,
                        days_passed: int, days_in_month: int, days_remaining: int) -> list:
    """Pure computation — no API calls. actual_cost sourced from Cost Management API."""
    sub_name     = sub["name"]
    tenant_name  = TENANT_NAMES.get(sub["tenantId"], sub["tenantId"])
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []

    for budget in budgets:
        props       = budget.get("properties", {})
        amount      = float(props.get("amount", 0))
        daily_burn  = actual_cost / days_passed if days_passed > 0 else 0.0
        projected   = round(daily_burn * days_in_month, 0)

        thresholds = []
        for notif in props.get("notifications", {}).values():
            pct    = float(notif.get("threshold", 0))
            emails = notif.get("contactEmails", [])
            thresholds.append({
                "pct":    pct,
                "amt":    round(amount * pct / 100, 0),
                "emails": "; ".join(emails),
            })
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


# ── Step 3: Write to Fabric Lakehouse ─────────────────────────────────────────

def write_to_lakehouse(json_str: str, stor_token: str) -> None:
    """Write BudgetData.json to OneLake — same 3-path strategy as StorageLifecycleAnalyzer."""

    # Option A: direct mount (Fabric notebook with attached Lakehouse)
    default_path = f"/lakehouse/default/Files/{OUTPUT_FILE}"
    try:
        if os.path.isdir("/lakehouse/default"):
            os.makedirs("/lakehouse/default/Files", exist_ok=True)
            with open(default_path, "w", encoding="utf-8") as f:
                f.write(json_str)
            print(f"  Written via local mount: {default_path}")
            return
    except Exception as e:
        print(f"  [Write] Local mount failed: {e}")

    # Option B: notebookutils / mssparkutils
    abfss = (
        f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com"
        f"/{LAKEHOUSE_ID}/Files/{OUTPUT_FILE}"
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

    # Option C: OneLake DFS REST API
    base_url = (
        f"https://onelake.dfs.fabric.microsoft.com"
        f"/{WORKSPACE_ID}/{LAKEHOUSE_ID}/Files/{OUTPUT_FILE}"
    )
    h = {"Authorization": f"Bearer {stor_token}", "x-ms-version": "2021-06-08"}
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
    print("  Azure Budget & Cost Analyzer — Fabric Edition")
    print(f"  {today.strftime('%Y-%m-%d %H:%M')}  |  Day {days_passed}/{days_in_month}  ({days_remaining} days remaining)")
    print("=" * 64)

    # Auth
    print(f"\n[{ts()}] STEP 1/4 — Authenticating...")
    tokens = resolve_tokens()

    # Subscriptions
    print(f"\n[{ts()}] STEP 2/4 — Discovering subscriptions...")
    all_subs = []
    for tid, tok in tokens.items():
        try:
            subs = get_subscriptions_for_tenant(tok, tid)
            print(f"  {TENANT_NAMES.get(tid, tid)}: {len(subs)} enabled subscriptions")
            all_subs.extend(subs)
        except Exception as e:
            print(f"  {TENANT_NAMES.get(tid, tid)}: FAILED — {e}")
    print(f"  Total: {len(all_subs)} subscriptions across {len(tokens)} tenant(s)")

    # STEP 3: parallel budget fetch + storage token
    print(f"\n[{ts()}] STEP 3/4 — Fetching budgets (50 parallel workers)...")

    stor_executor = ThreadPoolExecutor(max_workers=1)
    stor_future   = stor_executor.submit(get_storage_token)

    budgets_by_sub = get_all_budgets_parallel(all_subs, tokens, workers=50)
    print(f"  {len(budgets_by_sub)} subscriptions have budgets  [{ts()}]")

    # FIX: reduced to 8 workers (was 20) to avoid triggering Azure Cost Management rate limits.
    # With 20 workers firing ~200 simultaneous queries, Azure returned 429 for many subs.
    # The old code capped Retry-After at 30s, so all 5 retries fired too early → 0.0.
    # 8 workers keeps request bursts within Azure's per-SP rate limit window.
    print(f"\n[{ts()}] STEP 3b/4 — Fetching actual costs (per-subscription, 8 workers)...")
    costs_by_sub = {}
    for tid, tok in tokens.items():
        tenant_label = TENANT_NAMES.get(tid, tid)
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

    covered = sum(1 for sid in budgets_by_sub if costs_by_sub.get(sid, 0.0) > 0)
    print(f"  Cost coverage: {covered}/{len(budgets_by_sub)} budgeted subs have non-zero MTD spend")

    # Compute rows
    sub_map  = {s["id"].lower(): s for s in all_subs}
    all_rows = []
    for sub_id_lower, budgets in budgets_by_sub.items():
        sub = sub_map.get(sub_id_lower)
        if not sub:
            continue
        actual_cost = costs_by_sub.get(sub_id_lower, 0.0)
        all_rows.extend(compute_budget_rows(sub, budgets, actual_cost, days_passed, days_in_month, days_remaining))

    budgeted_count = len(budgets_by_sub)
    print(f"  Found {len(all_rows)} budget rows across {budgeted_count} subscriptions")

    all_rows.sort(key=lambda r: r["pctUsed"], reverse=True)

    over = sum(1 for r in all_rows if r["status"] == "OVER BUDGET")
    crit = sum(1 for r in all_rows if r["status"] == "CRITICAL")
    warn = sum(1 for r in all_rows if r["status"] == "WARNING")
    ok   = sum(1 for r in all_rows if r["status"] == "OK")
    print(f"\n  Status: {over} OVER BUDGET  |  {crit} CRITICAL  |  {warn} WARNING  |  {ok} OK")

    # Write to Lakehouse
    print(f"\n[{ts()}] STEP 4/4 — Writing to Fabric Lakehouse...")
    json_str   = json.dumps(all_rows, ensure_ascii=False, separators=(",", ":"))
    stor_token = stor_future.result()
    stor_executor.shutdown(wait=False)
    write_to_lakehouse(json_str, stor_token)

    elapsed = round(time.time() - start, 1)
    print(f"""
{"=" * 64}
  COMPLETE — {elapsed}s
{"=" * 64}
  Subscriptions scanned  : {len(all_subs):>6,}
  Subscriptions budgeted : {budgeted_count:>6,}
  Total budget rows      : {len(all_rows):>6,}
  OVER BUDGET            : {over:>6,}
  CRITICAL               : {crit:>6,}
  WARNING                : {warn:>6,}
  OK                     : {ok:>6,}
{"=" * 64}
  Output: Files/{OUTPUT_FILE}
{"=" * 64}""")


try:
    main()
except Exception as e:
    print(f"BudgetAnalyzer failed: {e}")
    raise


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

WORKSPACE_ID = "eca3c81e-a968-42a5-899f-d8fc1a45ebec"
LAKEHOUSE_ID = "84677723-0231-4f98-b71a-14879da990b8"

path = f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{LAKEHOUSE_ID}/Files/BudgetData.json"

df = spark.read.option("multiLine", "true").json(path)
df.write.format("delta").mode("overwrite").saveAsTable("BudgetData")
print(f"Done — {df.count()} rows written to BudgetData table")



# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
