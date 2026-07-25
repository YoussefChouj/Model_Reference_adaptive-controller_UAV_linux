# Search cocoindex_code for embedding model options
$pkgPath = "C:\Users\Acer\AppData\Local\Programs\Python\Python313\Lib\site-packages\cocoindex_code"
Write-Host "=== Files in cocoindex_code ==="
Get-ChildItem $pkgPath -File -Recurse -ErrorAction SilentlyContinue | Select-Object FullName

Write-Host ""
Write-Host "=== Search for 'openrouter' in cocoindex_code ==="
Get-ChildItem $pkgPath -File -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
    $content = Get-Content $_.FullName -Raw -ErrorAction SilentlyContinue
    if ($content -and $content.ToString().Contains("openrouter")) {
        Write-Host "FOUND in: $($_.FullName)"
        Write-Host $content
    }
}

Write-Host ""
Write-Host "=== Search for 'sentence-transformers' ==="
Get-ChildItem $pkgPath -File -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
    $content = Get-Content $_.FullName -Raw -ErrorAction SilentlyContinue
    if ($content -and $content.ToString().Contains("sentence-transformers")) {
        Write-Host "FOUND in: $($_.FullName)"
        $lines = $content -split "`n" | Select-Object -First 5
        $lines | ForEach-Object { Write-Host $_ }
    }
}
