param(
    [int]$Port = 18081
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

if (-not (Test-Path -Path "config.json")) {
    Copy-Item -Path "config.example.json" -Destination "config.json"
    Write-Host "Created config.json from config.example.json"
}

$env:HOST_PORT = $Port
docker compose up -d --build
Write-Host "gemini-web2api is running at http://localhost:$Port/v1"
Write-Host "Dashboard: http://localhost:$Port/dashboard"
Write-Host "Upstream: anonymous text-only; Cookie and file/image inputs are not supported"
