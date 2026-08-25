# Stop the previous K-town instance and start a new one.

param(
  [int]$Port = 8090,
  [string]$PythonExe = 'E:\anaconda\envs\python_class\python.exe',
  [switch]$Foreground
)

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$projectRoot = Split-Path -Parent $scriptDir
$pidPath = Join-Path $scriptDir 'server.pid'

function Get-ListeningProcessIds {
  $processIds = @()

  try {
    $connections = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop)
    $processIds += $connections | ForEach-Object { [int]$_.OwningProcess }
  } catch {
    # Fall back to netstat on systems where the NetTCPIP module is unavailable.
    foreach ($line in @(netstat -ano 2>$null)) {
      if ($line -match "^\s*TCP\s+\S+:$Port\s+\S+\s+LISTENING\s+(\d+)\s*$") {
        $processIds += [int]$Matches[1]
      }
    }
  }

  @($processIds | Where-Object { $_ -gt 0 } | Sort-Object -Unique)
}

function Stop-PreviousServer {
  $targetIds = @(Get-ListeningProcessIds)

  if (Test-Path -LiteralPath $pidPath) {
    $recordedText = (Get-Content -Raw -LiteralPath $pidPath).Trim()
    if ($recordedText -match '^\d+$') {
      $targetIds += [int]$recordedText
    }
  }

  $targetIds = @($targetIds | Where-Object {
      $_ -gt 0 -and $_ -ne 4 -and $_ -ne $PID
    } | Sort-Object -Unique)

  if ($targetIds.Count -eq 0) {
    Write-Output "No previous server found on port $Port."
  } else {
    foreach ($processId in $targetIds) {
      $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
      if ($null -eq $process) {
        continue
      }

      Write-Output "Stopping previous server (PID: $processId, Path: $($process.Path))..."
      Stop-Process -Id $processId -Force -ErrorAction Stop
    }
  }

  if (Test-Path -LiteralPath $pidPath) {
    Remove-Item -LiteralPath $pidPath -Force
  }

  $deadline = (Get-Date).AddSeconds(10)
  do {
    $remainingIds = @(Get-ListeningProcessIds)
    if ($remainingIds.Count -eq 0) {
      Write-Output "Port $Port is free."
      return
    }
    Start-Sleep -Milliseconds 250
  } while ((Get-Date) -lt $deadline)

  $remainingIds = @(Get-ListeningProcessIds)
  if ($remainingIds.Count -gt 0) {
    throw "Port $Port is still occupied by PID(s): $($remainingIds -join ', ')"
  }
}

if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
  throw "python_class interpreter not found: $PythonExe"
}

# Probe the selected interpreter before stopping a working server.
& $PythonExe -c "import sys; print(sys.executable)" *> $null
if ($LASTEXITCODE -ne 0) {
  throw "The selected interpreter could not start: $PythonExe"
}

Stop-PreviousServer

if ($Foreground) {
  Write-Output "Starting foreground server with: $PythonExe"
  Push-Location $projectRoot
  try {
    & $PythonExe -u main.py
  } finally {
    Pop-Location
  }
  return
}

$logDir = Join-Path $projectRoot 'logs'
if (-not (Test-Path -LiteralPath $logDir -PathType Container)) {
  New-Item -ItemType Directory -Path $logDir | Out-Null
}

$logPath = Join-Path $logDir 'server.log'
$errLogPath = Join-Path $logDir 'server.err.log'
$stdinPath = Join-Path $logDir 'server.stdin'
if (-not (Test-Path -LiteralPath $stdinPath -PathType Leaf)) {
  New-Item -ItemType File -Path $stdinPath | Out-Null
}

Write-Output "Starting detached server with: $PythonExe"
$processInfo = Start-Process `
  -FilePath $PythonExe `
  -ArgumentList @('-u', 'main.py') `
  -WorkingDirectory $projectRoot `
  -WindowStyle Hidden `
  -RedirectStandardInput $stdinPath `
  -RedirectStandardOutput $logPath `
  -RedirectStandardError $errLogPath `
  -PassThru

$processInfo.Id | Out-File -LiteralPath $pidPath -Encoding ascii
Write-Output "Started server (PID: $($processInfo.Id)). Log: $logPath"

$healthUri = "http://127.0.0.1:$Port/api/state"
$healthy = $false
$healthDeadline = (Get-Date).AddSeconds(20)
while ((Get-Date) -lt $healthDeadline) {
  Start-Sleep -Milliseconds 500

  try {
    $response = Invoke-WebRequest -Uri $healthUri -UseBasicParsing -TimeoutSec 2
    if ($response.StatusCode -eq 200) {
      $healthy = $true
      break
    }
  } catch {
    # The server may still be importing modules or opening SQLite.
  }
}

if (-not $healthy) {
  Write-Error "Health check failed: $healthUri"
  $failedProcess = Get-Process -Id $processInfo.Id -ErrorAction SilentlyContinue
  if ($failedProcess) {
    Stop-Process -Id $processInfo.Id -Force -ErrorAction SilentlyContinue
  }
  if (Test-Path -LiteralPath $pidPath) {
    Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
  }
  throw "K-town server did not become ready. Check $errLogPath"
}

Write-Output "Health check OK (200): $healthUri"
return
