# Windows Firewall: enabling mDNS discovery (UDP 5353)

This project’s Windows discovery agent (`service/mimir-discovery-node`) uses mDNS/Zeroconf.
On Windows, the most common reasons discovery shows **0 devices** are:

- the agent is bound to the wrong adapter (VPN/Docker/WSL/Hyper-V)
- Windows Firewall is blocking mDNS (UDP 5353)
- your network blocks multicast (guest Wi‑Fi / AP isolation)

## 1) First: bind to the correct interface (most common fix)

In PowerShell, set the agent to your Windows LAN IP (the IP on the same subnet as the displays):

```powershell
$env:MIMIR_MDNS_INTERFACE='192.168.1.28'
$env:LOG_LEVEL='debug'
$env:MIMIR_BROWSE_ALL='true'
npm start
```

If discovery immediately starts working after this, you may not need any firewall changes.

## 2) Verify your Windows network profile is Private

Firewall rules below are typically scoped to the **Private** profile.

- Settings → Network & Internet → (Wi‑Fi/Ethernet) → set Network profile to **Private**.

## 3) Create an inbound firewall rule for UDP 5353

Run PowerShell **as Administrator**.

This allows inbound mDNS packets to reach the machine:

```powershell
New-NetFirewallRule `
  -DisplayName 'Mimir mDNS (UDP 5353 In)' `
  -Direction Inbound `
  -Protocol UDP `
  -LocalPort 5353 `
  -Action Allow `
  -Profile Private
```

Optional (more strict): only allow mDNS multicast source address.
(Some environments will still send from regular host IPs, so this can be *too strict*.)

```powershell
New-NetFirewallRule `
  -DisplayName 'Mimir mDNS (UDP 5353 In, multicast only)' `
  -Direction Inbound `
  -Protocol UDP `
  -LocalPort 5353 `
  -RemoteAddress 224.0.0.251 `
  -Action Allow `
  -Profile Private
```

## 4) (Optional) Add a program-specific rule

If you want to scope the inbound rule to Node, point it at your `node.exe` path.
Common locations:

- `C:\Program Files\nodejs\node.exe`
- `C:\Users\<you>\AppData\Local\Programs\nodejs\node.exe`

Example:

```powershell
New-NetFirewallRule `
  -DisplayName 'Mimir discovery (node.exe UDP 5353 In)' `
  -Direction Inbound `
  -Program 'C:\Program Files\nodejs\node.exe' `
  -Protocol UDP `
  -LocalPort 5353 `
  -Action Allow `
  -Profile Private
```

If you later package the agent as an `.exe`, point `-Program` at that packaged binary instead.

## 5) Outbound rules (usually not needed)

By default, Windows allows outbound traffic. If you have a hardened outbound policy, allow UDP 5353 outbound:

```powershell
New-NetFirewallRule `
  -DisplayName 'Mimir mDNS (UDP 5353 Out)' `
  -Direction Outbound `
  -Protocol UDP `
  -RemotePort 5353 `
  -Action Allow `
  -Profile Private
```

## 6) Check for VPN / AP isolation / “guest Wi‑Fi” issues

Even with firewall rules, some networks block multicast entirely.

Things that commonly break mDNS:

- VPN clients (split tunnel or full tunnel)
- “AP isolation” / “client isolation” enabled on Wi‑Fi
- guest networks
- some managed enterprise WLAN policies

Quick checks:

- try from a wired connection
- temporarily disable VPN
- ensure the displays and the Windows machine are on the same VLAN/subnet

## 7) Removing the rules

List matching rules:

```powershell
Get-NetFirewallRule | Where-Object DisplayName -Like 'Mimir mDNS*'
Get-NetFirewallRule | Where-Object DisplayName -Like 'Mimir discovery*'
```

Remove by display name:

```powershell
Remove-NetFirewallRule -DisplayName 'Mimir mDNS (UDP 5353 In)'
Remove-NetFirewallRule -DisplayName 'Mimir mDNS (UDP 5353 Out)'
Remove-NetFirewallRule -DisplayName 'Mimir discovery (node.exe UDP 5353 In)'
```
