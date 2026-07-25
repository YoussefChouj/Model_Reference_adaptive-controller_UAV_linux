# Find cocoindex package location
Write-Host "=== Find cocoindex package ==="
$python313 = "C:\Users\Acer\AppData\Local\Programs\Python\Python313\python.exe"
if (Test-Path $python313) {
    & $python313 -c "import cocoindex_code; import inspect; print(inspect.getfile(cocoindex_code))"
} else {
    Write-Host "Python 3.13 not found at expected path"
}

Write-Host ""
Write-Host "=== Find ccc package ==="
& $python313 -c "import ccc; import inspect; print(inspect.getfile(ccc))"
