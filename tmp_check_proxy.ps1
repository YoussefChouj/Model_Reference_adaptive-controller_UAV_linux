# Check proxy settings and re-run doctor
Write-Host "=== Current proxy env vars ==="
Get-ChildItem Env: | Where-Object { $_.Name -match 'PROXY|HTTP|HTTPS' } | ForEach-Object {
    Write-Host "$($_.Name) = $($_.Value)"
}

Write-Host ""
Write-Host "=== Test connectivity to OpenRouter ==="
try {
    $response = Invoke-WebRequest -Uri "https://openrouter.ai/api/v1/models" -TimeoutSec 10 -UseBasicParsing
    Write-Host "OpenRouter reachable: $($response.StatusCode)"
} catch {
    Write-Host "OpenRouter NOT reachable: $($_.Exception.Message)"
}

Write-Host ""
Write-Host "=== ccc doctor ==="
& "$env:LOCALAPPDATA\Programs\Python\Python313\Scripts\ccc.exe" doctor
