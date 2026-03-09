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

& $python -m pip install -r requirements.txt
& $python -m uvicorn src.main.app:app --host 127.0.0.1 --port $Port
