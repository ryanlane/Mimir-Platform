$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootDir

# Defaults (override via environment)
if (-not $env:MIMIR_API_BASE) { $env:MIMIR_API_BASE = "http://127.0.0.1:5000" }
if (-not $env:MIMIR_MDNS_TYPE) { $env:MIMIR_MDNS_TYPE = "mimir-display" }
if (-not $env:MIMIR_MDNS_PROTOCOL) { $env:MIMIR_MDNS_PROTOCOL = "tcp" }
if (-not $env:MIMIR_BROWSE_UPDATE_MS) { $env:MIMIR_BROWSE_UPDATE_MS = "30000" }
if (-not $env:MIMIR_BATCH_MS) { $env:MIMIR_BATCH_MS = "1000" }
if (-not $env:MIMIR_STATS_MS) { $env:MIMIR_STATS_MS = "10000" }

# Best-effort auto-select LAN interface IP if none provided
if (-not $env:MIMIR_MDNS_INTERFACE) {
  try {
    $route = Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction Stop | Sort-Object -Property RouteMetric | Select-Object -First 1
    if ($route) {
      $iface = Get-NetIPAddress -InterfaceIndex $route.InterfaceIndex -AddressFamily IPv4 -ErrorAction Stop | Where-Object { $_.IPAddress -notlike "169.254.*" } | Select-Object -First 1
      if ($iface -and $iface.IPAddress) {
        $env:MIMIR_MDNS_INTERFACE = $iface.IPAddress
      }
    }
  } catch {
    # ignore and continue
  }
}

if (-not (Test-Path -Path "node_modules")) {
  Write-Host "[discovery-node] Installing dependencies..."
  npm install
}

Write-Host "[discovery-node] Starting with:"
Write-Host "  MIMIR_API_BASE=$env:MIMIR_API_BASE"
Write-Host "  MIMIR_MDNS_TYPE=$env:MIMIR_MDNS_TYPE"
Write-Host "  MIMIR_MDNS_PROTOCOL=$env:MIMIR_MDNS_PROTOCOL"
Write-Host "  MIMIR_BROWSE_UPDATE_MS=$env:MIMIR_BROWSE_UPDATE_MS"
Write-Host "  MIMIR_BATCH_MS=$env:MIMIR_BATCH_MS"
Write-Host "  MIMIR_STATS_MS=$env:MIMIR_STATS_MS"
if ($env:MIMIR_MDNS_INTERFACE) { Write-Host "  MIMIR_MDNS_INTERFACE=$env:MIMIR_MDNS_INTERFACE" }
if ($env:MIMIR_DISCOVERY_TOKEN) { Write-Host "  MIMIR_DISCOVERY_TOKEN=***" }

Write-Host "[discovery-node] Running... (Ctrl+C to stop)"

npm start
