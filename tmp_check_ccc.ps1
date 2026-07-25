# Check ccc CLI config and environment variables
Write-Host "=== ccc CLI location ==="
$cccPath = "$env:LOCALAPPDATA\Programs\Python\Python313\Scripts\ccc.exe"
Write-Host $cccPath

Write-Host ""
Write-Host "=== ccc --version ==="
& $cccPath --version

Write-Host ""
Write-Host "=== ccc info ==="
& $cccPath info

Write-Host ""
Write-Host "=== ccc env ==="
& $cccPath env 2>$null

Write-Host ""
Write-Host "=== Environment: OPENROUTER ==="
Get-ChildItem Env: | Where-Object { $_.Name -match 'OPENROUTER|EMBEDDING|MODEL|CCC' }

Write-Host ""
Write-Host "=== ccc config file locations ==="
& $cccPath config list 2>$null
