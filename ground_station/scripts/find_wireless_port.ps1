Write-Output "=== ALL ports/devices that might be a wireless UART ==="
Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object {
    $_.Status -eq 'OK' -and (
        $_.Class -match 'Ports|Bluetooth|CDC|USB' -or
        $_.FriendlyName -match 'Serial|UART|Wireless|COM|Radio|BT|nRF|SiK|Si1000'
    )
} | Sort-Object Class, FriendlyName | Format-Table Status, Class, FriendlyName, InstanceId -AutoSize

Write-Output "`n=== ALL COM port numbers currently registered in registry ==="
Get-ChildItem 'HKLM:\HARDWARE\DEVICEMAP\SERIALCOMM' -ErrorAction SilentlyContinue |
    ForEach-Object { Write-Output "  $($_.Property[0])" }

Write-Output "`n=== USB devices with multiple interfaces (look for wireless debugger) ==="
Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object {
    $_.InstanceId -match '^USB\\VID_[0-9A-F]{4}&PID_[0-9A-F]{4}&MI_'
} | Group-Object { ($_.InstanceId -split '\\')[1] } | ForEach-Object {
    $grp = $_.Group
    if ($grp.Count -gt 0) {
        Write-Output "Device $($_.Name) has $($grp.Count) interfaces:"
        $grp | ForEach-Object {
            Write-Output ("  IF {0}: {1} ({2})" -f ($_.InstanceId -split '&MI_')[1].Substring(0,2), $_.FriendlyName, $_.Class)
        }
    }
}