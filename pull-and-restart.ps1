#!/usr/bin/env pwsh
# Pull latest from git and restart servers

$ErrorActionPreference = "Stop"

Write-Host "📦 Pulling latest from origin..." -ForegroundColor Cyan
git pull origin main

Write-Host "🔨 Building cockpit..." -ForegroundColor Cyan
cd cockpit
npm run build
cd ..

Write-Host "🚀 Restarting server..." -ForegroundColor Cyan
.\restart-server-tmp.ps1

Write-Host "✅ Done! Server running on http://127.0.0.1:8731/cockpit" -ForegroundColor Green
