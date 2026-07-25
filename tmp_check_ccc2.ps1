# Check ccc help and config
Write-Host "=== ccc --help ==="
& "$env:LOCALAPPDATA\Programs\Python\Python313\Scripts\ccc.exe" --help

Write-Host ""
Write-Host "=== ccc index --help ==="
& "$env:LOCALAPPDATA\Programs\Python\Python313\Scripts\ccc.exe" index --help

Write-Host ""
Write-Host "=== Search for ccc config files ==="
$locations = @(
    "$env:USERPROFILE\.ccc",
    "$env:USERPROFILE\.config\ccc",
    "$env:APPDATA\ccc",
    "$env:LOCALAPPDATA\ccc",
    "$env:USERPROFILE\.config\config.json",
    "$env:USERPROFILE\AppData\Roaming\ccc"
)
foreach ($loc in $locations) {
    if (Test-Path $loc) {
        Write-Host "FOUND: $loc"
        Get-ChildItem $loc -Recurse -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host "=== Search for embedding model in ccc files ==="
$searchPaths = @(
    "$env:USERPROFILE\.ccc",
    "$env:LOCALAPPDATA\cocoindex",
    "$env:APPDATA\cocoindex"
)
foreach ($sp in $searchPaths) {
    if (Test-Path $sp) {
        Write-Host "Searching in: $sp"
        Get-ChildItem $sp -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
            $content = Get-Content $_.FullName -Raw -ErrorAction SilentlyContinue
            if ($content -match 'embedding|openrouter|nomic|model') {
                Write-Host "  => $($_.FullName)"
                Write-Host $content
            }
        }
    }
}
