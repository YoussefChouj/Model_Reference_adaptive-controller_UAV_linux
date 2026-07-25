# Check cocoindex config for embedding model
Write-Host "=== .cocoindex_code/settings.yml ==="
if (Test-Path ".cocoindex_code/settings.yml") {
    Get-Content ".cocoindex_code/settings.yml"
}

Write-Host ""
Write-Host "=== cocoindex global config (AppData) ==="
$globalConfig = "$env:LOCALAPPDATA\cocoindex\config.json"
if (Test-Path $globalConfig) {
    Get-Content $globalConfig
} else {
    Write-Host "(not found at $globalConfig)"
}

Write-Host ""
Write-Host "=== ccc CLI info ==="
$cccPath = "$env:LOCALAPPDATA\Programs\Python\Python313\Scripts\ccc.exe"
if (Test-Path $cccPath) {
    & $cccPath --version 2>$null
    & $cccPath info 2>$null
} else {
    Write-Host "(ccc not found at $cccPath)"
}
