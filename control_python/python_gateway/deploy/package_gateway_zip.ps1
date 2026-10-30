# FR3D — Empaqueta el programa gateway (sin config/datos) para OTA zip.
# Uso (desde control_python/):
#   .\python_gateway\deploy\package_gateway_zip.ps1
#   .\python_gateway\deploy\package_gateway_zip.ps1 -OutDir C:\temp\fr3d-ota
#
# Salida:
#   fr3d-gateway-<ver>.zip
#   fr3d-gateway-<ver>.sha256
#   fr3d-gateway-latest.zip      (copia)
#   fr3d-gateway-latest.sha256
#   MANIFEST.json
param(
    [string]$OutDir = "",
    [string]$VersionOverride = ""
)

$ErrorActionPreference = "Stop"
$DeployDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$GatewayDir = Split-Path -Parent $DeployDir
$Root = Split-Path -Parent $GatewayDir
Set-Location $Root

$VersionFile = Join-Path $GatewayDir "VERSION"
if ($VersionOverride) {
    $Version = $VersionOverride.Trim()
} elseif (Test-Path $VersionFile) {
    $Version = (Get-Content $VersionFile -Raw).Trim()
} else {
    $Version = "0.0.0-dev"
}

if (-not $OutDir) {
    $OutDir = Join-Path $Root "dist\gateway-ota"
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$Stage = Join-Path $env:TEMP "fr3d-gateway-ota-stage-$(Get-Random)"
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

function Copy-TextAsUnixLf {
    param([string]$Src, [string]$Dst)
    # Detecta UTF-16 (sin BOM) típico de editores en Windows; escribe UTF-8 sin BOM + LF.
    $bytes = [IO.File]::ReadAllBytes($Src)
    $utf16 = $false
    if ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE) {
        $utf16 = $true
    } elseif ($bytes.Length -ge 4 -and $bytes[1] -eq 0 -and $bytes[0] -ne 0) {
        $utf16 = $true
    }
    if ($utf16) {
        $text = [Text.Encoding]::Unicode.GetString($bytes)
    } else {
        $text = [Text.Encoding]::UTF8.GetString($bytes)
    }
    $text = $text -replace "`r`n", "`n" -replace "`r", "`n"
    # Quitar BOM UTF-8 si vino en el string
    if ($text.Length -gt 0 -and [int][char]$text[0] -eq 0xFEFF) {
        $text = $text.Substring(1)
    }
    $dstDir = Split-Path $Dst -Parent
    if (-not (Test-Path $dstDir)) {
        New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
    }
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [IO.File]::WriteAllBytes($Dst, $utf8.GetBytes($text))
}

try {
    $RootFiles = @(
        "control_and_merge_dual_serial_csv.py",
        "ui_config_csv.py",
        "fr3d_totem_bridge.py",
        "fr3d_totem_commands.py",
        "fr3d_totem_winder.py",
        "fr3d_totem_predictor.py",
        "fr3d_predictor_engine.py",
        "i18n.py",
        "locale_en.json",
        "requirements-gateway.txt",
        "setup_gateway_venv.sh",
        "run_gateway.sh"
    )

    foreach ($name in $RootFiles) {
        $src = Join-Path $Root $name
        if (Test-Path $src) {
            $dst = Join-Path $Stage $name
            if ($name -like "*.sh") {
                Copy-TextAsUnixLf -Src $src -Dst $dst
            } else {
                Copy-Item $src $dst -Force
            }
        } else {
            Write-Host "[Package] Omitido (no existe): $name"
        }
    }

    $StageGw = Join-Path $Stage "python_gateway"
    New-Item -ItemType Directory -Force -Path $StageGw | Out-Null

    Get-ChildItem $GatewayDir -Recurse -File -Include "*.py","*.service" | ForEach-Object {
        $rel = $_.FullName.Substring($GatewayDir.Length).TrimStart("\", "/") -replace '\\', '/'
        if ($rel -match "(^|/)\.venv(/|$)|__pycache__|csv_logs") { return }
        # No incluir configs de sitio ni overlays de lab.
        if ($rel -match "(^|/)config_gateway(\.|$)") { return }
        if ($rel -match "(^|/)PI(material|colors)\.csv$") { return }
        $dst = Join-Path $StageGw ($rel -replace '/', '\')
        $dstDir = Split-Path $dst -Parent
        if (-not (Test-Path $dstDir)) {
            New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
        }
        Copy-Item $_.FullName $dst -Force
    }

    $DeploySrc = Join-Path $GatewayDir "deploy"
    if (Test-Path $DeploySrc) {
        $DeployDst = Join-Path $StageGw "deploy"
        New-Item -ItemType Directory -Force -Path $DeployDst | Out-Null
        Get-ChildItem $DeploySrc -File | ForEach-Object {
            if ($_.Name -eq "desktop.ini") { return }
            $dst = Join-Path $DeployDst $_.Name
            if ($_.Extension -eq ".sh") {
                Copy-TextAsUnixLf -Src $_.FullName -Dst $dst
            } else {
                Copy-Item $_.FullName $dst -Force
            }
        }
    }

    $DataSrc = Join-Path $GatewayDir "data"
    if (Test-Path $DataSrc) {
        $DataDst = Join-Path $StageGw "data"
        New-Item -ItemType Directory -Force -Path $DataDst | Out-Null
        Get-ChildItem $DataSrc -File | ForEach-Object {
            if ($_.Name -eq "desktop.ini") { return }
            if ($_.Name -match "identity|secret") { return }
            Copy-Item $_.FullName (Join-Path $DataDst $_.Name) -Force
        }
    }

    # VERSION siempre en el paquete
    Set-Content -Path (Join-Path $StageGw "VERSION") -Value "$Version`n" -NoNewline -Encoding ascii

    $ReqHash = ""
    $ReqPath = Join-Path $Stage "requirements-gateway.txt"
    if (Test-Path $ReqPath) {
        $ReqHash = (Get-FileHash -Algorithm SHA256 -Path $ReqPath).Hash.ToLowerInvariant()
    }

    $Manifest = [ordered]@{
        version                 = $Version
        min_image               = "2026-07-01"
        requires_venv_rebuild   = $false
        requirements_sha256     = $ReqHash
        packaged_at             = (Get-Date).ToUniversalTime().ToString("o")
        excludes                = @(
            "config_gateway.csv",
            "PImaterial.csv",
            "PIcolors.csv",
            "csv_logs/",
            "fr3d_web/",
            ".venv/",
            "secrets/"
        )
    }
    $ManifestPath = Join-Path $Stage "MANIFEST.json"
    $json = ($Manifest | ConvertTo-Json -Depth 5)
    [IO.File]::WriteAllText($ManifestPath, $json + "`n", [Text.UTF8Encoding]::new($false))

    $ZipName = "fr3d-gateway-$Version.zip"
    $ZipPath = Join-Path $OutDir $ZipName
    if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }

    # Zip con rutas POSIX (Python): Compress-Archive de Windows a veces falla en unzip de Linux.
    $PyZipHelper = Join-Path $env:TEMP "fr3d_make_gateway_zip.py"
    @'
import zipfile, os, sys
stage, out = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for root, _dirs, files in os.walk(stage):
        for name in files:
            full = os.path.join(root, name)
            arc = os.path.relpath(full, stage).replace("\\", "/")
            zf.write(full, arcname=arc)
print("wrote", out)
'@ | Set-Content -Path $PyZipHelper -Encoding ascii
    python $PyZipHelper $Stage $ZipPath
    if (-not (Test-Path $ZipPath)) {
        throw "[Package] Fallo al crear zip con Python: $ZipPath"
    }

    $Sha = (Get-FileHash -Algorithm SHA256 -Path $ZipPath).Hash.ToLowerInvariant()
    $ShaPath = Join-Path $OutDir "fr3d-gateway-$Version.sha256"
    [IO.File]::WriteAllText($ShaPath, "$Sha  $ZipName`n", [Text.UTF8Encoding]::new($false))

    Copy-Item $ZipPath (Join-Path $OutDir "fr3d-gateway-latest.zip") -Force
    [IO.File]::WriteAllText(
        (Join-Path $OutDir "fr3d-gateway-latest.sha256"),
        "$Sha  fr3d-gateway-latest.zip`n",
        [Text.UTF8Encoding]::new($false)
    )
    Copy-Item $ManifestPath (Join-Path $OutDir "MANIFEST.json") -Force

    Write-Host "[Package] Version: $Version"
    Write-Host "[Package] Zip:     $ZipPath"
    Write-Host "[Package] SHA256:  $Sha"
    Write-Host "[Package] Latest:  $(Join-Path $OutDir 'fr3d-gateway-latest.zip')"
    Write-Host "[Package] Manifest:$(Join-Path $OutDir 'MANIFEST.json')"
}
finally {
    if (Test-Path $Stage) {
        Remove-Item $Stage -Recurse -Force -ErrorAction SilentlyContinue
    }
}
