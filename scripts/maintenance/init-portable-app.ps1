param(
  [string]$ProjectPath = "",
  [string]$BranchName = "portable-app",
  [string]$BackendApiUrl = "http://127.0.0.1:8010/api",
  [bool]$UseWorktree = $true,
  [switch]$SkipFrontendCopy
)

$ErrorActionPreference = "Stop"

function Write-AsciiFile {
  param(
    [string]$Path,
    [string]$Content
  )

  $directory = Split-Path -Path $Path -Parent
  if ($directory -and -not (Test-Path $directory)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
  }
  Set-Content -Path $Path -Value $Content -Encoding ascii
}

function Ensure-Directory {
  param([string]$Path)
  if (-not (Test-Path $Path)) {
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
  }
}

function Ensure-Worktree {
  param(
    [string]$RepoRoot,
    [string]$TargetPath,
    [string]$TargetBranch
  )

  if (Test-Path (Join-Path $TargetPath ".git")) {
    Write-Host "Using existing worktree at $TargetPath"
    return
  }

  if (Test-Path $TargetPath) {
    throw "Target path exists but is not a git worktree: $TargetPath"
  }

  & git -C $RepoRoot show-ref --verify --quiet "refs/heads/$TargetBranch"
  $branchExists = ($LASTEXITCODE -eq 0)

  if ($branchExists) {
    Write-Host "Adding worktree on existing branch '$TargetBranch'..."
    & git -C $RepoRoot worktree add $TargetPath $TargetBranch
  } else {
    Write-Host "Adding worktree and creating branch '$TargetBranch'..."
    & git -C $RepoRoot worktree add $TargetPath -b $TargetBranch
  }

  if ($LASTEXITCODE -ne 0) {
    throw "git worktree add failed."
  }
}

function Copy-FrontendSource {
  param(
    [string]$SourcePath,
    [string]$TargetPath
  )

  Ensure-Directory -Path $TargetPath

  & robocopy $SourcePath $TargetPath /E /NFL /NDL /NJH /NJS /NP `
    /XD node_modules dist .vite .turbo coverage .git `
    /XF dev-frontend.log

  # robocopy: 0..7 = success, >=8 = failure
  if ($LASTEXITCODE -ge 8) {
    throw "Failed to copy frontend to $TargetPath"
  }
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")

if ([string]::IsNullOrWhiteSpace($ProjectPath)) {
  $ProjectPath = Join-Path (Split-Path $repoRoot -Parent) "Randogen-portable"
}

if ($UseWorktree) {
  Ensure-Worktree -RepoRoot $repoRoot -TargetPath $ProjectPath -TargetBranch $BranchName
} else {
  Ensure-Directory -Path $ProjectPath
}

$projectRoot = Resolve-Path $ProjectPath
Write-Host "Portable project root: $projectRoot"

$appsDir = Join-Path $projectRoot "apps"
$packagesDir = Join-Path $projectRoot "packages"
$scriptsDir = Join-Path $projectRoot "scripts\dev"

Ensure-Directory -Path $appsDir
Ensure-Directory -Path $packagesDir
Ensure-Directory -Path $scriptsDir

$webDir = Join-Path $appsDir "web"
$mobileDir = Join-Path $appsDir "mobile"
$desktopDir = Join-Path $appsDir "desktop"
$sharedTypesDir = Join-Path $packagesDir "shared-types"
$engineSdkDir = Join-Path $packagesDir "engine-sdk"

if (-not $SkipFrontendCopy) {
  Write-Host "Copying frontend into apps/web..."
  Copy-FrontendSource -SourcePath (Join-Path $repoRoot "frontend") -TargetPath $webDir
} else {
  Ensure-Directory -Path $webDir
}

Ensure-Directory -Path (Join-Path $mobileDir "src")
Ensure-Directory -Path (Join-Path $desktopDir "src")
Ensure-Directory -Path (Join-Path $sharedTypesDir "src")
Ensure-Directory -Path (Join-Path $engineSdkDir "src")

Write-AsciiFile -Path (Join-Path $projectRoot ".gitignore") -Content @'
node_modules/
dist/
build/
.turbo/
.vite/
coverage/
*.log
.env.local
.DS_Store
Thumbs.db
'@

Write-AsciiFile -Path (Join-Path $projectRoot "package.json") -Content @'
{
  "name": "randogen-portable",
  "private": true,
  "version": "0.1.0",
  "workspaces": [
    "apps/*",
    "packages/*"
  ],
  "scripts": {
    "dev:web": "npm --workspace apps/web run dev -- --host 127.0.0.1 --port 5174",
    "build:web": "npm --workspace apps/web run build",
    "dev:mobile": "npm --workspace apps/mobile run dev",
    "dev:desktop": "npm --workspace apps/desktop run dev",
    "check": "npm run build:web"
  }
}
'@

Write-AsciiFile -Path (Join-Path $projectRoot "tsconfig.base.json") -Content @'
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM"],
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true
  }
}
'@

Write-AsciiFile -Path (Join-Path $projectRoot "README.portable.md") -Content @'
# Randogen Portable

Projet multi-support derive de Randogen pour viser:

- Web (PWA)
- Android / iOS (Capacitor)
- Windows / macOS / Linux (Tauri)

## Arborescence

```text
randogen-portable/
  apps/
    web/
    mobile/
    desktop/
  packages/
    shared-types/
    engine-sdk/
  scripts/
    dev/
```

## Demarrage rapide

1. Lancer le backend Randogen principal (port 8010).
2. Installer les deps du web portable:
   `cd apps/web && npm install`
3. Lancer le web portable:
   `npm run dev -- --host 127.0.0.1 --port 5174`

## Etapes suivantes

- brancher `apps/web` sur `packages/shared-types`
- initialiser Capacitor dans `apps/mobile`
- initialiser Tauri dans `apps/desktop`
- migrer progressivement le moteur vers `packages/engine-sdk`
'@

$routeTypesSource = Join-Path $repoRoot "frontend\src\types\route.ts"
$routeTypesTarget = Join-Path $sharedTypesDir "src\route.ts"
if (Test-Path $routeTypesSource) {
  Copy-Item -Path $routeTypesSource -Destination $routeTypesTarget -Force
} else {
  Write-AsciiFile -Path $routeTypesTarget -Content @'
export interface UserPosition {
  latitude: number;
  longitude: number;
}
'@
}

Write-AsciiFile -Path (Join-Path $sharedTypesDir "src\index.ts") -Content @'
export * from "./route";
'@

Write-AsciiFile -Path (Join-Path $sharedTypesDir "package.json") -Content @'
{
  "name": "@randogen/shared-types",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "files": ["dist"],
  "scripts": {
    "build": "tsc -p tsconfig.json"
  },
  "devDependencies": {
    "typescript": "^5.6.3"
  }
}
'@

Write-AsciiFile -Path (Join-Path $sharedTypesDir "tsconfig.json") -Content @'
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "rootDir": "src",
    "outDir": "dist",
    "declaration": true
  },
  "include": ["src"]
}
'@

Write-AsciiFile -Path (Join-Path $engineSdkDir "src\types.ts") -Content @'
import type {
  GenerateRoutesRequest,
  GenerateRoutesResponse,
  PointOfInterest,
  WeatherData
} from "@randogen/shared-types";

export interface NearbyPoiOptions {
  radiusKm?: number;
  limit?: number;
  categories?: Array<
    "viewpoint" | "water" | "summit" | "nature" | "heritage" | "facility" | "start_access"
  >;
}

export interface RouteEngine {
  generateRoutes(payload: GenerateRoutesRequest): Promise<GenerateRoutesResponse>;
  fetchNearbyPois(lat: number, lon: number, options?: NearbyPoiOptions): Promise<PointOfInterest[]>;
  fetchWeather(lat: number, lon: number): Promise<WeatherData | null>;
  exportRouteGpx(stableRouteId: string, userId?: string): Promise<Blob>;
}
'@

Write-AsciiFile -Path (Join-Path $engineSdkDir "src\remoteEngine.ts") -Content @'
import type {
  GenerateRoutesRequest,
  GenerateRoutesResponse,
  PointOfInterest,
  WeatherData
} from "@randogen/shared-types";
import type { NearbyPoiOptions, RouteEngine } from "./types";

export class RemoteEngine implements RouteEngine {
  constructor(private readonly apiBaseUrl: string) {}

  async generateRoutes(payload: GenerateRoutesRequest): Promise<GenerateRoutesResponse> {
    const response = await fetch(`${this.apiBaseUrl}/routes/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(`generateRoutes failed (${response.status})`);
    return (await response.json()) as GenerateRoutesResponse;
  }

  async fetchNearbyPois(lat: number, lon: number, options?: NearbyPoiOptions): Promise<PointOfInterest[]> {
    const params = new URLSearchParams();
    params.set("lat", String(lat));
    params.set("lon", String(lon));
    params.set("radius_km", String(options?.radiusKm ?? 5));
    params.set("limit", String(options?.limit ?? 250));
    for (const category of options?.categories ?? []) params.append("categories", category);
    const response = await fetch(`${this.apiBaseUrl}/routes/pois/nearby?${params.toString()}`);
    if (!response.ok) throw new Error(`fetchNearbyPois failed (${response.status})`);
    return (await response.json()) as PointOfInterest[];
  }

  async fetchWeather(lat: number, lon: number): Promise<WeatherData | null> {
    const response = await fetch(`${this.apiBaseUrl}/routes/weather?lat=${lat}&lon=${lon}`);
    if (!response.ok) return null;
    return (await response.json()) as WeatherData;
  }

  async exportRouteGpx(stableRouteId: string, userId?: string): Promise<Blob> {
    const suffix = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
    const response = await fetch(`${this.apiBaseUrl}/routes/${encodeURIComponent(stableRouteId)}/export.gpx${suffix}`);
    if (!response.ok) throw new Error(`exportRouteGpx failed (${response.status})`);
    return await response.blob();
  }
}
'@

Write-AsciiFile -Path (Join-Path $engineSdkDir "src\localEngine.ts") -Content @'
import type { RouteEngine } from "./types";

export class LocalEngine implements RouteEngine {
  private unsupported(op: string): never {
    throw new Error(`LocalEngine not implemented yet: ${op}`);
  }

  async generateRoutes() {
    this.unsupported("generateRoutes");
  }

  async fetchNearbyPois() {
    this.unsupported("fetchNearbyPois");
  }

  async fetchWeather() {
    this.unsupported("fetchWeather");
  }

  async exportRouteGpx() {
    this.unsupported("exportRouteGpx");
  }
}
'@

Write-AsciiFile -Path (Join-Path $engineSdkDir "src\index.ts") -Content @'
export type * from "./types";
export * from "./remoteEngine";
export * from "./localEngine";
'@

Write-AsciiFile -Path (Join-Path $engineSdkDir "package.json") -Content @'
{
  "name": "@randogen/engine-sdk",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "files": ["dist"],
  "scripts": {
    "build": "tsc -p tsconfig.json"
  },
  "dependencies": {
    "@randogen/shared-types": "0.1.0"
  },
  "devDependencies": {
    "typescript": "^5.6.3"
  }
}
'@

Write-AsciiFile -Path (Join-Path $engineSdkDir "tsconfig.json") -Content @'
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "rootDir": "src",
    "outDir": "dist",
    "declaration": true
  },
  "include": ["src"]
}
'@

Write-AsciiFile -Path (Join-Path $mobileDir "package.json") -Content @'
{
  "name": "@randogen/mobile",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "npm run doctor",
    "doctor": "echo \"Run npm run init:capacitor when web build is ready\"",
    "init:capacitor": "npx cap init Randogen com.randogen.app --web-dir=../web/dist",
    "sync": "npx cap sync",
    "open:android": "npx cap open android",
    "open:ios": "npx cap open ios"
  },
  "dependencies": {
    "@capacitor/core": "^7.0.0"
  },
  "devDependencies": {
    "@capacitor/cli": "^7.0.0"
  }
}
'@

Write-AsciiFile -Path (Join-Path $mobileDir "README.md") -Content @'
# Mobile shell (Capacitor)

This folder is reserved for Android/iOS packaging.

Quick commands:

- npm run init:capacitor
- npm run sync
- npm run open:android
- npm run open:ios
'@

Write-AsciiFile -Path (Join-Path $desktopDir "package.json") -Content @'
{
  "name": "@randogen/desktop",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "npm run doctor",
    "doctor": "echo \"Run npm run init:tauri when web build is ready\"",
    "init:tauri": "npx tauri init --ci",
    "tauri:dev": "npx tauri dev",
    "tauri:build": "npx tauri build"
  },
  "devDependencies": {
    "@tauri-apps/cli": "^2.0.0"
  }
}
'@

Write-AsciiFile -Path (Join-Path $desktopDir "README.md") -Content @'
# Desktop shell (Tauri)

This folder is reserved for Windows/macOS/Linux packaging.

Quick commands:

- npm run init:tauri
- npm run tauri:dev
- npm run tauri:build
'@

Write-AsciiFile -Path (Join-Path $scriptsDir "start-web.ps1") -Content @'
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
'@

if (Test-Path $webDir) {
  Write-AsciiFile -Path (Join-Path $webDir ".env.local") -Content "VITE_API_URL=$BackendApiUrl"
}

Write-Host ""
Write-Host "Portable scaffold ready."
Write-Host "Project: $projectRoot"
Write-Host ""
Write-Host "Next:"
Write-Host "  1) cd $projectRoot\apps\web"
Write-Host "  2) npm install"
Write-Host "  3) npm run dev -- --host 127.0.0.1 --port 5174"
Write-Host ""
Write-Host "Backend API URL written in apps\web\.env.local => $BackendApiUrl"
