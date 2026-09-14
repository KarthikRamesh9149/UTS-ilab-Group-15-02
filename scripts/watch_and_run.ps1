<#
Wait for the CETUS vLLM job to come up, then run the frozen 21 tasks unattended.

Why this exists: the serve job's walltime starts when PBS schedules it, not when
someone sits down at the laptop. If a GPU frees at 3am, an idle server burns hours
of a 12-hour window. This watches for the endpoint and starts the run immediately.

What it does, in order:
  1. polls CETUS for ~/vllm-endpoint.txt, which serve_vllm.pbs writes when it starts
  2. opens an SSH tunnel from this laptop to the GPU node
  3. waits until the model actually answers through the tunnel
  4. runs the 21 tasks for the custom harness, then for mini-swe-agent

Step 3 is not redundant. The PBS job writes the endpoint file BEFORE launching vLLM,
because it needs to record the node and token first. Loading a 14B AWQ model takes
minutes, so the file exists well before the server can answer. Acting on the file
alone would fail the runner's preflight.

Requirements while this runs: UTS VPN connected, Docker Desktop running, and the
laptop set not to sleep. Sleep is the one thing this script cannot work around:
  powercfg /change standby-timeout-ac 0
  powercfg /change hibernate-timeout-ac 0

Usage:
    powershell -ExecutionPolicy Bypass -File scripts/watch_and_run.ps1
    powershell -ExecutionPolicy Bypass -File scripts/watch_and_run.ps1 -HarnessOnly custom
#>
[CmdletBinding()]
param(
    [int]$PollSeconds = 60,
    [int]$MaxWaitHours = 48,
    [int]$ReadySeconds = 1800,   # model load: 14B AWQ on Turing is slow
    [int]$Attempts = 3,          # the runner is resumable, so retries are cheap
    [ValidateSet("custom", "mini-swe-agent", "both")]
    [string]$HarnessOnly = "both",
    # Reuse an existing jobs/<harness>-21-<stamp> directory so a resume skips
    # already-scored tasks instead of starting a new 21-task folder.
    [string]$RunStamp = ""
)

$ErrorActionPreference = "Continue"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$stamp = if ($RunStamp) { $RunStamp } else { Get-Date -Format "yyyyMMdd_HHmmss" }
$log = Join-Path $repo "results\watch-run-$stamp.log"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null

function Write-Log {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message
    Write-Host $line
    Add-Content -Path $log -Value $line
}

Write-Log "watcher started; logging to $log"
Write-Log "waiting for the CETUS serve job (checking every ${PollSeconds}s, giving up after ${MaxWaitHours}h)"

# ---------------------------------------------------------------- 1. wait for job
$deadline = (Get-Date).AddHours($MaxWaitHours)
$endpoint = $null

while ((Get-Date) -lt $deadline) {
    # BatchMode so a dropped VPN fails fast instead of prompting for a password.
    # The trailing sentinel is how we tell "connected, file absent" from "could not
    # connect": ssh reports the REMOTE command's exit status, so a missing file also
    # gives a non-zero code and would otherwise be misread as a network failure.
    $sshOpts = @(
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=15",
        "-o", "ServerAliveInterval=10",
        "-o", "ServerAliveCountMax=2"
    )
    $raw = ssh @sshOpts cetus `
        "cat ~/vllm-endpoint.txt 2>/dev/null; echo __REACHED__" 2>$null
    $text = ($raw -join "`n")

    if ($text -notmatch "__REACHED__") {
        Write-Log "cannot reach CETUS (VPN down?) - retrying"
    }
    elseif ($text -match "NODE=(\S+)") {
        # The endpoint file is written at job START and left behind after the
        # job dies. Last night's file would send us at a dead node. Only trust
        # it if qstat shows vllm-serve actually Running.
        $jobs = ssh @sshOpts cetus "qstat -u `$USER 2>/dev/null" 2>$null
        $jobsText = $jobs -join "`n"
        if ($jobsText -notmatch "vllm-serve.* R ") {
            Write-Log "stale endpoint file (no Running vllm-serve) - waiting for a new job"
        }
        else {
            $endpoint = @{
                Node   = ([regex]::Match($text, "NODE=(\S+)")).Groups[1].Value
                Port   = ([regex]::Match($text, "PORT=(\S+)")).Groups[1].Value
                Model  = ([regex]::Match($text, "MODEL=(\S+)")).Groups[1].Value
                ApiKey = ([regex]::Match($text, "API_KEY=(\S+)")).Groups[1].Value
            }
            Write-Log "endpoint published: node=$($endpoint.Node) port=$($endpoint.Port) model=$($endpoint.Model)"
            break
        }
    }
    else {
        # Reachable but no endpoint yet. Report queue position so the log shows
        # progress rather than silence.
        $q = ssh @sshOpts cetus "qstat -u `$USER 2>/dev/null | tail -n 1" 2>$null
        Write-Log "connected; job not up yet: $(($q -join ' ').Trim())"
    }
    Start-Sleep -Seconds $PollSeconds
}

if (-not $endpoint) {
    Write-Log "gave up after ${MaxWaitHours}h without an endpoint. Nothing was run."
    exit 1
}

# ---------------------------------------------------------------- 2. tunnel
$port = [int]$endpoint.Port
Write-Log "opening tunnel 127.0.0.1:$port -> $($endpoint.Node):$port"

# ExitOnForwardFailure so a port already in use is an error rather than a tunnel
# that silently forwards nothing.
$tunnel = Start-Process ssh -PassThru -NoNewWindow -ArgumentList @(
    "-N", "-o", "BatchMode=yes", "-o", "ExitOnForwardFailure=yes",
    "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=6",
    "-L", "${port}:$($endpoint.Node):${port}", "cetus"
)
Start-Sleep -Seconds 5
if ($tunnel.HasExited) {
    Write-Log "tunnel failed to start (is port $port already in use?). Aborting."
    exit 1
}
Write-Log "tunnel pid=$($tunnel.Id)"

# ------------------------------------------------- 3. wait for the model to answer
Write-Log "waiting up to ${ReadySeconds}s for the model to finish loading"
$ready = $false
$readyBy = (Get-Date).AddSeconds($ReadySeconds)

while ((Get-Date) -lt $readyBy) {
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:$port/v1/models" `
            -Headers @{ Authorization = "Bearer $($endpoint.ApiKey)" } -TimeoutSec 15
        $served = @($r.data | ForEach-Object { $_.id })
        Write-Log "endpoint is answering; serving: $($served -join ', ')"
        if ($served -notcontains $endpoint.Model) {
            Write-Log "WARNING: expected $($endpoint.Model) but got $($served -join ', ')"
        }
        $ready = $true
        break
    }
    catch {
        Start-Sleep -Seconds 20
    }
}

if (-not $ready) {
    Write-Log "model never became ready. Check: ssh cetus 'tail -50 ~/vllm-server.log'"
    Stop-Process -Id $tunnel.Id -Force -ErrorAction SilentlyContinue
    exit 1
}

# ---------------------------------------------------------------- 4. run the tasks
# Custom harness first: it is the one the project is actually about, so if the
# walltime runs out mid-way it should be the baseline that is missing, not ours.
$harnesses = switch ($HarnessOnly) {
    "both" { @("custom", "mini-swe-agent") }
    default { @($HarnessOnly) }
}

foreach ($harness in $harnesses) {
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        Write-Log "running 21 tasks: harness=$harness (attempt $attempt of $Attempts)"
        $env:PYTHONIOENCODING = "utf-8"
        $env:PYTHONUTF8 = "1"
        python scripts/run_subset_vllm.py `
            --harness $harness `
            --model $endpoint.Model `
            --port $port `
            --api-key $endpoint.ApiKey `
            --run-name "$harness-21-$stamp" 2>&1 | Tee-Object -FilePath $log -Append

        if ($LASTEXITCODE -eq 0) {
            Write-Log "harness=$harness finished"
            break
        }
        # Already-scored tasks are skipped on re-entry, so a retry resumes rather
        # than repeating work. Usually this is a dropped tunnel.
        Write-Log "harness=$harness exited $LASTEXITCODE; retrying (finished tasks are skipped)"
        Start-Sleep -Seconds 30
    }
}

Write-Log "closing tunnel"
Stop-Process -Id $tunnel.Id -Force -ErrorAction SilentlyContinue

Write-Log "done. Results:"
Get-ChildItem (Join-Path $repo "results") -Filter "*-21-$stamp.csv" -ErrorAction SilentlyContinue |
    ForEach-Object { Write-Log "  $($_.Name)" }
Write-Log "full log: $log"
