Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    $p = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
    $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($p.Id)" -ErrorAction SilentlyContinue).CommandLine
    Write-Host ("PID={0} Name={1} Started={2}" -f $p.Id, $p.ProcessName, $p.StartTime)
    Write-Host "  CMD: $cmd"
}