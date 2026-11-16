# Run DCRG Test Suite
Write-Host "Running Backend Tests..." -ForegroundColor Cyan
Set-Location (Join-Path $PSScriptRoot "..\backend")
& ".\.venv\Scripts\python.exe" -m pytest tests -v

Write-Host "`nVerifying Frontend TypeScript Build..." -ForegroundColor Cyan
Set-Location (Join-Path $PSScriptRoot "..\frontend")
npm.cmd run build

