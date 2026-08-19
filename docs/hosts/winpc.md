# Windows 11 (nex-pc dual-boot)

**Date:** 2026-08-07
**Hostname:** DESKTOP-BO661M2
**IP address:** 192.168.0.100 (Ethernet, same lease as Nobara - see below)
**Tailscale IP:** 100.80.75.55 (`nex-windows`)
**User:** Nex
**SSH access from LXC 109:** `ssh winpc`

---

## Overview

| Property | Value |
|----------|-------|
| OS | Windows 11 Pro (build 26100) |
| Hardware | shared with [Nobara](nobara.md) - Ryzen 7 3700X, RTX 2060 SUPER, 32 GB |
| System disk | `nvme1n1p2` (465 GB NTFS), mounted as `/mnt/nvme` when Nobara is running |
| SSH | in-box OpenSSH 9.5p1 (client + server) |
| Shell | PowerShell 7.4.6, Windows Terminal |
| Remote access | Tailscale node `nex-windows` |

This is the **same physical machine as the Nobara PC**, dual-booting from a second NVMe. It takes the same DHCP lease, so `192.168.0.100` is Nobara or Windows depending on what is booted - never both. The boot layout and its repair history are documented in [Nobara PC → Dual-boot with Windows 11](nobara.md#dual-boot-with-windows-11).

The SSH config on LXC 109 therefore has two aliases pointing at one address:

```
Host nobara      # expect Linux
Host winpc       # expect Windows
```

Both machines' host keys live side by side in `known_hosts`, so switching between them does not trigger the `REMOTE HOST IDENTIFICATION HAS CHANGED` warning. OpenSSH accepts any key that matches one of the recorded entries for a host.

---

## OpenSSH server

Windows has shipped OpenSSH since Windows 10 1809. No PuTTY, no third-party client: the `config` file format is identical to Linux, so a config is portable between the two sides of the dual-boot.

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Set-Service ssh-agent -StartupType Automatic ; Start-Service ssh-agent
Set-Service sshd      -StartupType Automatic ; Start-Service sshd
```

The `~~~~0.0.1.0` suffix is **not** a version number. Windows capability names follow `Name~Publisher~Architecture~Language~Version`, and optional features always carry the placeholder `0.0.1.0`. The actual OpenSSH version is whatever the Windows build ships (9.5p1 here) and is serviced through Windows Update.

### Five traps, each of which fails silently or misleadingly

**1. `ssh-agent` ships Disabled.** `Start-Service ssh-agent` fails with a generic "cannot start service" until the startup type is changed. Set `-StartupType Automatic` first.

**2. The firewall rule is Private-profile only, and a fresh install classifies the LAN as Public.** The capability creates `OpenSSH-Server-In-TCP` enabled and allowing, so everything *looks* correct, while connections **time out** rather than being refused - the signature of a dropped packet, not a missing listener.

```powershell
Get-NetConnectionProfile | Format-Table Name, InterfaceAlias, NetworkCategory
Set-NetConnectionProfile -InterfaceAlias "Ethernet" -NetworkCategory Private
```

A home LAN should be Private anyway. The alternative, `Set-NetFirewallRule -Name OpenSSH-Server-In-TCP -Profile Any`, punches the rule into the Public profile instead and is the worse choice.

**3. For members of the Administrators group, sshd ignores `~/.ssh/authorized_keys`.** It reads `C:\ProgramData\ssh\administrators_authorized_keys`, and only if the ACL grants nobody beyond Administrators and SYSTEM. Wrong permissions are ignored without a word in the client output.

```powershell
Add-Content -Path C:\ProgramData\ssh\administrators_authorized_keys -Value 'ssh-ed25519 AAAA...your_public_key_here comment'
icacls C:\ProgramData\ssh\administrators_authorized_keys /inheritance:r /grant "Administrators:F" /grant "SYSTEM:F"
```

**4. The default remote shell is `cmd.exe`.** Any command containing `;` or `$` arrives mangled. Point `DefaultShell` at PowerShell 7; it applies to new connections with no service restart.

```powershell
New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShell `
  -Value "C:\Program Files\PowerShell\7\pwsh.exe" -PropertyType String -Force
```

**5. The SSH session is not elevated.** `Add-WindowsCapability`, `Set-NetConnectionProfile` and similar admin work must be run from an interactive elevated window, even when the SSH user is an administrator. This is a useful property rather than a limitation: remote automation cannot silently change machine-wide state.

### Verifying the host key

The dual-boot means the same IP answers with a different host key depending on the OS, which is exactly what a man-in-the-middle looks like. Compare before trusting - scan from the client, print from the server:

```bash
ssh-keyscan -t ed25519,rsa 192.168.0.100 | ssh-keygen -lf -        # on the client
```

```powershell
Get-ChildItem C:\ProgramData\ssh\ssh_host_*_key.pub | ForEach-Object {
  & "$env:SystemRoot\System32\OpenSSH\ssh-keygen.exe" -l -f $_.FullName
}
```

---

## OpenSSH client

The **Server** capability does not add `C:\Windows\System32\OpenSSH` to `PATH` - only the **Client** capability does, and shells opened before the install keep the stale `PATH`. This produces a confusing sequence where `ssh-keygen` works in one window and not in another. Full paths always work; a new window picks up the change.

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0    # elevated
ssh-keygen -t ed25519 -C "nex-pc-windows"                        # normal window
ssh-add $env:USERPROFILE\.ssh\id_ed25519
```

**Use a passphrase.** The Windows `ssh-agent` stores loaded keys in the user's credential store and reloads them after a reboot, so a passphrase is entered once on the machine and never again. An empty passphrase buys nothing here.

An empty agent is the single most misleading failure mode: with a passphrase-protected key and nothing loaded, every host answers `Permission denied (publickey)` - identical to a key that was never installed. Check `ssh-add -l` before debugging the server side.

### Config

`C:\Users\<user>\.ssh\config`, same syntax as Linux. A file written into `~/.ssh` by a remote process inherits ACLs the client rejects with `Bad owner or permissions`; reset with:

```powershell
icacls "$env:USERPROFILE\.ssh\config" /inheritance:r /grant:r "${env:USERNAME}:F"
```

```
Host *
    IdentityFile C:\Users\<user>\.ssh\id_ed25519
    ServerAliveInterval 30
    ServerAliveCountMax 4

Host proxmox
    HostName 192.168.0.109
    User root
# ... one block per host
```

The `ServerAlive*` pair is deliberate: this machine reaches the LAN over the RE605X wireless backhaul, where idle sessions have been observed to stall.

### Reachable hosts

The public key is in `~/.ssh/authorized_keys` on: claude-mgmt, proxmox, docker-host, adguard, komodo, karakeep, n8n, scraper, agentos, plus the Hetzner VPS and Home Assistant (both special, below).

---

## Home Assistant is special, twice over

**Cipher negotiation fails.** The Advanced SSH & Web Terminal addon runs OpenSSH 10.3p1 against the Windows client's 9.5p1. They agree on `umac-128-etm@openssh.com` and the connection dies mid-handshake:

```
ssh_dispatch_run_fatal: Connection to 192.168.0.202 port 22: message authentication code incorrect
```

The same client reaches every other host fine, and the same server accepts every other client fine, which makes this look like a network fault rather than an algorithm mismatch. Pinning a MAC both implementations agree on fixes it:

```
Host haos
    HostName 192.168.0.202
    User hassio
    MACs hmac-sha2-256-etm@openssh.com,hmac-sha2-512-etm@openssh.com
```

**Keys do not go in `authorized_keys`.** The addon's sshd honours `/etc/ssh/authorized_keys`, not `~/.ssh/authorized_keys`, and `/etc/s6-overlay/s6-rc.d/init-ssh/run` rebuilds that file from the addon's own options on every start:

```bash
if bashio::config.has_value 'ssh.authorized_keys'; then
    while read -r key; do
        echo "${key}" >> "${SSH_AUTHORIZED_KEYS_PATH}"
    done <<< "$(bashio::config 'ssh.authorized_keys')"
fi
```

Editing the file directly therefore survives only until the next addon restart. Add keys in **Settings → Add-ons → Advanced SSH & Web Terminal → Configuration**. The option is nested under `ssh:` and the form hides unused optional options, so use the three-dot menu → **Edit in YAML**:

```yaml
ssh:
  username: hassio
  authorized_keys:
    - ssh-ed25519 AAAA...key_one_here comment
    - ssh-ed25519 AAAA...key_two_here comment
```

Saving restarts the addon by itself.

---

## Hetzner VPS

The VPS is the only host reachable from the public internet. Its posture was already `PasswordAuthentication no`, `PermitRootLogin without-password`, fail2ban active, and ufw rate-limiting (`LIMIT`) port 22.

Two options were weighed for adding this workstation's key:

| | |
|---|---|
| Unrestricted | matches the existing keys; works from any network, including without Tailscale |
| `from="100.64.0.0/10"` prefix | key is only accepted from tailnet source addresses, so a leaked private key is useless from the open internet - at the cost of depending on Tailscale being up |

**Unrestricted was chosen**, consistent with the keys already present. The restriction remains a one-word change to the `authorized_keys` line if that trade is ever revisited. Worth noting that this key is passphrase-protected, unlike the non-interactive automation key that predates it.

---

## DNS

A fresh Windows install carried static DNS servers (Quad9), so no `*.lan` name resolved while every IP-based connection worked. Point it at AdGuard instead:

```powershell
Set-DnsClientServerAddress -InterfaceAlias "Ethernet" -ServerAddresses 192.168.0.111
Clear-DnsClientCache
```

`Set-DnsClientServerAddress -InterfaceAlias "Ethernet" -ResetServerAddresses` hands control back to DHCP.

`.lan` names resolve to the Caddy reverse proxy and are served over HTTPS with a mkcert CA - see the next section for making that CA trusted. Until it is, browsers warn; direct `IP:port` access sidesteps it (Home Assistant, for example, at `192.168.0.202:8123`).

---

## HTTPS for .lan services

Every `.lan` name resolves to Caddy (192.168.0.208), which serves a certificate signed by the mkcert CA that lives on LXC 110. Nothing outside the LAN issued it, so a fresh Windows install does not trust it and the browser says so.

### Read the error before doing anything

The three failures look similar in the address bar and have nothing to do with each other:

| What the browser shows | Firefox code | Cause | Fix |
|---|---|---|---|
| Warning page, "Potential Security Risk Ahead" | `SEC_ERROR_UNKNOWN_ISSUER` | The mkcert CA is not trusted on this machine | Install the CA, below |
| Warning page, "does not apply to the name" | `SSL_ERROR_BAD_CERT_DOMAIN` | The domain is not in the cert's SAN list | Regenerate the cert on LXC 110 with the domain added ([caddy → Regenerating the cert](caddy.md#regenerating-the-cert)) |
| No warning page, "Not secure" beside the URL | - | The address is `http://`, not `https://` | Type the `https://` scheme, or fix the bookmark |

The last one is easy to mistake for a certificate problem. Caddy deliberately serves the same handlers on port 80 for devices that cannot hold the CA, so `http://jellyfin.lan` works and is honestly labelled insecure.

### Two trust stores, not one

Windows keeps one store; **Firefox keeps its own (NSS) and consults the Windows store only when `security.enterprise_roots.enabled` is set**. `mkcert -install` cannot bridge that gap here - mkcert supports the Firefox store on macOS and Linux only. So Edge and Chrome can be working perfectly while Firefox still refuses, which is exactly what it looks like when the CA install "did not take".

### The script

`scripts/install-lan-ca-windows.ps1` in this repo does all of it. Elevated PowerShell, Firefox closed:

```powershell
.\install-lan-ca-windows.ps1 -Fetch
```

`-Fetch` pulls `rootCA.pem` off the Caddy LXC over the existing SSH access. Without it, pass `-CertPath` to a copy already on disk. The script:

1. imports the CA into `LocalMachine\Root` - covers Edge, Chrome, `curl.exe` and .NET
2. copies the CA into `%LOCALAPPDATA%\Mozilla\Certificates` and merges a `distribution\policies.json` next to `firefox.exe` setting `Certificates.Install` plus `Certificates.ImportEnterpriseRoots` - covers Firefox
3. warns if DNS is not pointing at AdGuard (192.168.0.111), then flushes the resolver cache
4. fetches `https://homepage.lan` and reports whether the chain validated

It is idempotent and backs up an existing `policies.json` to `policies.json.bak`.

### Doing it by hand

```powershell
# 1. get the CA
ssh root@192.168.0.109 "pct pull 110 /etc/caddy/certs/rootCA.pem /tmp/rootCA.pem"
scp root@192.168.0.109:/tmp/rootCA.pem $env:USERPROFILE\Downloads\mkcert-rootCA.pem

# 2. Windows store (elevated) - Chrome, Edge, curl.exe
Import-Certificate -FilePath $env:USERPROFILE\Downloads\mkcert-rootCA.pem `
  -CertStoreLocation Cert:\LocalMachine\Root

# 3. verify it landed
Get-ChildItem Cert:\LocalMachine\Root | Where-Object Subject -like '*mkcert*'
```

For Firefox, either flip **Settings → Privacy & Security → Certificates → "Allow Firefox to automatically trust third-party root certificates you install"** (this is `security.enterprise_roots.enabled`, so step 2 then suffices), or import the file directly: **View Certificates → Authorities → Import → mkcert-rootCA.pem → tick "Trust this CA to identify websites"**. Either way Firefox reads the change at startup only, so restart it fully - closing the window is not enough if it is still in the tray.

### Verifying

```powershell
Resolve-DnsName homepage.lan          # must answer 192.168.0.208
curl.exe -sI https://homepage.lan     # Schannel, so this proves the Windows store
Invoke-WebRequest https://homepage.lan -UseBasicParsing | Select-Object StatusCode
```

`curl.exe` succeeding while Firefox still warns is the normal intermediate state, and means only the Firefox half is outstanding.

### Expiry

The current server cert runs to **2028-10-19**. New `.lan` domains added after that cert was issued produce `SSL_ERROR_BAD_CERT_DOMAIN` on every device until the cert is regenerated - the CA in the Windows store does not need touching for that, only the server cert on LXC 110.

---

## Terminal

Windows Terminal was not present on this install and is worth adding - not as a PowerShell replacement but as the window PowerShell runs in, the same relation as Konsole to bash. It brings tabs and split panes, true colour and correct UTF-8 box-drawing (so `htop` and `ncdu` over SSH are legible instead of shredded), GPU-accelerated scrolling, and searchable scrollback.

```powershell
winget install --id Microsoft.WindowsTerminal
```

---

## Tailscale

Windows is its own tailnet node, `nex-windows` (100.80.75.55), separate from Nobara's `nex-pc` (100.109.197.79). Because the two operating systems can never run at once, this pair cannot produce the UDP 41641 port collision that has bitten other nodes behind this router.

```powershell
winget install --id tailscale.tailscale
```

---

## Seelen UI

!!! warning "Removed on 2026-08-19"

    Seelen UI is no longer installed on this machine. This section is kept as a record of the diagnosis and of why it was dropped; see [Why it was removed](#why-it-was-removed) at the end. Everything below describes how it *was* set up.

[Seelen UI](https://github.com/eythaann/Seelen-UI) 2.8.2 replaced the Windows shell on this machine: its own taskbar, dock, app menu and tiling window manager. It came from the Microsoft Store as `Seelen.SeelenUI_p6yyn03m1894e`, so it also updated itself from there.

Every widget it draws is a **separate WebView2 instance**. That is the architecture, and it is also the source of the only real trouble this machine has had with it.

### The widget that stopped responding

On 2026-08-19 the shell came apart a piece at a time. Clicking the tray, the settings, the quick settings or a context menu produced:

> The widget 'XY' stopped responding too many times. You can try restarting the app.

The taskbar and the dock kept working, which made it read as a random partial failure. The log said otherwise:

```
[2026-08-19][07:28:19][ERROR][tauri_runtime_wry] failed to create webview: WebView2 error:
  WindowsError(Error { code: HRESULT(0x80010108), message: "The object invoked has disconnected from its clients." })
[2026-08-19][07:29:24][ERROR][seelen_ui::widgets::loader] Liveness prove failed for @seelen/system-tray too many times, giving up.
```

`0x80010108` is `RPC_E_DISCONNECTED`. Lining those timestamps up against the WebView2 install directory explains all of it:

| Time | Event |
|---|---|
| 07:13:09 | `seelen-ui.exe` starts, spawning WebView2 processes from `151.0.4129.78` |
| 07:14:30 | Edge Update creates `...\EdgeWebView\Application\151.0.4129.93` |
| 07:24:47 | the installer finishes and the old version's directory goes away |
| 07:28:03 | first `Liveness prove failed`; nine widgets give up over the next ninety seconds |

**The Evergreen WebView2 runtime updated underneath a process that was already running.** Widgets that already held a webview carried on, which is why the taskbar looked healthy. Anything that had to create a *new* one was asking for a runtime that no longer existed on disk. Nine gave up: `tooltip`, `context-menu` (two instances), `user-menu`, `settings`, `notifications`, `quick-settings`, `keyboard-selector`, `system-tray`.

A process in this state never recovers on its own. Only a restart fixes it, and the same thing will happen at the next runtime update - this is design, not a bug that gets patched.

### Diagnosing it without reading the log

Compare the registered runtime version against what Seelen's children are actually running:

```powershell
(Get-ItemProperty 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}').pv
Get-CimInstance Win32_Process -Filter "Name='msedgewebview2.exe' AND ParentProcessId=$((Get-Process seelen-ui).Id)" |
  Select-Object ProcessId, ExecutablePath
```

Two things about that second command. The GUID is the **WebView2 Runtime**'s, not the Edge browser's. And it returns exactly **one** row, not the eleven `msedgewebview2.exe` processes visible in Task Manager: only the browser process is a direct child of `seelen-ui.exe`, the renderers are children of *it*. If that one path does not carry the version from the first command, the shell is already broken and has no way to tell you.

### The fix that was rejected

There is a one-line way to stop this permanently:

```powershell
reg add "HKLM\SOFTWARE\Policies\Microsoft\EdgeUpdate" /v "Update{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" /t REG_DWORD /d 0 /f
```

It works, and it was **not** used. WebView2 is not Seelen's private dependency: the new Outlook, Teams and a long tail of Store apps render web content with the same runtime, some of it from the open internet. Freezing the runtime freezes their engine's security patches too. That is a bad trade on a machine in daily use, to spare a three-second restart every few weeks.

### The guard

`scripts/seelen-webview-guard.ps1` in this repo, deployed to `C:\Users\Nex\seelen-webview-guard.ps1` and driven by a scheduled task named `Seelen WebView2 guard`. It watches the exact condition that breaks the shell - Seelen's own webview child running from a directory other than the registered runtime - and restarts Seelen when it sees it. Nothing is grepped, nothing is guessed.

The task does not call PowerShell directly. It runs `scripts/seelen-webview-guard.vbs`, a small launcher whose only job is to start PowerShell with no window; the reason is the third trap below.

```powershell
$me = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

$action = New-ScheduledTaskAction -Execute 'wscript.exe' `
  -Argument '"C:\Users\Nex\seelen-webview-guard.vbs"'
$t1 = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 5)
$t2 = New-ScheduledTaskTrigger -AtLogOn -User $me

Register-ScheduledTask -TaskName 'Seelen WebView2 guard' -Action $action -Trigger @($t1,$t2) `
  -Principal (New-ScheduledTaskPrincipal -UserId $me -LogonType Interactive -RunLevel Limited) `
  -Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
              -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -MultipleInstances IgnoreNew)
```

Three traps:

**`$env:USERDOMAIN` is `WORKGROUP` on a machine that is not domain-joined**, and `Register-ScheduledTask` rejects `WORKGROUP\nex` with `No mapping between account names and security IDs was done` - an error that reads like a permissions problem rather than a bad string. `[System.Security.Principal.WindowsIdentity]::GetCurrent().Name` returns `DESKTOP-BO661M2\Nex`, which it accepts.

**`-LogonType Interactive` is not optional.** Relaunching an MSIX app means `Start-Process explorer.exe 'shell:AppsFolder\<PackageFamilyName>!App'`, and that needs a desktop session to appear on. A task running as SYSTEM or with a stored password would kill Seelen and never bring it back - the worst possible outcome for a script whose job is keeping the shell alive. `-RunLevel Limited` is deliberate too: none of this needs administrator.

**`powershell.exe -WindowStyle Hidden` still flashes a console window.** The console host is created before PowerShell parses its own parameters, so the window exists for a few hundred milliseconds no matter what the flag says. On a five-minute schedule that is a blink on the desktop twelve times an hour, and it can take focus off whatever is in front of it - which is how this was noticed at all, from the desk rather than from a log. `wscript.exe` has no console of its own, so a `.vbs` doing `CreateObject("WScript.Shell").Run cmd, 0, True` starts PowerShell hidden and waits for it, keeping the task's runtime and its execution time limit meaningful.

The `-AtLogOn` trigger exists because the repeating trigger alone is not dependable across a reboot. `IgnoreNew` keeps a slow run from stacking, and the script writes a `seelen-webview-guard.last` stamp so a mismatch that somehow refuses to clear cannot turn into a restart every five minutes.

### Verifying it

The first run was a real one - the shell was still broken at the time, so the guard had actual work to do:

```
task last run     : 08/19/2026 07:46:35  result=0
seelen pid        : 9428 -> 8064  (started 07:46:38)
webview child     : 6192  ...\EdgeWebView\Application\151.0.4129.93\msedgewebview2.exe
```

`%LOCALAPPDATA%\seelen-webview-guard.log`:

```
2026-08-19T07:46:37 restart: bejegyzett runtime=151.0.4129.93, futo=...\151.0.4129.78\msedgewebview2.exe
2026-08-19T07:46:40 ujrainditva
```

Then it was run a second time, which is the half that actually matters: **pid 8064 stayed 8064** and the log stayed two lines. A guard that restarts things is only safe once you have watched it decline to.

Moving the task onto the `.vbs` launcher needed one more proof, because **`wscript.exe` returns 0 whether or not the script it launched did anything**. A task result of `0` says nothing about the PowerShell underneath. So the guard was swapped for a one-line stand-in that writes a file unconditionally, the task was fired, and the stand-in reported back:

```
ran at 2026-08-19T10:13:31 as desktop-bo661m2\nex session 1
```

`session 1` is the interactive desktop session, which is the property the MSIX relaunch depends on. The real script was then restored and its SHA256 compared against the copy in this repo to prove the swap left nothing behind.

### Three log lines that are not evidence

Every Seelen start writes these, including the 2026-08-11 start that predates all of the above:

```
[ERROR][seelen_ui::error] WMI(HResultError { hres: -2147217396 })
[ERROR][seelen_ui::error] Windows(Error { code: HRESULT(0x80040154), message: "Class not registered" })
```

And `telemetry.seelen.io` fails DNS resolution on every run, because AdGuard blocks it. Neither has anything to do with the widget failure, and both are easy to seize on when hunting for a cause.

### What it costs, and why it stays

Measured on 2026-08-19 with the shell idle:

| | |
|---|---|
| `seelen-ui.exe` | 152 MB |
| `msedgewebview2.exe` x11 | 926 MB |
| `slu-service.exe` | 4 MB |
| **total** | **1 082 MB** |

Plus 82 CPU-seconds over 26.3 minutes of uptime, or roughly **5.2% of one core, sustained, doing nothing** - a good part of it the per-second window preview capture that the log shows on every single second.

That is a lot for a shell, and it stays anyway. This machine is the games half of the dual boot; the daily desktop is [Nobara](nobara.md). 1 GB out of 32 GB and 5% of one core buy a desktop that is pleasant to be in for the few hours a week it runs, and the failure that prompted all of this is now handled in fifteen lines of PowerShell.

If that ever changes - if real work happens on the Windows side - the durable replacement is **komorebi plus YASB**: a tiling window manager and a status bar with no browser engine anywhere in the loop, so no runtime update can reach them. The cost is TOML and JSON configuration and `whkd` for the key bindings, with no settings GUI at all. [GlazeWM](https://github.com/glzr-io/glazewm) is the obvious third option and is not recommended here: as of 2026-08-19 it carries 400 open issues with no commit since 2026-06-20, and Zebar, its companion bar, has not been touched since 2026-03-31.

### Why it was removed

The guard worked. It was also, within four hours, clearly fixing one instance of a class of problem rather than the problem.

At 11:05:15 the same day, `@seelen/wallpaper-manager` began failing, and the shell showed the same "stopped responding too many times" dialog. This time it was **not** the WebView2 update:

| | Morning failure | Midday failure |
|---|---|---|
| HRESULT | `0x80010108` `RPC_E_DISCONNECTED` | `0x8007139F` `ERROR_INVALID_STATE` |
| Registered runtime vs. Seelen's child | `.93` vs `.78` - mismatch | `.93` vs `.93` - identical |
| Widgets lost | nine | one |
| Guard's verdict | restart | do nothing |

The guard's verdict was **correct** both times. There was no runtime mismatch at 11:05, so restarting Seelen was not its call to make. The trigger was mundane: a window closed (`Removing: Window(0xb0788)`), and the wallpaper manager's webview never came back. Six liveness attempts over forty seconds, then `giving up`.

What settled it was what happened next. The automatic wallpaper rotation kept firing on its five-minute timer against a widget that no longer existed, and the log went from 785 KB to 937 KB in twenty seconds - **7 602 bytes per second**, 2 173 copies of the same error, with no upper bound and no self-recovery. CPU stayed low (1.7% of one core), so nothing was on fire; it was simply going to grind on until someone restarted the shell by hand.

That is the argument against the whole arrangement. `0x8007139F` is a known WebView2 failure with [several distinct causes reported upstream](https://github.com/MicrosoftEdge/WebView2Feedback/issues/4216), and Tauri has [its own long-running issue for it](https://github.com/tauri-apps/tauri/issues/8640). Guarding against each new symptom means writing a new detector every time, and the only detector that would have caught this one is log-grepping for `giving up` - which cannot distinguish a widget that failed once from a widget that fails on every start, so it risks a restart loop on the desktop it is supposed to protect.

Weighed against 1 GB of RAM and 5% of a core for a shell on a machine that exists to run games, that was not a trade worth defending. Windows 11's own shell went back on.

### What removing it touched

```powershell
Unregister-ScheduledTask -TaskName 'Seelen WebView2 guard' -Confirm:$false
Get-Process seelen-ui, slu-service | Stop-Process -Force
Get-AppxPackage Seelen.SeelenUI | Remove-AppxPackage
Unregister-ScheduledTask -TaskName 'Seelen UI Service' -TaskPath '\Seelen\' -Confirm:$false
Remove-Item "$env:APPDATA\com.seelen.seelen-ui", "$env:LOCALAPPDATA\com.seelen.seelen-ui" -Recurse -Force
Stop-Process -Name explorer -Force        # rebuilds the native taskbar
```

Two things are worth knowing before doing this on a machine you are sitting at.

**`slu-service.exe` is what hides the native taskbar**, through `HideNativeTaskbar` IPC calls. Removing the package while it is hidden can leave a desktop with no taskbar at all, so the order matters: stop the processes first, uninstall second, and restart `explorer.exe` at the end to rebuild `Shell_TrayWnd` from scratch. If that is ever missed, **Ctrl+Shift+Esc → Run new task → `explorer.exe`** is the way back.

**A second scheduled task survives the uninstall.** `\Seelen\Seelen UI Service` is registered outside the MSIX package and `Remove-AppxPackage` leaves it behind, along with its `\Seelen\` folder in the Task Scheduler tree.

Removed: the 2.8.2.0 package, a 38.1 MB local data directory, 3 KB of settings, two scheduled tasks and four guard files. `explorer.exe` restarted cleanly (pid 9712 to 10656).

One thing SSH cannot answer: whether the taskbar is actually on screen. `FindWindow('Shell_TrayWnd', ...)` from an SSH session returns a null handle **regardless**, because that session cannot see the interactive desktop's windows - the same trap as reading monitor geometry remotely, where `[System.Windows.Forms.Screen]::AllScreens` reports a phantom 1024x768. Neither is evidence of anything. Only a human looking at the screen can confirm it.
