$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$model = "qwen3.5:2b-q4_K_M"

Set-Location -LiteralPath $repoRoot

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    throw "Ollama was not found. Install it first, then run: ollama pull $model"
}

$installedModels = & ollama list 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Ollama is unavailable. Start the local Ollama service first."
}
$installedModelText = $installedModels -join [Environment]::NewLine
if ($installedModelText -notmatch [regex]::Escape($model)) {
    throw "$model is not installed. Run: ollama pull $model"
}

$env:INCIDENT_LAB_ENABLE_OLLAMA = "1"
Write-Host "Starting local Ollama mode with $model" -ForegroundColor Cyan
python -m streamlit run streamlit_app.py
