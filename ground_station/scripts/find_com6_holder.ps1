$ports = Get-CimInstance Win32_SerialPort -ErrorAction SilentlyContinue
foreach ($p in $ports) {
    Write-Output "Port=$($p.DeviceID) Desc=$($p.Description)"

    # Find processes holding the port via kernel handles
    $handleQuery = @"
SELECT ProcessId, Name FROM Win32_Process
"@
}
Write-Output "---"
Write-Output "Active COM ports:"
& mode 2>&1 | Select-String "COM"
Write-Output "---"
# Check who has COM6 open (any process with handle to COM6 device)
Write-Output "Looking for processes with handles to COM6..."
$devs = & handle64 2>&1 | Select-String "COM6" -Context 0,3
Write-Output $devs