<#
  Doc-mate local dev launcher.

    .\dev.ps1           start Postgres + MinIO, migrate, seed if empty, open backend + frontend windows
    .\dev.ps1 -Seed     same, but always run the seeders
    .\dev.ps1 -Stop     stop the containers (data volumes are kept)

  Backend  -> http://localhost:8000  (API docs at /docs)
  Frontend -> http://localhost:3000  (reception@demo / doctor@demo, password demo1234)
#>
param(
    [switch]$Seed,
    [switch]$Stop
)

$ErrorActionPreference = 'Stop'
$root     = $PSScriptRoot
$compose  = Join-Path $root 'infra\docker-compose.yml'
$backend  = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$python   = Join-Path $backend '.venv\Scripts\python.exe'

function Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Fail($msg) { Write-Host "xx  $msg" -ForegroundColor Red; exit 1 }

if ($Stop) {
    Step 'Stopping containers (volumes kept)'
    docker compose -f $compose down
    Write-Host 'Close the backend and frontend windows (Ctrl+C) to stop them.'
    exit 0
}

# --- 1. Docker ---------------------------------------------------------------
Step 'Checking Docker'
docker info *> $null
if ($LASTEXITCODE -ne 0) { Fail 'Docker is not responding. Start Docker Desktop and re-run.' }

# Refuse to start on top of another project's containers; never stop them.
$owners = docker ps --format '{{.Names}} {{.Ports}}'
foreach ($port in 5432, 9000, 9001) {
    $clash = $owners | Where-Object { $_ -match ":$port->" -and $_ -notmatch '^docmate-' }
    if ($clash) { Fail "Port $port is already used by: $($clash.Split(' ')[0]). Stop that project first (this script will not touch it)." }
}

Step 'Starting Postgres + MinIO'
docker compose -f $compose up -d
if ($LASTEXITCODE -ne 0) { Fail 'docker compose up failed.' }

Step 'Waiting for Postgres'
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    docker exec docmate-postgres pg_isready -U docmate -d docmate *> $null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 1
}
if (-not $ready) { Fail 'Postgres did not become ready in 30s. Check: docker logs docmate-postgres' }

# --- 2. Backend: migrate + seed ----------------------------------------------
if (-not (Test-Path $python)) { Fail "Backend venv not found at $python" }

Step 'Running migrations'
Push-Location $backend
try {
    & $python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { Fail 'alembic upgrade failed.' }

    $count = docker exec docmate-postgres psql -U docmate -d docmate -tAc 'SELECT count(*) FROM patients' 2>$null
    if ($Seed -or "$count".Trim() -eq '0') {
        Step 'Seeding demo data'
        foreach ($s in 'scripts.seed', 'scripts.seed_demo', 'scripts.seed_cohort') {
            & $python -m $s
            if ($LASTEXITCODE -ne 0) { Fail "$s failed." }
        }
    } else {
        Step "Database already has $("$count".Trim()) patients, skipping seed (use -Seed to force)"
    }
} finally { Pop-Location }

# --- 3. Frontend prerequisites -----------------------------------------------
$envLocal = Join-Path $frontend '.env.local'
$apiLine  = 'NEXT_PUBLIC_API_URL=http://localhost:8000'
if (-not (Test-Path $envLocal) -or -not (Select-String -Path $envLocal -SimpleMatch $apiLine -Quiet)) {
    Step 'Writing frontend/.env.local'
    Set-Content -Path $envLocal -Value $apiLine -Encoding utf8
}
if (-not (Test-Path (Join-Path $frontend 'node_modules'))) {
    Step 'Installing frontend packages'
    Push-Location $frontend; npm install; Pop-Location
}

# --- 4. Launch servers in their own windows ----------------------------------
Step 'Starting backend on :8000 (new window)'
Start-Process powershell -WorkingDirectory $backend -ArgumentList '-NoExit', '-Command',
    "`$host.UI.RawUI.WindowTitle='doc-mate backend'; & '$python' -m uvicorn app.main:app --reload --port 8000"

Step 'Starting frontend on :3000 (new window)'
Start-Process powershell -WorkingDirectory $frontend -ArgumentList '-NoExit', '-Command',
    "`$host.UI.RawUI.WindowTitle='doc-mate frontend'; npm run dev"

Write-Host ''
Write-Host 'Doc-mate is starting:' -ForegroundColor Green
Write-Host '  App       http://localhost:3000   (reception@demo / doctor@demo, password demo1234)'
Write-Host '  API docs  http://localhost:8000/docs'
Write-Host '  MinIO     http://localhost:9001   (minioadmin / minioadmin)'
Write-Host 'Stop with:  .\dev.ps1 -Stop   (then close the two server windows)'
