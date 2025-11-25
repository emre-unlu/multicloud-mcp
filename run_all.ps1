#Requires -Version 7
$ErrorActionPreference = "Stop"
$PSStyle.OutputRendering = "Ansi"

# Base paths
$RepoRoot = "C:\github\multicloud-mcp"
$K8sDir = Join-Path $RepoRoot "mcp\kubernetes"
$SupDir = Join-Path $RepoRoot "supervisor"

# First check if Ollama is running
$ollamaProc = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -like "*ollama*" }
if (-not $ollamaProc) {
    Write-Host "Starting Ollama..." -ForegroundColor Yellow
    Start-Process -WindowStyle Normal -FilePath "ollama" -ArgumentList "serve"
    Start-Sleep -Seconds 3
}

# Pull the models only if they're not already present
$modelsToEnsure = @('mistral:7b', 'qwen3:8b')
foreach ($model in $modelsToEnsure) {
    if (-not (ollama list | Select-String -Pattern "^$model(\s|$)")) {
        Write-Host "Model not found locally. Pulling $model..." -ForegroundColor Yellow
        ollama pull $model
    } else {
        Write-Host "Model $model already present. Skipping pull." -ForegroundColor Green
    }
}

# Start K8s MCP Server
Write-Host "Starting Kubernetes MCP Server..." -ForegroundColor Yellow
$k8sCmd = @"
Set-Location '$K8sDir'
& '${K8sDir}\.venv\Scripts\python.exe' server.py
Read-Host "Press Enter to exit"
"@
Start-Process -WindowStyle Normal -FilePath "powershell" -ArgumentList "-ExecutionPolicy Bypass -Command", $k8sCmd

# Start Supervisor
Write-Host "Starting Supervisor..." -ForegroundColor Yellow
$supCmd = @"
Set-Location '$RepoRoot'
`$env:MODEL = 'ollama:mistral:7b'
`$env:DIAGNOSTICS_MODEL = 'ollama:qwen3:8b'
& '${SupDir}\.venv\Scripts\uvicorn.exe' supervisor.app:app --reload --port 9000
Read-Host "Press Enter to exit"
"@
Start-Process -WindowStyle Normal -FilePath "powershell" -ArgumentList "-ExecutionPolicy Bypass -Command", $supCmd

# Start Go UI Server
Write-Host "Starting UI Server..." -ForegroundColor Yellow
$uiCmd = @"
Set-Location '$RepoRoot\app'
go run .
Read-Host "Press Enter to exit"
"@
Start-Process -WindowStyle Normal -FilePath "powershell" -ArgumentList "-Command", $uiCmd

Write-Host "`n✅ Services started:" -ForegroundColor Green
Write-Host "- Kubernetes MCP Server running in new window"
Write-Host "- Supervisor running in new window on http://127.0.0.1:9000"
Write-Host "- UI Server running in new window on http://127.0.0.1:8088"
