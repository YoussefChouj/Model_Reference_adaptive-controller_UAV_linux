Write-Output "=== All serial/USB-serial class devices ==="
Get-PnpDevice -Class "Ports (COM & LPT)" -ErrorAction SilentlyContinue | Format-Table Status, FriendlyName, InstanceId -AutoSize

Write-Output "`n=== USB Serial Device candidates (any vendor) ==="
Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object {
    $_.InstanceId -match 'USB\\VID_[0-9A-F]{4}&PID_[0-9A-F]{4}'
} | Where-Object {
    $_.Class -match 'Ports' -or $_.FriendlyName -match 'Serial|USB|CH340|CP210|FTDI|Silicon|Bluetooth|UART'
} | Format-Table Status, Class, FriendlyName, InstanceId -AutoSize

Write-Output "`n=== USB enumeration (anything plugged in but not yet enumerated as COM) ==="
Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object {
    $_.InstanceId -match '^USB\\'
} | Where-Object {
    $_.Status -ne 'OK' -or $_.FriendlyName -match 'Serial|Unknown|Bluetooth|wireless|2\.4|GHz|RF'
} | Select-Object -First 40 | Format-Table Status, Class, FriendlyName, InstanceId -AutoSize

Write-Output "`n=== Bluetooth paired devices (radio might be a paired BT SPP) ==="
Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | Format-Table Status, FriendlyName -AutoSize
try {
    & bluetoothctl paired-devices 2>&1 | Select-String -Pattern "Device"
} catch { }