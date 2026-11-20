# scripts/dev.ps1
# One-command development startup for Windows 11 PowerShell.
# Sets up Python virtualenv, installs dependencies, and launches backend & frontend.

$ErrorActionPreference = "Stop"

Write-Host "`n🚀 [Dev Environment] Starting GitHub Repo Profiler..." -ForegroundColor Cyan

$WorkspaceRoot = (Get-Item $PSScriptRoot).Parent.FullName
Set-Location $WorkspaceRoot

# 1. Python Virtual Environment
$VenvDir = Join-Path $WorkspaceRoot "venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    Write-Host "📦 Creating Python virtual environment in $VenvDir..." -ForegroundColor Yellow
    python -m venv $VenvDir
}

Write-Host "✅ Virtual environment ready." -ForegroundColor Green

# 2. Install Backend Dependencies
Write-Host "📦 Verifying backend dependencies..." -ForegroundColor Yellow
& $PythonExe -m pip install -q -r backend/requirements.txt

# 3. Verify Frontend Dependencies
$NodeModules = Join-Path $WorkspaceRoot "frontend\node_modules"
if (-not (Test-Path $NodeModules)) {
    Write-Host "📦 Installing frontend npm dependencies..." -ForegroundColor Yellow
    Set-Location (Join-Path $WorkspaceRoot "frontend")
    npm install
    Set-Location $WorkspaceRoot
}

# 4. Start Backend (port 8000)
Write-Host "`n🌐 Launching FastAPI Backend on http://localhost:8000..." -ForegroundColor Cyan
$BackendJob = Start-Process -FilePath $PythonExe -ArgumentList "-m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload" -WorkingDirectory (Join-Path $WorkspaceRoot "backend") -PassThru

# 5. Start Frontend (port 5173)
Write-Host "💻 Launching Vite React Frontend on http://localhost:5173..." -ForegroundColor Cyan
$FrontendJob = Start-Process -FilePath "npm" -ArgumentList "run dev" -WorkingDirectory (Join-Path $WorkspaceRoot "frontend") -PassThru

Write-Host "`n✨ Both servers are running!" -ForegroundColor Green
Write-Host "👉 Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "👉 Backend API Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host "`nPress Ctrl+C in this console or close the process windows to exit.`n" -ForegroundColor Gray

try {
    # Keep script open while processes run
    Wait-Process -Id $BackendJob.Id, $FrontendJob.Id
} finally {
    Write-Host "`n🛑 Shutting down development servers..." -ForegroundColor Yellow
    Stop-Process -Id $BackendJob.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $FrontendJob.Id -ErrorAction SilentlyContinue
}
