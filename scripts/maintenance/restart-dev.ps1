param(
  [int]$BackendPort = 8010,
  [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"

function Stop-ListeningProcesses {
  param([int[]]$Ports)

  foreach ($port in $Ports) {
    $listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if (-not $listeners) { continue }

    $pids = $listeners | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $pids) {
      if (-not $procId -or $procId -eq $PID) { continue }
      try {
        Stop-Process -Id $procId -Force -ErrorAction Stop
        Write-Host "Stopped PID $procId on port $port"
      } catch {
        Write-Warning "Could not stop PID $procId on port ${port}: $($_.Exception.Message)"
      }
    }
  }
}

function Stop-RandogenProcesses {
  param(
    [string]$BackendDir,
    [string]$FrontendDir
  )

  $toStop = New-Object System.Collections.Generic.List[int]
  $backendPrefix = (Resolve-Path $BackendDir).Path
  $frontendPrefix = (Resolve-Path $FrontendDir).Path

  foreach ($proc in Get-Process -ErrorAction SilentlyContinue) {
    try {
      if ($proc.ProcessName -eq "uvicorn") {
        $toStop.Add($proc.Id)
        continue
      }

      $path = $proc.Path
      if (-not $path) { continue }
      if ($path.StartsWith($backendPrefix, [System.StringComparison]::OrdinalIgnoreCase) -or
          $path.StartsWith($frontendPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        $toStop.Add($proc.Id)
      }
    } catch {
      # Ignore access-denied processes
    }
  }

  foreach ($id in ($toStop | Sort-Object -Unique)) {
    if ($id -eq $PID) { continue }
    try {
      Stop-Process -Id $id -Force -ErrorAction Stop
      Write-Host "Stopped project PID $id"
    } catch {
      Write-Warning "Could not stop project PID ${id}: $($_.Exception.Message)"
    }
  }
}

function Wait-ForPort {
  param(
    [int]$Port,
    [int]$TimeoutSeconds = 20
  )
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($listener) { return $true }
    Start-Sleep -Milliseconds 400
  }
  return $false
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"
$envLocalPath = Join-Path $frontendDir ".env.local"

Write-Host "Stopping previous servers..."
Stop-ListeningProcesses -Ports @($BackendPort, 8000, $FrontendPort)
Stop-RandogenProcesses -BackendDir $backendDir -FrontendDir $frontendDir

Write-Host "Writing frontend API URL..."
Set-Content -Path $envLocalPath -Value "VITE_API_URL=http://127.0.0.1:$BackendPort/api" -Encoding ascii

Write-Host "Starting backend window..."
$venvPython = Join-Path $backendDir ".venv\Scripts\python.exe"
$uvCacheDir = Join-Path $backendDir ".uv-cache"
$npmCacheDir = Join-Path $repoRoot ".npm-cache"
if (-not (Test-Path $uvCacheDir)) {
  New-Item -ItemType Directory -Path $uvCacheDir | Out-Null
}
if (-not (Test-Path $npmCacheDir)) {
  New-Item -ItemType Directory -Path $npmCacheDir | Out-Null
}
$backendCmd = "title Randogen Backend && cd /d `"$backendDir`" && set `"DEBUG=false`" && set `"UV_CACHE_DIR=$uvCacheDir`" && `"$venvPython`" -m uvicorn src.main.app:app --host 127.0.0.1 --port $BackendPort"
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", $backendCmd

Write-Host "Starting frontend window..."
$frontendCmd = "title Randogen Frontend && cd /d `"$frontendDir`" && set `"npm_config_cache=$npmCacheDir`" && npm run dev -- --host 127.0.0.1 --port $FrontendPort"
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", $frontendCmd

$backendReady = Wait-ForPort -Port $BackendPort -TimeoutSeconds 60
$frontendReady = Wait-ForPort -Port $FrontendPort -TimeoutSeconds 45

Write-Host ""
Write-Host "Backend : $(if ($backendReady) { "UP" } else { "DOWN" }) on http://127.0.0.1:$BackendPort"
Write-Host "Frontend: $(if ($frontendReady) { "UP" } else { "DOWN" }) on http://127.0.0.1:$FrontendPort"
Write-Host ""
Write-Host "If one service is DOWN, check the opened backend/frontend windows for the exact error."
