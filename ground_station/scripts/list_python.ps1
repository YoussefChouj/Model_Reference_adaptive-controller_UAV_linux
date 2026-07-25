$procs = Get-Process python -ErrorAction SilentlyContinue
foreach ($p in $procs) {
    try {
        $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId = $($p.Id)" -ErrorAction SilentlyContinue).CommandLine
        Write-Output "PID=$($p.Id) Cmd=$cmd"
    } catch {
        Write-Output "PID=$($p.Id) (no cmdline)"
    }
}