#Requires -Version 7
$ErrorActionPreference = "Stop"
$PSStyle.OutputRendering = "Ansi"

# Base paths
$RepoRoot = "C:\multicloud-mcp"
$K8sDir = Join-Path $RepoRoot "mcp\kubernetes"
$SupDir = Join-Path $RepoRoot "supervisor"

# First check if Ollama is running
$ollamaProc = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -like "*ollama*" }
if (-not $ollamaProc) {
    Write-Host "Starting Ollama..." -ForegroundColor Yellow
    Start-Process -WindowStyle Normal -FilePath "ollama" -ArgumentList "serve"
    Start-Sleep -Seconds 3
}

# Pull the model
Write-Host "Pulling Ollama model..." -ForegroundColor Yellow
ollama pull llama3.1:8b

# Start K8s MCP Server
Write-Host "Starting Kubernetes MCP Server..." -ForegroundColor Yellow
$k8sCmd = @"
Set-Location '$K8sDir'
& '${K8sDir}\.venv\Scripts\Activate.ps1'
python server.py
"@
Start-Process -WindowStyle Normal -FilePath "powershell" -ArgumentList "-Command", $k8sCmd

# Start Supervisor
Write-Host "Starting Supervisor..." -ForegroundColor Yellow
$supCmd = @"
Set-Location '$RepoRoot'
& '${SupDir}\.venv\Scripts\Activate.ps1'
`$env:MODEL = 'ollama:llama3.1:8b'
uvicorn supervisor.app:app --reload --port 9000
"@
Start-Process -WindowStyle Normal -FilePath "powershell" -ArgumentList "-Command", $supCmd

# Start Go UI Server
Write-Host "Starting UI Server..." -ForegroundColor Yellow
$uiCmd = @"
Set-Location '$RepoRoot\app'
go run .
"@
Start-Process -WindowStyle Normal -FilePath "powershell" -ArgumentList "-Command", $uiCmd

Write-Host "`n✅ Services started:" -ForegroundColor Green
Write-Host "- Kubernetes MCP Server running in new window"
Write-Host "- Supervisor running in new window on http://127.0.0.1:9000"
Write-Host "- UI Server running in new window on http://127.0.0.1:8088"
