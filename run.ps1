<#
    Start SIMBA. One flow, one command, cleaned up on Ctrl+C.

        .\run.ps1                 registration replica, hardcoded plan
        .\run.ps1 billing         billing replica, hardcoded plan
        .\run.ps1 railways        the live public site, read-only, hardcoded plan
        .\run.ps1 mock            overlay + scripted backend, nothing real

    .\run.ps1 mock -Seconds 20 starts everything, waits, and shuts down again.
    A smoke test: it proves the pieces come up and that cleanup works, without
    a person having to press anything.

    The hardcoded plan is the default everywhere on purpose: it spends no API
    quota and it is deterministic, so a run that misbehaves is the system's
    fault rather than the model's. For the LLM, set
    $env:SIMBA_USE_HARDCODED_PLAN = "0" first.

    See RUNNING.md for what each flow shows and what to do when one fails.
#>

[CmdletBinding()]
param(
    [ValidateSet("registration", "billing", "railways", "mock")]
    [string]$Flow = "registration",

    # Run for this many seconds and then shut down. 0 means run until Ctrl+C.
    [int]$Seconds = $(if ($env:SIMBA_RUN_SECONDS) { [int]$env:SIMBA_RUN_SECONDS } else { 0 })
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$BackendPort = if ($env:SIMBA_BACKEND_PORT) { $env:SIMBA_BACKEND_PORT } else { "8000" }
$CdpPort = if ($env:SIMBA_CDP_PORT) { $env:SIMBA_CDP_PORT } else { "9222" }
$Hardcoded = if ($null -ne $env:SIMBA_USE_HARDCODED_PLAN) { $env:SIMBA_USE_HARDCODED_PLAN } else { "1" }
$PlannerName = if ($Hardcoded -eq "1") { "hardcoded (no API quota spent)" } else { "LLM (spends API quota)" }

# Electron reads this and runs as plain Node when it is set: no window, no
# CDP, and an error naming our entry point rather than the real cause. Some
# editors set it in their integrated terminal, which is exactly where someone
# is most likely to run this. Removed for child processes only.
Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue

$Started = [System.Collections.ArrayList]::new()
$Ports = [System.Collections.ArrayList]::new()
$Stopped = $false

function Say([string]$Message) { Write-Host "==> $Message" -ForegroundColor Cyan }
function Warn([string]$Message) { Write-Host "!! $Message" -ForegroundColor Yellow }
function Die([string]$Message) { Write-Host "!! $Message" -ForegroundColor Red; throw $Message }

function Get-PortOwners([string]$Port) {
    netstat -ano |
        Select-String "LISTENING" |
        Select-String ":$Port\s" |
        ForEach-Object { ($_ -split '\s+')[-1] } |
        Sort-Object -Unique
}

function Stop-Port([string]$Port) {
    # By listening port rather than by recorded pid, because the thing to stop
    # is rarely the thing that was started: npm.cmd becomes node becomes
    # electron.exe plus five helpers, and none of those die when their
    # launcher does. The port reaches whatever is actually holding it, and
    # /T takes that process's tree with it. The pre-flight check below is what
    # makes this safe: anything on these ports is ours.
    foreach ($owner in Get-PortOwners $Port) {
        if ($owner -match '^\d+$') { & taskkill /F /T /PID $owner *> $null }
    }
}

function Stop-Everything {
    if ($script:Stopped) { return }
    $script:Stopped = $true

    Write-Host ""
    Say "stopping"
    foreach ($proc in $Started) {
        try {
            if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction Stop }
        } catch {}
    }
    foreach ($port in $Ports) { Stop-Port $port }
    Say "stopped"
}

# The backend's venv if it exists, so nobody has to remember to activate it.
if (Test-Path "backend\venv\Scripts\python.exe") {
    $Py = (Resolve-Path "backend\venv\Scripts\python.exe").Path
} else {
    $Py = "python"
    Warn "no backend\venv found, using 'python' from PATH"
}

function Start-Tracked([string]$File, [string[]]$Arguments, [hashtable]$Variables = @{}, [string]$Cwd = $PSScriptRoot) {
    # Not $Args: that is an automatic variable, and naming a parameter after
    # it means the caller's array never arrives -- Start-Process then rejects
    # a null ArgumentList and the whole launcher dies one line in.
    #
    # Environment is set, inherited by the child, and put back. Leaving it set
    # would hand the next process someone else's PORT.
    $previous = @{}
    foreach ($key in $Variables.Keys) {
        $previous[$key] = [Environment]::GetEnvironmentVariable($key)
        Set-Item -Path "Env:$key" -Value $Variables[$key]
    }
    try {
        $proc = Start-Process -FilePath $File -ArgumentList $Arguments -WorkingDirectory $Cwd -NoNewWindow -PassThru
    } finally {
        foreach ($key in $Variables.Keys) {
            if ($null -eq $previous[$key]) { Remove-Item "Env:$key" -ErrorAction SilentlyContinue }
            else { Set-Item -Path "Env:$key" -Value $previous[$key] }
        }
    }
    [void]$Started.Add($proc)
    return $proc
}

function Wait-For([string]$Url, [string]$What, [int]$Limit = 60) {
    for ($waited = 0; $waited -lt $Limit; $waited++) {
        try {
            Invoke-WebRequest -Uri $Url -TimeoutSec 2 -UseBasicParsing | Out-Null
            Say "$What is up"
            return
        } catch {
            # A 4xx still means something is listening.
            if ($_.Exception.Response) { Say "$What is up"; return }
        }
        Start-Sleep -Seconds 1
    }
    Die "$What did not come up at $Url after ${Limit}s - see the output above"
}

function Start-Replica([string]$Name, [string]$Port) {
    Say "starting the $Name replica on :$Port"
    [void]$Ports.Add($Port)
    Start-Tracked $Py @("replicas\$Name\app.py") @{ PORT = $Port } | Out-Null
    Wait-For "http://127.0.0.1:$Port/" "the $Name replica" 30
}

function Start-Host([string]$StartUrl) {
    if (-not (Test-Path "frontend\node_modules")) {
        Say "installing frontend dependencies (first run only)"
        Start-Process -FilePath "npm.cmd" -ArgumentList @("install") -WorkingDirectory "$PSScriptRoot\frontend" -NoNewWindow -Wait
    }
    Say "starting the Electron host (builds first, ~10s)"
    [void]$Ports.Add($CdpPort)
    Start-Tracked "npm.cmd" @("start") @{ SIMBA_START_URL = $StartUrl; SIMBA_CDP_PORT = $CdpPort } "$PSScriptRoot\frontend" | Out-Null
    Wait-For "http://127.0.0.1:$CdpPort/json/version" "the host (CDP $CdpPort)" 120
}

function Start-Backend([string]$FlowName) {
    Say "starting the backend on :$BackendPort - flow=$FlowName, planner=$PlannerName"
    [void]$Ports.Add($BackendPort)
    Start-Tracked $Py @("-m", "uvicorn", "backend.orchestrator.app:app", "--port", $BackendPort) @{
        SIMBA_FLOW               = $FlowName
        SIMBA_BROWSER            = "electron"
        SIMBA_CDP_URL            = "http://127.0.0.1:$CdpPort"
        SIMBA_USE_HARDCODED_PLAN = $Hardcoded
    } | Out-Null
    Wait-For "http://127.0.0.1:$BackendPort/" "the backend" 45
}

# Refuse to start on top of another run. Without this the second launcher
# attaches to the first one's host and backend without saying so, and its
# cleanup then kills processes it did not start.
foreach ($port in @($BackendPort, $CdpPort, "5000", "5100")) {
    if (Get-PortOwners $port) {
        Die "port $port is already in use - another SIMBA run is probably up. Stop that one first."
    }
}

try {
    switch ($Flow) {
        "registration" {
            Start-Replica "registration" "5000"
            Start-Host "http://127.0.0.1:5000"
            Start-Backend "registration"
        }
        "billing" {
            Start-Replica "billing" "5100"
            Start-Host "http://127.0.0.1:5100"
            Start-Backend "billing"
        }
        "railways" {
            Warn "railways is a live public website. Read-only, and please do not"
            Warn "hammer it - a handful of runs, not a benchmark."
            Start-Host "https://www.pakrailways.gov.pk/train"
            Start-Backend "railways"
        }
        "mock" {
            # No replica and no real backend: the scripted one plays the
            # backend's whole side of the conversation, including a mid-task
            # level change, so the fold between detail levels can be watched
            # without a site at all.
            Say "starting the mock backend on :$BackendPort (scripted, no browser driving)"
            [void]$Ports.Add($BackendPort)
            Start-Tracked $Py @("-m", "uvicorn", "tools.mock_backend:app", "--port", $BackendPort) | Out-Null
            Wait-For "http://127.0.0.1:$BackendPort/" "the mock backend" 30
            Start-Host "about:blank"
        }
    }

    Write-Host ""
    Say "ready - type a goal in the SIMBA window and press Start"
    if ($Flow -eq "mock") {
        Say "the level changes itself before step 3 and back before step 4: watch the fold"
    }
    Say "Ctrl+Shift+D in the window shows the message log"
    Say "Ctrl+C here stops everything"
    Write-Host ""

    if ($Seconds -gt 0) {
        Say "-Seconds $Seconds, shutting down after that"
        Start-Sleep -Seconds $Seconds
    } else {
        while ($true) { Start-Sleep -Seconds 1 }
    }
} finally {
    Stop-Everything
}
