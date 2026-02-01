$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootDir

if (-not $env:MIMIR_API_BASE) { $env:MIMIR_API_BASE = "http://127.0.0.1:5000" }
if (-not $env:MIMIR_MDNS_TYPE) { $env:MIMIR_MDNS_TYPE = "mimir-display" }
if (-not $env:MIMIR_MDNS_PROTOCOL) { $env:MIMIR_MDNS_PROTOCOL = "tcp" }
if (-not $env:MIMIR_BROWSE_UPDATE_MS) { $env:MIMIR_BROWSE_UPDATE_MS = "30000" }
if (-not $env:MIMIR_BATCH_MS) { $env:MIMIR_BATCH_MS = "1000" }
if (-not $env:MIMIR_STATS_MS) { $env:MIMIR_STATS_MS = "10000" }
if (-not $env:LOG_LEVEL) { $env:LOG_LEVEL = "info" }

Write-Host "[discovery-dotnet] Starting with:"
Write-Host "  MIMIR_API_BASE=$env:MIMIR_API_BASE"
Write-Host "  MIMIR_MDNS_TYPE=$env:MIMIR_MDNS_TYPE"
Write-Host "  MIMIR_MDNS_PROTOCOL=$env:MIMIR_MDNS_PROTOCOL"
Write-Host "  MIMIR_BROWSE_UPDATE_MS=$env:MIMIR_BROWSE_UPDATE_MS"
Write-Host "  MIMIR_BATCH_MS=$env:MIMIR_BATCH_MS"
Write-Host "  MIMIR_STATS_MS=$env:MIMIR_STATS_MS"
Write-Host "  LOG_LEVEL=$env:LOG_LEVEL"
if ($env:MIMIR_MDNS_INTERFACE) { Write-Host "  MIMIR_MDNS_INTERFACE=$env:MIMIR_MDNS_INTERFACE" }
if ($env:MIMIR_MDNS_PORT) { Write-Host "  MIMIR_MDNS_PORT=$env:MIMIR_MDNS_PORT" }
if ($env:MIMIR_DISCOVERY_TOKEN) { Write-Host "  MIMIR_DISCOVERY_TOKEN=***" }

Write-Host "[discovery-dotnet] Running... (Ctrl+C to stop)"

dotnet run --project "$RootDir\Mimir.Discovery.csproj"
