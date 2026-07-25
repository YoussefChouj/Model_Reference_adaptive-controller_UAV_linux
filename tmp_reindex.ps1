# Full re-index to rebuild all chunks with the new model
Write-Host "=== Full re-index with OpenRouter gemini-embedding-001 ==="
Write-Host "Started at: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
& "$env:LOCALAPPDATA\Programs\Python\Python313\Scripts\ccc.exe" index
Write-Host "Finished at: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"

Write-Host ""
Write-Host "=== Final doctor check ==="
& "$env:LOCALAPPDATA\Programs\Python\Python313\Scripts\ccc.exe" doctor
