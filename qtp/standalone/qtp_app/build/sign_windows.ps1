[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ExePath,
    [string]$ExportCerPath = "",
    [switch]$AllowUntrustedRoot
)

$ErrorActionPreference = "Stop"

$resolvedExe = (Resolve-Path -LiteralPath $ExePath).Path
$cert = $null
$tempPfxCert = $false

if ($env:QTP_SIGN_PFX -and (Test-Path -LiteralPath $env:QTP_SIGN_PFX)) {
    $pfxFlags = [System.Security.Cryptography.X509Certificates.X509KeyStorageFlags]::UserKeySet
    $pfxPass = if ($env:QTP_SIGN_PFX_PASSWORD) { $env:QTP_SIGN_PFX_PASSWORD } else { "" }
    $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($env:QTP_SIGN_PFX, $pfxPass, $pfxFlags)
    $tempPfxCert = $true
} elseif ($env:QTP_SIGN_THUMBPRINT) {
    $thumb = $env:QTP_SIGN_THUMBPRINT.Trim().ToUpperInvariant()
    $cert = Get-ChildItem Cert:\CurrentUser\My, Cert:\LocalMachine\My -ErrorAction SilentlyContinue |
        Where-Object { $_.Thumbprint -eq $thumb -and $_.HasPrivateKey -and $_.NotAfter -gt (Get-Date) } |
        Select-Object -First 1
    if (-not $cert) {
        throw "Belirtilen QTP_SIGN_THUMBPRINT sertifikası bulunamadı veya süresi dolmuş: $thumb"
    }
} else {
    $now = Get-Date
    $cert = Get-ChildItem Cert:\CurrentUser\My |
        Where-Object {
            $_.Subject -eq "CN=Murat Sönmez" -and
            $_.HasPrivateKey -and
            $_.NotAfter -gt $now -and
            ($_.EnhancedKeyUsageList | Where-Object { $_.ObjectId -eq "1.3.6.1.5.5.7.3.3" })
        } |
        Sort-Object NotAfter -Descending |
        Select-Object -First 1
    if (-not $cert) {
        $cert = New-SelfSignedCertificate `
            -Type CodeSigningCert `
            -Subject "CN=Murat Sönmez" `
            -FriendlyName "Murat Sönmez Code Signing (QTP)" `
            -KeyAlgorithm RSA `
            -KeyLength 4096 `
            -HashAlgorithm SHA256 `
            -KeyExportPolicy Exportable `
            -NotAfter (Get-Date).AddYears(5) `
            -CertStoreLocation "Cert:\CurrentUser\My"
    }
}

$cerTarget = $ExportCerPath
if (-not $cerTarget) {
    $cerTarget = Join-Path ([System.IO.Path]::GetTempPath()) ("qtp_pub_" + $cert.Thumbprint + ".cer")
}
$cerDir = Split-Path -Parent $cerTarget
if ($cerDir -and -not (Test-Path -LiteralPath $cerDir)) {
    New-Item -ItemType Directory -Path $cerDir -Force | Out-Null
}
Export-Certificate -Cert $cert -FilePath $cerTarget -Type CERT -Force | Out-Null
$pubCheck = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($cerTarget)
if ($pubCheck.HasPrivateKey) {
    throw "Dışa aktarılan ortak sertifika beklenmedik biçimde özel anahtar içeriyor."
}

$isSelfSigned = ($cert.Issuer -eq $cert.Subject)
if ($isSelfSigned) {
    $inTp = Get-ChildItem Cert:\CurrentUser\TrustedPublisher -ErrorAction SilentlyContinue |
        Where-Object { $_.Thumbprint -eq $cert.Thumbprint }
    if (-not $inTp) {
        Import-Certificate -FilePath $cerTarget -CertStoreLocation Cert:\CurrentUser\TrustedPublisher | Out-Null
    }
    $inRoot = Get-ChildItem Cert:\CurrentUser\Root, Cert:\LocalMachine\Root -ErrorAction SilentlyContinue |
        Where-Object { $_.Thumbprint -eq $cert.Thumbprint }
    if (-not $inRoot) {
        $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
            [Security.Principal.WindowsBuiltInRole]::Administrator
        )
        if ($isAdmin) {
            Import-Certificate -FilePath $cerTarget -CertStoreLocation Cert:\LocalMachine\Root | Out-Null
            $inLmTp = Get-ChildItem Cert:\LocalMachine\TrustedPublisher -ErrorAction SilentlyContinue |
                Where-Object { $_.Thumbprint -eq $cert.Thumbprint }
            if (-not $inLmTp) {
                Import-Certificate -FilePath $cerTarget -CertStoreLocation Cert:\LocalMachine\TrustedPublisher | Out-Null
            }
        } elseif ([Environment]::UserInteractive -and -not $env:CI -and -not $env:GITHUB_ACTIONS) {
            Import-Certificate -FilePath $cerTarget -CertStoreLocation Cert:\CurrentUser\Root | Out-Null
        }
    }
}

if (-not $ExportCerPath -and (Test-Path -LiteralPath $cerTarget)) {
    Remove-Item -LiteralPath $cerTarget -Force -ErrorAction SilentlyContinue
}

$timestampServers = @(
    "http://timestamp.digicert.com",
    "http://timestamp.sectigo.com"
)
$signedSig = $null
$usedTimestamp = "none"

foreach ($tsUrl in $timestampServers) {
    $attempt = Set-AuthenticodeSignature -FilePath $resolvedExe -Certificate $cert -HashAlgorithm SHA256 -TimestampServer $tsUrl -ErrorAction SilentlyContinue
    if ($attempt -and $attempt.SignerCertificate -and $attempt.Status -ne [System.Management.Automation.SignatureStatus]::NotSigned -and $attempt.Status -ne [System.Management.Automation.SignatureStatus]::HashMismatch) {
        $signedSig = $attempt
        $usedTimestamp = $tsUrl
        break
    }
}

if (-not $signedSig) {
    $signedSig = Set-AuthenticodeSignature -FilePath $resolvedExe -Certificate $cert -HashAlgorithm SHA256
    $usedTimestamp = "none"
}

$verify = Get-AuthenticodeSignature -FilePath $resolvedExe
if (-not $verify.SignerCertificate) {
    throw "İmza doğrulanamadı: SignerCertificate boş ($($verify.Status))."
}
if ($verify.Status -eq [System.Management.Automation.SignatureStatus]::HashMismatch -or $verify.Status -eq [System.Management.Automation.SignatureStatus]::NotSigned) {
    throw "İmza bütünlük hatası: $($verify.Status) ($($verify.StatusMessage))"
}
if (-not $AllowUntrustedRoot -and $verify.Status -ne [System.Management.Automation.SignatureStatus]::Valid) {
    throw "Authenticode doğrulaması geçerli değil: $($verify.Status) — $($verify.StatusMessage)"
}
if (-not $tempPfxCert -and $verify.SignerCertificate.Subject -ne "CN=Murat Sönmez") {
    throw "Beklenen imzalayıcı 'CN=Murat Sönmez', bulunan: '$($verify.SignerCertificate.Subject)'"
}

[PSCustomObject]@{
    Path = $resolvedExe
    Status = $verify.Status.ToString()
    Subject = $verify.SignerCertificate.Subject
    Thumbprint = $verify.SignerCertificate.Thumbprint
    HashAlgorithm = $verify.SignerCertificate.SignatureAlgorithm.FriendlyName
    TimestampServer = $usedTimestamp
    TimeStamper = if ($verify.TimeStamperCertificate) { $verify.TimeStamperCertificate.Subject } else { "" }
} | ConvertTo-Json -Compress
