$ErrorActionPreference = "Stop"

$jobScript = "C:\Users\lcrettol\Documents\Codex\2026-08-25\i-am-working-on-this-spreadsheet\outputs\run_pairwise_current_flow.jl"
$logDirectory = "C:\cheetah\circuitscape\outputs"
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$transcript = Join-Path $logDirectory "pairwise_current_flow_console.log"
Start-Transcript -Path $transcript -Append

try {
    $julia = Get-Command julia -ErrorAction SilentlyContinue
    if (-not $julia) {
        Write-Host "Julia was not found. Installing the official Julia distribution with Juliaup..."
        winget install --name Julia --id 9NJNWW8PVKMN -e -s msstore --accept-source-agreements --accept-package-agreements

        $windowsApps = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps"
        if ($env:Path -notlike "*$windowsApps*") {
            $env:Path = "$windowsApps;$env:Path"
        }
        $julia = Get-Command julia -ErrorAction SilentlyContinue
    }

    if (-not $julia) {
        throw "Julia installation finished but julia is not visible yet. Close this window, restart Windows once, and rerun the same ArcGIS command."
    }

    Write-Host "Julia executable: $($julia.Source)"
    Write-Host "Starting all four pairwise current-flow runs. This is a long-running job."
    $nativeLog = Join-Path $logDirectory "pairwise_current_flow_native.log"
    # Julia/Circuitscape writes ordinary informational log records to stderr.
    # Windows PowerShell 5 converts those records into PowerShell errors when
    # stderr is merged into a pipeline, so temporarily allow them through and
    # use the native process exit code as the actual success/failure signal.
    $savedErrorPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $julia.Source --threads=auto $jobScript 2>&1 | Tee-Object -FilePath $nativeLog -Append
        $juliaExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $savedErrorPreference
    }
    if ($juliaExitCode -ne 0) {
        throw "Julia/Circuitscape exited with code $juliaExitCode"
    }
}
finally {
    Stop-Transcript
}

Write-Host "Complete. You may close this window."
Read-Host "Press Enter to close"
