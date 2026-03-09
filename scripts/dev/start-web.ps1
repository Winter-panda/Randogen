param(
  [string]$ApiUrl = "http://127.0.0.1:8010/api",
  [int]$Port = 5174
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$webDir = Join-Path $root "apps\web"

Set-Content -Path (Join-Path $webDir ".env.local") -Encoding ascii -Value "VITE_API_URL=$ApiUrl"
Set-Location $webDir
npm install
npm run dev -- --host 127.0.0.1 --port $Port
