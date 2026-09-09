$ErrorActionPreference = "Stop"

$jobScript = "C:\Users\lcrettol\Documents\Codex\2026-08-25\i-am-working-on-this-spreadsheet\outputs\run_final_pairwise_current_flow.jl"
$logDirectory = "C:\cheetah\circuitscape\outputs\final_balanced_fence_documented"
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$transcript = Join-Path $logDirectory "final_pairwise_current_flow_console.log"
Start-Transcript -Path $transcript -Append

try {
    $julia = Get-Command julia -ErrorAction SilentlyContinue
    if (-not $julia) {
        throw "Julia was not found. Re-run the earlier Circuitscape installation script or restart Windows so Julia becomes available."
    }
    Write-Host "Julia executable: $($julia.Source)"
    Write-Host "Starting four FINAL pairwise current-flow runs. This is a long-running job."
    Write-Host "Scenario: vegetation-balanced + documented finite KAZA/Kruger fences."
    $nativeLog = Join-Path $logDirectory "final_pairwise_current_flow_native.log"
    $savedErrorPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $julia.Source --threads=auto $jobScript 2>&1 | Tee-Object -FilePath $nativeLog -Append
        $juliaExitCode = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $savedErrorPreference }
    if ($juliaExitCode -ne 0) { throw "Julia/Circuitscape exited with code $juliaExitCode" }
}
finally { Stop-Transcript }

Write-Host "Complete. You may close this window."
Read-Host "Press Enter to close"
