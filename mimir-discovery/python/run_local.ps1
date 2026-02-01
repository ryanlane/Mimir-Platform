Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

if (-not (Test-Path .venv)) {
  python -m venv .venv
}

.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

# Example:
#   $env:MIMIR_API_BASE = 'http://127.0.0.1:5000'
#   $env:MIMIR_DISCOVERY_TOKEN = '...'
#   .\run_local.ps1

python -m mimir_discovery
