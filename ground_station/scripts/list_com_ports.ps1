$ports = [System.IO.Ports.SerialPort]::GetPortNames()
Write-Output "All COM ports known to Windows:"
foreach ($p in $ports) {
    try {
        $sp = New-Object System.IO.Ports.SerialPort $p, 115200
        $sp.Open()
        $sp.Close()
        Write-Output "  $p  : opens cleanly"
    } catch {
        Write-Output "  $p  : $($_.Exception.Message)"
    }
}
Write-Output "---"
Write-Output "PnpDevices (USB-Serial adapters + radios):"
Get-PnpDevice -Class Ports -ErrorAction SilentlyContinue | Format-Table Status, Class, FriendlyName, InstanceId -AutoSize
Write-Output "---"
Write-Output "FTDI devices:"
Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -match 'FTDIBUS|VID_0403' } | Format-Table Status, FriendlyName, InstanceId