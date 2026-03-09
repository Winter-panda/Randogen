param(
  [int]$Port = 8010
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$backendDir = Join-Path $root "backend"
Set-Location $backendDir

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
  py -m venv .venv
}

$python = ".\.venv\Scripts\python.exe"

$env:DEBUG = "false"
$env:UV_CACHE_DIR = Join-Path $backendDir ".uv-cache"

$hasOrsKey = $false
if (-not [string]::IsNullOrWhiteSpace($env:ORS_API_KEY)) {
  $hasOrsKey = $true
}
elseif (Test-Path ".\.env") {
  $line = Get-Content ".\.env" | Where-Object {
    $_ -match "^\s*ORS_API_KEY\s*=" -and $_ -notmatch "^\s*#"
  } | Select-Object -First 1
  if ($line) {
    $value = (($line -split "=", 2)[1]).Trim()
    if (-not [string]::IsNullOrWhiteSpace($value) -and $value -notmatch "replace_with_your_openrouteservice_api_key") {
      $hasOrsKey = $true
    }
  }
}

if (-not $hasOrsKey) {
  Write-Host "WARN: ORS_API_KEY non configuree (backend/.env manquant ou vide)." -ForegroundColor Yellow
  Write-Host "      La generation utilisera le fallback mock (parcours carres/rectangles)." -ForegroundColor Yellow
}

& $python -m pip install -r requirements.txt
& $python -m uvicorn src.main.app:app --host 127.0.0.1 --port $Port
