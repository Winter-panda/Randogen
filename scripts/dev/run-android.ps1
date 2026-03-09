param(
  [string]$JavaHome = "",
  [string]$AndroidHome = ""
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$mobileDir = Join-Path $root "apps\mobile"

if ([string]::IsNullOrWhiteSpace($JavaHome)) {
  $candidates = @(
    "C:\Program Files\Android\Android Studio\jbr",
    "C:\Program Files\Android\Android Studio\jre",
    "C:\Program Files\Eclipse Adoptium\jdk-21*",
    "C:\Program Files\Microsoft\jdk-21*"
  )

  foreach ($candidate in $candidates) {
    if (Test-Path (Join-Path $candidate "bin\java.exe")) {
      $JavaHome = $candidate
      break
    }

    if ($candidate -like "*`**") {
      $resolved = Get-ChildItem -Path $candidate -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Path (Join-Path $_.FullName "bin\java.exe") } |
        Select-Object -First 1
      if ($resolved) {
        $JavaHome = $resolved.FullName
        break
      }
    }
  }
}

if ([string]::IsNullOrWhiteSpace($JavaHome) -or -not (Test-Path (Join-Path $JavaHome "bin\java.exe"))) {
  throw "JDK introuvable. Installe Android Studio (JBR) ou passe -JavaHome 'C:\path\to\jdk'."
}

$env:JAVA_HOME = $JavaHome
if (-not ($env:Path -split ";" | Where-Object { $_ -eq (Join-Path $env:JAVA_HOME "bin") })) {
  $env:Path = "$(Join-Path $env:JAVA_HOME "bin");$env:Path"
}

Set-Location $mobileDir
$androidDir = Join-Path $mobileDir "android"

if ([string]::IsNullOrWhiteSpace($AndroidHome)) {
  $sdkCandidates = @(
    (Join-Path $env:LOCALAPPDATA "Android\Sdk"),
    (Join-Path $env:USERPROFILE "AppData\Local\Android\Sdk"),
    "C:\Android\Sdk"
  )
  foreach ($candidate in $sdkCandidates) {
    if (Test-Path (Join-Path $candidate "platform-tools\adb.exe")) {
      $AndroidHome = $candidate
      break
    }
  }
}

if ([string]::IsNullOrWhiteSpace($AndroidHome) -or -not (Test-Path (Join-Path $AndroidHome "platform-tools\adb.exe"))) {
  throw "Android SDK introuvable. Installe Android SDK ou passe -AndroidHome 'C:\path\to\Sdk'."
}

$env:ANDROID_HOME = $AndroidHome
$env:ANDROID_SDK_ROOT = $AndroidHome
foreach ($segment in @(
  (Join-Path $env:ANDROID_HOME "platform-tools"),
  (Join-Path $env:ANDROID_HOME "emulator"),
  (Join-Path $env:ANDROID_HOME "cmdline-tools\latest\bin")
)) {
  if ((Test-Path $segment) -and -not ($env:Path -split ";" | Where-Object { $_ -eq $segment })) {
    $env:Path = "$segment;$env:Path"
  }
}

if (Test-Path $androidDir) {
  $escapedSdk = $env:ANDROID_HOME -replace "\\", "\\\\"
  Set-Content -Path (Join-Path $androidDir "local.properties") -Encoding ascii -Value "sdk.dir=$escapedSdk"
}

$devices = @()
try {
  $adbDevicesOutput = & adb devices
  foreach ($line in $adbDevicesOutput) {
    if ($line -match "^(\S+)\s+device$") {
      $devices += $Matches[1]
    }
  }
} catch {
  # fallback below
}

if ($devices.Count -gt 0) {
  npx cap run android --target $devices[0]
} else {
  npx cap run android
}
