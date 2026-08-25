$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$launcher = Join-Path $projectRoot 'scripts\ensure-start-server.ps1'

if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) {
  Write-Error "Launcher not found: $launcher"
  return
}

Write-Host "Starting K-town with conda environment python_class..." -ForegroundColor Green

try {
  & $launcher -Port 8090 -Foreground
  if (-not $?) {
    Write-Error "K-town server stopped with an error."
  }
} catch {
  Write-Error $_
}
