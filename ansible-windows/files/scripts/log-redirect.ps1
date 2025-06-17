# Windows Log Redirection Script
# - Redirects Cloudbase-Init logs until completion or timeout
# - Redirects Windows boot logs (equivalent of journal logs)
# - Uses batching & chunking to handle VMware RPC throttling

# Set error action preference
$ErrorActionPreference = "Stop"

# Configuration
$BufferFile = "C:\TEMP\cloudinit-buffer.log"
$CloudbaseLog =  "C:\Program Files\Cloudbase Solutions\Cloudbase-Init\log\cloudbase-init.log"
$Rpctool = "C:\Program Files\VMware\VMware Tools\rpctool.exe"
$TimeoutMinutes = 15
$ChunkLineLimit = 40
$MaxChunkLength = 100

# Clean buffer 
Remove-Item -Path $BufferFile -ErrorAction SilentlyContinue
New-Item -Path $BufferFile -ItemType File -Force | Out-Null

# Flushing logic as the ScriptBlock
$FlushScript = {
    param($BufferFile, $Rpctool, $ChunkLineLimit, $MaxChunkLength)

    if (!(Test-Path $BufferFile)) { return }

    $lines = Get-Content -Path $BufferFile -ErrorAction SilentlyContinue
    if (-not $lines) { return }

    $chunks = @()
    $current = ""

    foreach ($line in $lines) {
        if (($current.Length + $line.Length + 1) -gt $MaxChunkLength -or ($chunks.Count -ge $ChunkLineLimit)) {
            if ($current) { $chunks += $current; $current = "" }
        }
        $current += if ($current) { "`n$line" } else { $line }
    }
    if ($current) { $chunks += $current }

    foreach ($chunk in $chunks) {
        try {
            & $Rpctool "log $chunk" | Out-Null
        } catch {
            Add-Content -Path $BufferFile -Value "[ERROR] RPCTool failed: $_"
        }
        Start-Sleep -Milliseconds 100
    }

    Clear-Content -Path $BufferFile -ErrorAction SilentlyContinue
}

# Tail Cloudbase-Init Logs
Start-Job -Name TailLogs -ScriptBlock {
    param($CloudbaseLog, $BufferFile)
    
    while(!(Test-Path $CloudbaseLog)) {
        Start-Sleep -Seconds 1
    }
    function WriteLogToBuffer {
        param($line, $BufferFile)
        if (-not [string]::IsNullOrWhiteSpace($_)) {
            Add-Content -Path $BufferFile -Value "[CLOUDBASE] $line"
        }
    }
    # Start tailing the file capturing the early logs if any
    Get-Content -Path $CloudbaseLog -Tail 200 -Wait | ForEach-Object {
        WriteLogToBuffer $_ $BufferFile
    }
} -ArgumentList $CloudbaseLog, $BufferFile | Out-Null

# Tail Critical Event Logs
Start-Job -Name TailEvents -ScriptBlock {
    param($BufferFile)
    while ($true) {
        try {
            $filter = @{
                LogName = @("System", "Application")
                Level = 1,2
                StartTime = (Get-Date).AddSeconds(-5)
            }
            Get-WinEvent -FilterHashtable $filter -MaxEvents 50 | ForEach-Object {
                $msg = "$($_.LevelDisplayName) $($_.TimeCreated) [$($_.ProviderName)] $($_.Message)"
                if (-not [string]::IsNullOrWhiteSpace($msg)) {
                    Add-Content -Path $BufferFile -Value "[EVENTLOG] $msg"
                }
            }
        } catch {
            Add-Content -Path $BufferFile -Value "[ERROR] Failed reading event logs: $_"
        }
        Start-Sleep -Seconds 5
    }
} -ArgumentList $BufferFile | Out-Null

# Periodic Flusher Job
Start-Job -Name Flusher -ScriptBlock {
    param($BufferFile, $Rpctool, $ChunkLineLimit, $MaxChunkLength)

    $Flush = {
        param($BufferFile, $Rpctool, $ChunkLineLimit, $MaxChunkLength)

        if (!(Test-Path $BufferFile)) { return }

        $lines = Get-Content -Path $BufferFile -ErrorAction SilentlyContinue
        if (-not $lines) { return }

        $chunks = @()
        $current = ""

        foreach ($line in $lines) {
            if (($current.Length + $line.Length + 1) -gt $MaxChunkLength -or ($chunks.Count -ge $ChunkLineLimit)) {
                if ($current) { $chunks += $current; $current = "" }
            }
            $current += if ($current) { "`n$line" } else { $line }
        }
        if ($current) { $chunks += $current }

        foreach ($chunk in $chunks) {
            try {
                & $Rpctool "log $chunk" | Out-Null
            } catch {
                Add-Content -Path $BufferFile -Value "[ERROR] Failed reading event logs: $_"
            }
            Start-Sleep -Milliseconds 100
        }

        Clear-Content -Path $BufferFile -ErrorAction SilentlyContinue
    }

    while ($true) {
        Start-Sleep -Seconds 1
        & $Flush $BufferFile $Rpctool $ChunkLineLimit $MaxChunkLength
    }
} -ArgumentList $BufferFile, $Rpctool, $ChunkLineLimit, $MaxChunkLength | Out-Null

# Completion Monitor
$StartTime = Get-Date
while ($true) {
    $cloudbaseDone = $false
    if (Test-Path $CloudbaseLog) {
        $last = Get-Content -Path $CloudbaseLog -Tail 50 -ErrorAction SilentlyContinue
        if ($last -match "Cloudbase-Init.*finished") {
            Add-Content -Path $BufferFile -Value "[INFO] Cloudbase-Init finished"
            $cloudbaseDone = $true
        }
    }

    if ($cloudbaseDone -or (New-TimeSpan -Start $StartTime -End (Get-Date)).TotalMinutes -ge $TimeoutMinutes) {
        if (-not $cloudbaseDone) {
            Add-Content -Path $BufferFile -Value "[INFO] Timeout reached"
        }
        break
    }
    Start-Sleep -Seconds 2
}

# Stop Jobs and Final Flush 
Start-Sleep -Seconds 3
Get-Job -Name TailLogs, TailEvents, Flusher | Stop-Job -ErrorAction SilentlyContinue

# Final flush using  flush logic
& $FlushScript $BufferFile $Rpctool $ChunkLineLimit $MaxChunkLength
Remove-Item $BufferFile -ErrorAction SilentlyContinue

# Stop service after completion
Stop-Service -Name logredirector
exit 0