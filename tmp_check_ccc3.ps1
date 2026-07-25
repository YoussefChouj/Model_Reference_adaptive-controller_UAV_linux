# Check ccc doctor and status
Write-Host "=== ccc doctor ==="
& "$env:LOCALAPPDATA\Programs\Python\Python313\Scripts\ccc.exe" doctor

Write-Host ""
Write-Host "=== ccc status ==="
& "$env:LOCALAPPDATA\Programs\Python\Python313\Scripts\ccc.exe" status

Write-Host ""
Write-Host "=== Search Python site-packages for cocoindex config ==="
$sitePackages = python -c "import site; print(site.getsitepackages()[0])"
if ($sitePackages) {
    $cp = [System.IO.Path]::GetDirectoryName($sitePackages)
    Get-ChildItem $cp -Filter "*.py" -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'cocoindex|ccc' } | ForEach-Object {
        Write-Host "Found: $($_.FullName)"
    }
    $cccDir = Join-Path $cp "ccc"
    if (Test-Path $cccDir) {
        Write-Host "ccc module dir: $cccDir"
        Get-ChildItem $cccDir -File -ErrorAction SilentlyContinue
    }
}
