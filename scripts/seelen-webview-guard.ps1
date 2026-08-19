<#
.SYNOPSIS
    Restarts Seelen UI when the WebView2 Evergreen runtime has been updated
    underneath the running process.

.DESCRIPTION
    Every widget Seelen UI draws is a separate WebView2 instance. When Edge
    Update installs a new Evergreen runtime, the previous version's directory is
    removed, and the already-running shell keeps talking to a runtime that no
    longer exists. From that moment every attempt to create a new webview fails:

      ERROR tauri_runtime_wry: failed to create webview: WebView2 error:
        HRESULT(0x80010108) "The object invoked has disconnected from its clients."
      ERROR seelen_ui::widgets::loader: Liveness prove failed for
        @seelen/system-tray too many times, giving up.

    which surfaces as "The widget 'X' stopped responding too many times". The
    taskbar and dock survive because they already hold a webview; the tray,
    settings, quick settings, notifications and context menus do not. The process
    never recovers on its own - only a restart does.

    This script detects exactly that condition and nothing else: Seelen's own
    msedgewebview2 child running from a directory other than the currently
    registered runtime version. It does not parse logs.

    Deployed to C:\Users\<user>\seelen-webview-guard.ps1 and driven by a
    scheduled task ("Seelen WebView2 guard") every 5 minutes plus at logon. The
    task must use -LogonType Interactive: relaunching an MSIX app needs a desktop
    session to appear on, so a SYSTEM task would kill Seelen and never bring it
    back. It does not need administrator rights.

    The task runs seelen-webview-guard.vbs rather than powershell.exe directly,
    because powershell.exe flashes a console window on every fire even with
    -WindowStyle Hidden.

.NOTES
    Documented in docs/hosts/winpc.md#seelen-ui
#>

$ErrorActionPreference = 'Stop'
$log   = "$env:LOCALAPPDATA\seelen-webview-guard.log"
$stamp = "$env:LOCALAPPDATA\seelen-webview-guard.last"
$aumid = 'shell:AppsFolder\Seelen.SeelenUI_p6yyn03m1894e!App'

function Log($m) { Add-Content -Path $log -Value "$(Get-Date -Format s) $m" }

$s = Get-Process seelen-ui -ErrorAction SilentlyContinue
if (-not $s) { exit }

# Currently registered WebView2 Runtime version. This GUID is the WebView2
# Runtime's, not the Edge browser's.
$key = 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
$pv  = (Get-ItemProperty -Path $key -ErrorAction SilentlyContinue).pv
if (-not $pv) { exit }

# Only Seelen's own children count - another app (Outlook, Teams) holding a
# stale webview is no reason to restart this shell. Exactly one row comes back:
# only the browser process is a direct child of seelen-ui.exe, the renderers are
# children of it.
$stale = @(Get-CimInstance Win32_Process -Filter "Name='msedgewebview2.exe' AND ParentProcessId=$($s.Id)" |
           Where-Object { $_.ExecutablePath -and $_.ExecutablePath -notlike "*\$pv\*" })
if ($stale.Count -eq 0) { exit }

# Safety valve: never restart twice within 10 minutes, so a mismatch that
# somehow refuses to clear cannot become a restart loop every 5 minutes.
if ((Test-Path $stamp) -and (((Get-Date) - (Get-Item $stamp).LastWriteTime).TotalMinutes -lt 10)) {
    Log "runtime mismatch ($pv), but restarted less than 10 minutes ago - skipping"
    exit
}

Log "restart: registered runtime=$pv, running=$($stale[0].ExecutablePath)"
New-Item -Path $stamp -ItemType File -Force | Out-Null
Stop-Process -Id $s.Id -Force
Start-Sleep -Seconds 3
Start-Process explorer.exe $aumid
Log "restarted"
