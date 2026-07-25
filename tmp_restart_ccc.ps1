# Restart ccc daemon and re-index
Write-Host "=== Restarting ccc daemon ==="
& "$env:LOCALAPPDATA\Programs\Python\Python313\Scripts\ccc.exe" daemon restart

Write-Host ""
Write-Host "=== Waiting for daemon to restart ==="
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "=== Re-indexing workspace ==="
& "$env:LOCALAPPDATA\Programs\Python\Python313\Scripts\ccc.exe" index

Write-Host ""
Write-Host "=== Doctor check ==="
& "$env:LOCALAPPDATA\Programs\Python\Python313\Scripts\ccc.exe" doctor
