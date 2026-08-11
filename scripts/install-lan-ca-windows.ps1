<#
.SYNOPSIS
    Trusts the homelab mkcert root CA on Windows, so https://<service>.lan works
    without a browser warning in Edge, Chrome and Firefox.

.DESCRIPTION
    The .lan domains are served by Caddy (LXC 110, 192.168.0.208) with a
    certificate signed by a local mkcert CA. Windows and Chromium browsers share
    the Windows certificate store; Firefox keeps its own NSS store and mkcert
    cannot write to it on Windows at all (mkcert supports Firefox only on macOS
    and Linux). This script covers both:

      1. imports rootCA.pem into LocalMachine\Root   -> Edge, Chrome, curl.exe
      2. drops the same CA into the Firefox certificate directory and writes a
         distribution\policies.json with Certificates.Install +
         Certificates.ImportEnterpriseRoots          -> Firefox
      3. checks that DNS points at AdGuard, flushes the resolver cache
      4. verifies with a real HTTPS request

    Idempotent: re-running it re-checks every step and changes only what is off.

.PARAMETER CertPath
    Path to rootCA.pem on this machine. Default: Downloads\mkcert-rootCA.pem.

.PARAMETER Fetch
    Pull rootCA.pem off the Caddy LXC through Proxmox first (needs working SSH
    to $ProxmoxHost, see docs/hosts/winpc.md).

.EXAMPLE
    # elevated PowerShell 7
    .\install-lan-ca-windows.ps1 -Fetch

.EXAMPLE
    .\install-lan-ca-windows.ps1 -CertPath C:\Users\Nex\Downloads\rootCA.pem

.NOTES
    Must run elevated: LocalMachine\Root and the Firefox install directory are
    both machine-wide. Firefox must be fully closed for the policy to take
    effect; a running instance reads policies.json only at startup.
#>
[CmdletBinding()]
param(
    [string]$CertPath    = "$env:USERPROFILE\Downloads\mkcert-rootCA.pem",
    [switch]$Fetch,
    [string]$ProxmoxHost = 'root@192.168.0.109',
    [int]$CaddyVmid      = 110,
    [string]$DnsServer   = '192.168.0.111',
    [string]$TestUrl     = 'https://homepage.lan',
    [switch]$SkipFirefox
)

$ErrorActionPreference = 'Stop'

function Write-Step { param([string]$Text) Write-Host "`n== $Text" -ForegroundColor Cyan }
function Write-Ok   { param([string]$Text) Write-Host "   OK   $Text" -ForegroundColor Green }
function Write-Warn { param([string]$Text) Write-Host "   WARN $Text" -ForegroundColor Yellow }

# --- elevation ---------------------------------------------------------------
$identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this from an elevated PowerShell (Run as administrator).'
}

# --- 1. get the CA file ------------------------------------------------------
Write-Step "Root CA file"
if ($Fetch) {
    Write-Host "   pulling rootCA.pem from LXC $CaddyVmid via $ProxmoxHost"
    & ssh $ProxmoxHost "pct pull $CaddyVmid /etc/caddy/certs/rootCA.pem /tmp/rootCA.pem"
    if ($LASTEXITCODE -ne 0) { throw "ssh pct pull failed (exit $LASTEXITCODE)" }
    & scp "${ProxmoxHost}:/tmp/rootCA.pem" $CertPath
    if ($LASTEXITCODE -ne 0) { throw "scp failed (exit $LASTEXITCODE)" }
}
if (-not (Test-Path -LiteralPath $CertPath)) {
    throw "No CA file at $CertPath. Re-run with -Fetch, or copy rootCA.pem there by hand."
}

# Parse without Import-Certificate: this works identically on Windows PowerShell
# 5.1 and PowerShell 7, and accepts the PEM armour mkcert writes.
$raw   = Get-Content -Raw -LiteralPath $CertPath
$match = [regex]::Match($raw, '(?s)-----BEGIN CERTIFICATE-----(.*?)-----END CERTIFICATE-----')
if ($match.Success) {
    $bytes = [Convert]::FromBase64String(($match.Groups[1].Value -replace '\s', ''))
    $cert  = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 (,$bytes)
} else {
    $cert  = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 (Resolve-Path $CertPath).Path
}
Write-Ok "$($cert.Subject)"
Write-Host "        thumbprint $($cert.Thumbprint)  expires $($cert.NotAfter.ToString('yyyy-MM-dd'))"
if ($cert.NotAfter -lt (Get-Date)) { Write-Warn 'This CA has already expired - regenerate it on the Caddy LXC.' }

# --- 2. Windows store (Edge, Chrome, curl.exe, .NET) -------------------------
Write-Step "Windows trust store (LocalMachine\Root)"
$store = New-Object System.Security.Cryptography.X509Certificates.X509Store('Root', 'LocalMachine')
$store.Open('ReadWrite')
try {
    $found = $store.Certificates.Find('FindByThumbprint', $cert.Thumbprint, $false)
    if ($found.Count -gt 0) {
        Write-Ok 'already trusted'
    } else {
        $store.Add($cert)
        Write-Ok 'imported'
    }
} finally {
    $store.Close()
}

# --- 3. Firefox (its own NSS store, ignores the Windows store by default) ----
if (-not $SkipFirefox) {
    Write-Step 'Firefox'
    $ffDirs = @(
        "$env:ProgramFiles\Mozilla Firefox",
        "${env:ProgramFiles(x86)}\Mozilla Firefox"
    ) | Where-Object { $_ -and (Test-Path -LiteralPath (Join-Path $_ 'firefox.exe')) }

    if (-not $ffDirs) {
        Write-Warn 'Firefox not found in the usual locations - skipping.'
    } else {
        # Certificates.Install looks for bare file names in these two directories.
        # Using a bare name avoids the backslash-escaping trap of full paths.
        $certName = 'homelab-lan-rootCA.pem'
        foreach ($dir in @("$env:LOCALAPPDATA\Mozilla\Certificates", "$env:APPDATA\Mozilla\Certificates")) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
            Copy-Item -LiteralPath $CertPath -Destination (Join-Path $dir $certName) -Force
        }
        Write-Ok "CA copied to the Firefox certificate directories as $certName"

        foreach ($dir in $ffDirs) {
            $distDir  = Join-Path $dir 'distribution'
            $polPath  = Join-Path $distDir 'policies.json'
            New-Item -ItemType Directory -Path $distDir -Force | Out-Null

            # Merge rather than overwrite - an existing policies.json may carry
            # unrelated policy the machine depends on.
            if (Test-Path -LiteralPath $polPath) {
                Copy-Item -LiteralPath $polPath -Destination "$polPath.bak" -Force
                $policies = Get-Content -Raw -LiteralPath $polPath | ConvertFrom-Json
            } else {
                $policies = [pscustomobject]@{}
            }
            if (-not $policies.PSObject.Properties['policies']) {
                $policies | Add-Member -NotePropertyName policies -NotePropertyValue ([pscustomobject]@{})
            }
            if (-not $policies.policies.PSObject.Properties['Certificates']) {
                $policies.policies | Add-Member -NotePropertyName Certificates -NotePropertyValue ([pscustomobject]@{})
            }
            $certPolicy = $policies.policies.Certificates

            $installList = @()
            if ($certPolicy.PSObject.Properties['Install']) { $installList = @($certPolicy.Install) }
            if ($installList -notcontains $certName) { $installList += $certName }

            $certPolicy | Add-Member -NotePropertyName Install `
                -NotePropertyValue ([string[]]$installList) -Force
            $certPolicy | Add-Member -NotePropertyName ImportEnterpriseRoots `
                -NotePropertyValue $true -Force

            $policies | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $polPath -Encoding UTF8
            Write-Ok "policy written: $polPath"
        }
        Write-Warn 'Close every Firefox window and start it again - policies.json is read only at startup.'
    }
}

# --- 4. DNS ------------------------------------------------------------------
Write-Step 'DNS'
$servers = Get-DnsClientServerAddress -AddressFamily IPv4 |
    Where-Object { $_.ServerAddresses } |
    Select-Object InterfaceAlias, @{n = 'Servers'; e = { $_.ServerAddresses -join ', ' } }
$servers | Format-Table -AutoSize | Out-String | Write-Host
if ($servers.Servers -join ',' -notmatch [regex]::Escape($DnsServer)) {
    Write-Warn "AdGuard ($DnsServer) is not among the DNS servers - .lan names will not resolve."
    Write-Host  "        Set-DnsClientServerAddress -InterfaceAlias 'Ethernet' -ServerAddresses $DnsServer"
} else {
    Write-Ok "AdGuard ($DnsServer) in use"
}
Clear-DnsClientCache
Write-Ok 'resolver cache flushed'

# --- 5. verify ---------------------------------------------------------------
Write-Step "Verifying $TestUrl"
try {
    $response = Invoke-WebRequest -Uri $TestUrl -UseBasicParsing -TimeoutSec 15
    Write-Ok "HTTPS OK, HTTP $($response.StatusCode) - the certificate chain validated"
} catch {
    # An HTTP status error still means the TLS handshake succeeded, which is the
    # only thing being tested here. Only a missing response is a cert failure.
    if ($_.Exception.Response) {
        Write-Ok "TLS OK (service answered HTTP $([int]$_.Exception.Response.StatusCode))"
    } else {
        Write-Warn "$TestUrl failed: $($_.Exception.Message)"
        Write-Host '        Trust problem -> the CA above is not the one Caddy serves; re-pull it with -Fetch.'
        Write-Host '        Name problem  -> the domain is missing from the cert SAN list; regenerate the'
        Write-Host '                         cert on LXC 110 (see docs/hosts/caddy.md).'
        Write-Host '        No resolve    -> DNS is not pointing at AdGuard (see the DNS step above).'
    }
}

Write-Host "`nDone. Firefox needs a full restart before it picks the CA up.`n" -ForegroundColor Cyan
