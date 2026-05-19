# ── Azure Token Refresh — MedInsight & Milliman ───────────────────────────────
#
# Generates tokens for two use cases:
#
#   [A] BudgetAnalyzer.py (management.azure.com)
#       Paste output into BudgetAnalyzer.py → TENANT_TOKENS
#
#   [B] Streamlit dashboards (Power BI / analysis.windows.net)
#       Paste output into Streamlit app → st.session_state or manual var
#
# Usage:
#   .\Get-Token.ps1              — get all tokens (default)
#   .\Get-Token.ps1 -Budget      — management tokens only (for BudgetAnalyzer)
#   .\Get-Token.ps1 -PowerBI     — Power BI token only   (for Streamlit)
#   .\Get-Token.ps1 -Login       — run az login first, then get tokens
#   .\Get-Token.ps1 -CopyBudget  — copy MedInsight management token to clipboard
# ─────────────────────────────────────────────────────────────────────────────

param(
    [switch]$Budget,
    [switch]$PowerBI,
    [switch]$Login,
    [switch]$CopyBudget
)

# Tenant IDs
$TENANT_MEDINSIGHT = "b2e2e6d4-979f-4671-aa72-0f0c494a0173"   # MedInsight Production (home)
$TENANT_MILLIMAN   = "e240d61e-61e3-4c9e-ab90-8644b2f4d2a9"   # Milliman Inc. / Fabric

# Resources
$RES_MGMT  = "https://management.azure.com/"
$RES_PBI   = "https://analysis.windows.net/powerbi/api"

Write-Host ""
Write-Host "  Azure Token Refresh" -ForegroundColor Cyan
Write-Host "  -------------------" -ForegroundColor DarkGray

# Check az CLI
if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    Write-Host "  [ERROR] Azure CLI not found." -ForegroundColor Red
    Write-Host "  Install: https://aka.ms/installazurecliwindows" -ForegroundColor Yellow
    exit 1
}

# Login if requested
if ($Login) {
    Write-Host ""
    Write-Host "  Logging in to MedInsight Production tenant..." -ForegroundColor Yellow
    Write-Host "  Sign in as: anmol.sharma@milliman.com" -ForegroundColor Gray
    Write-Host ""
    az login --tenant $TENANT_MEDINSIGHT --allow-no-subscriptions
    if ($LASTEXITCODE -ne 0) { Write-Host "  [ERROR] Login failed." -ForegroundColor Red; exit 1 }
}

# ── Helper: fetch one token ────────────────────────────────────────────────────
function Get-AzToken {
    param([string]$Resource, [string]$Tenant, [string]$Label)

    $json = az account get-access-token --resource $Resource --tenant $Tenant --output json 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [FAILED] $Label" -ForegroundColor Red
        Write-Host "           Run: .\Get-Token.ps1 -Login" -ForegroundColor Yellow
        return $null
    }

    $parsed = $json | ConvertFrom-Json
    $token  = $parsed.accessToken

    # Decode expiry from JWT
    try {
        $seg  = $token.Split(".")[1]
        $pad  = 4 - ($seg.Length % 4); if ($pad -ne 4) { $seg = $seg + ("=" * $pad) }
        $seg  = $seg.Replace("-", "+").Replace("_", "/")
        $dec  = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($seg)) | ConvertFrom-Json
        $exp  = [DateTimeOffset]::FromUnixTimeSeconds($dec.exp).LocalDateTime
        $mins = [math]::Round(($exp - (Get-Date)).TotalMinutes)
    } catch {
        $exp = $parsed.expiresOn; $mins = "?"
    }

    Write-Host "  [OK] $Label" -ForegroundColor Green
    Write-Host "       Expires: $exp  ($($mins) min remaining)" -ForegroundColor DarkGray
    return $token
}

# ── Fetch tokens ───────────────────────────────────────────────────────────────
$tokMgmtMedInsight = $null
$tokMgmtMilliman   = $null
$tokPBI            = $null

$doBudget  = $Budget  -or (-not $Budget -and -not $PowerBI)
$doPowerBI = $PowerBI -or (-not $Budget -and -not $PowerBI)

Write-Host ""

if ($doBudget) {
    Write-Host "  [A] Management API tokens (for BudgetAnalyzer.py)" -ForegroundColor White
    $tokMgmtMedInsight = Get-AzToken -Resource $RES_MGMT -Tenant $TENANT_MEDINSIGHT -Label "MedInsight Production  (b2e2e6d4)"
    $tokMgmtMilliman   = Get-AzToken -Resource $RES_MGMT -Tenant $TENANT_MILLIMAN   -Label "Milliman Inc.          (e240d61e)"
    Write-Host ""
}

if ($doPowerBI) {
    Write-Host "  [B] Power BI API token (for Streamlit dashboards)" -ForegroundColor White
    $tokPBI = Get-AzToken -Resource $RES_PBI -Tenant $TENANT_MILLIMAN -Label "Milliman / Fabric      (e240d61e)"
    Write-Host ""
}

# ── Output: paste-ready strings ───────────────────────────────────────────────
Write-Host "  ============================================================" -ForegroundColor DarkGray

if ($doBudget -and $tokMgmtMedInsight) {
    Write-Host ""
    Write-Host "  [A] PASTE INTO BudgetAnalyzer.py → TENANT_TOKENS" -ForegroundColor Yellow
    Write-Host "  ─────────────────────────────────────────────────" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host '  TENANT_TOKENS = {' -ForegroundColor White

    $mi_prev = $tokMgmtMedInsight.Substring(0,30) + "..." + $tokMgmtMedInsight.Substring($tokMgmtMedInsight.Length-8)
    Write-Host "      `"b2e2e6d4-979f-4671-aa72-0f0c494a0173`": `"$mi_prev`"," -ForegroundColor Cyan

    if ($tokMgmtMilliman) {
        $mil_prev = $tokMgmtMilliman.Substring(0,30) + "..." + $tokMgmtMilliman.Substring($tokMgmtMilliman.Length-8)
        Write-Host "      `"e240d61e-61e3-4c9e-ab90-8644b2f4d2a9`": `"$mil_prev`"," -ForegroundColor Cyan
    } else {
        Write-Host "      `"e240d61e-61e3-4c9e-ab90-8644b2f4d2a9`": `"`","  -ForegroundColor DarkGray
    }

    Write-Host '  }' -ForegroundColor White
    Write-Host ""
    Write-Host "  (tokens truncated above for display — full tokens set in env vars below)" -ForegroundColor DarkGray
}

if ($doPowerBI -and $tokPBI) {
    Write-Host ""
    Write-Host "  [B] POWER BI TOKEN (for Streamlit / manual curl)" -ForegroundColor Yellow
    Write-Host "  ─────────────────────────────────────────────────" -ForegroundColor DarkGray
    $pbi_prev = $tokPBI.Substring(0,30) + "..." + $tokPBI.Substring($tokPBI.Length-8)
    Write-Host "  $pbi_prev" -ForegroundColor Cyan
    Write-Host ""
}

# ── Set env vars for current session ──────────────────────────────────────────
Write-Host "  ============================================================" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Env vars set for this session:" -ForegroundColor White

if ($tokMgmtMedInsight) { $env:TOK_MGMT_MEDINSIGHT = $tokMgmtMedInsight; Write-Host "    `$env:TOK_MGMT_MEDINSIGHT  (management, MedInsight)" -ForegroundColor Gray }
if ($tokMgmtMilliman)   { $env:TOK_MGMT_MILLIMAN   = $tokMgmtMilliman;   Write-Host "    `$env:TOK_MGMT_MILLIMAN    (management, Milliman)"   -ForegroundColor Gray }
if ($tokPBI)            { $env:TOK_PBI              = $tokPBI;            Write-Host "    `$env:TOK_PBI               (Power BI, Milliman)"     -ForegroundColor Gray }

if ($CopyBudget -and $tokMgmtMedInsight) {
    $tokMgmtMedInsight | Set-Clipboard
    Write-Host ""
    Write-Host "  MedInsight management token copied to clipboard." -ForegroundColor Green
}

Write-Host ""
Write-Host "  Tip: run with -Login if you get auth errors" -ForegroundColor DarkGray
Write-Host ""
