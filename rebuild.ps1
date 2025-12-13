# Rebuild Trends.exe
Set-Location "c:\Users\pi\Trends"

# Activate venv
& .\venv\Scripts\Activate.ps1

# Clean old build
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }

# Build
Write-Host "Building Trends.exe..." -ForegroundColor Cyan
pyinstaller trends.spec --clean --noconfirm

# Check result
if (Test-Path "dist\Trends.exe") {
    $file = Get-Item "dist\Trends.exe"
    Write-Host "`nBuild successful!" -ForegroundColor Green
    Write-Host "File: $($file.FullName)"
    Write-Host "Size: $([math]::Round($file.Length / 1MB, 1)) MB"
    Write-Host "Modified: $($file.LastWriteTime)"
} else {
    Write-Host "`nBuild FAILED!" -ForegroundColor Red
}

