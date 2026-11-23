param(
    [string]$CorpusDir = (Join-Path $env:LOCALAPPDATA "MMS\UMPD\corpus"),
    [string]$MinecraftVersion = "26.2",
    [string]$Loader = "fabric",
    [int]$MaxDownloads = 42,
    [long]$MaxTotalBytes = 2147483648
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $PSCommandPath
$CandidateManifestPath = Join-Path $ScriptDir "manifest.csv"
if (-not (Test-Path -LiteralPath $CandidateManifestPath -PathType Leaf)) {
    throw "Candidate manifest not found: $CandidateManifestPath"
}
if ($MaxDownloads -lt 1 -or $MaxDownloads -gt 100) {
    throw "MaxDownloads must be between 1 and 100."
}
if ($MaxTotalBytes -le 0) {
    throw "MaxTotalBytes must be positive."
}
if ([string]::IsNullOrWhiteSpace($MinecraftVersion) -or [string]::IsNullOrWhiteSpace($Loader)) {
    throw "MinecraftVersion and Loader are required."
}

$CorpusDir = [System.IO.Path]::GetFullPath($CorpusDir)
$JarDir = Join-Path $CorpusDir "jars"
New-Item -ItemType Directory -Force -Path $JarDir | Out-Null
$UpdatedManifest = Join-Path $CorpusDir "manifest-$MinecraftVersion-$Loader.csv"
$InputManifestPath = if (Test-Path -LiteralPath $UpdatedManifest -PathType Leaf) {
    $UpdatedManifest
} else {
    $CandidateManifestPath
}
$Rows = @(Import-Csv -LiteralPath $InputManifestPath)
$RequiredColumns = @(
    "modrinth_file_name", "local_file_name", "size_bytes", "sha512", "downloaded_at"
)
foreach ($Row in $Rows) {
    foreach ($Column in $RequiredColumns) {
        if (-not $Row.PSObject.Properties[$Column]) {
            $Row | Add-Member -NotePropertyName $Column -NotePropertyValue ""
        }
    }
}

$Headers = @{ "User-Agent" = "MMS-UMPD/0.1.0 (https://github.com/tortletortle/minecraft-mod-studio)" }
$GameFilter = [System.Uri]::EscapeDataString((ConvertTo-Json @($MinecraftVersion) -Compress))
$LoaderFilter = [System.Uri]::EscapeDataString((ConvertTo-Json @($Loader) -Compress))
$PinnedOrVerified = 0
[long]$TotalBytes = 0

function Test-VerifiedArtifact {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][pscustomobject]$Row
    )
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $false
    }
    $Attributes = [System.IO.File]::GetAttributes($Path)
    if (($Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Refusing to follow a symbolic-link/reparse-point corpus file: $Path"
    }
    if ([string]::IsNullOrWhiteSpace($Row.sha256)) {
        return $false
    }
    $ActualSize = (Get-Item -LiteralPath $Path).Length
    if (-not [string]::IsNullOrWhiteSpace($Row.size_bytes) -and
        $ActualSize -ne [long]$Row.size_bytes) {
        return $false
    }
    $ActualSha256 = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($ActualSha256 -ne $Row.sha256.ToLowerInvariant()) {
        return $false
    }
    if (-not [string]::IsNullOrWhiteSpace($Row.sha512)) {
        $ActualSha512 = (Get-FileHash -LiteralPath $Path -Algorithm SHA512).Hash.ToLowerInvariant()
        if ($ActualSha512 -ne $Row.sha512.ToLowerInvariant()) {
            return $false
        }
    }
    return $true
}

foreach ($Row in $Rows) {
    if ($PinnedOrVerified -ge $MaxDownloads) {
        break
    }

    $Slug = $Row.modrinth_slug
    Write-Host "Checking $Slug for $Loader / Minecraft $MinecraftVersion ..."

    try {
        # Reuse a previously pinned artifact only after re-verifying its local bytes.
        if ($Row.scanner_status -eq "DOWNLOADED" -and
            -not [string]::IsNullOrWhiteSpace($Row.local_file_name)) {
            $ExistingName = [System.IO.Path]::GetFileName($Row.local_file_name)
            if ($ExistingName -ne $Row.local_file_name) {
                throw "Unsafe local_file_name in manifest for $Slug."
            }
            $ExistingPath = Join-Path $JarDir $ExistingName
            if (Test-VerifiedArtifact -Path $ExistingPath -Row $Row) {
                $ExistingSize = (Get-Item -LiteralPath $ExistingPath).Length
                if (($TotalBytes + $ExistingSize) -gt $MaxTotalBytes) {
                    $Row.scanner_status = "SKIPPED_SIZE_LIMIT"
                    $Row.notes = "Previously pinned artifact exceeds the current total byte budget."
                    continue
                }
                $TotalBytes += $ExistingSize
                $PinnedOrVerified++
                continue
            }
            if (Test-Path -LiteralPath $ExistingPath -PathType Leaf) {
                Remove-Item -LiteralPath $ExistingPath -Force
            }
        }

        if (-not [string]::IsNullOrWhiteSpace($Row.modrinth_version_id)) {
            # Re-fetch the exact version ID stored in the local manifest; never silently upgrade it.
            $VersionUrl = "https://api.modrinth.com/v2/version/$($Row.modrinth_version_id)"
            $Version = Invoke-RestMethod -Uri $VersionUrl -Headers $Headers -Method Get -TimeoutSec 30
        } else {
            $VersionsUrl = "https://api.modrinth.com/v2/project/$Slug/version?game_versions=$GameFilter&loaders=$LoaderFilter"
            $Versions = @(Invoke-RestMethod -Uri $VersionsUrl -Headers $Headers -Method Get -TimeoutSec 30)
            if ($Versions.Count -eq 0) {
                $Row.scanner_status = "NOT_AVAILABLE_FOR_COHORT"
                $Row.notes = "No $Loader version published for Minecraft $MinecraftVersion."
                continue
            }

            $Version = $Versions |
                Where-Object { $_.version_type -eq "release" } |
                Sort-Object date_published -Descending |
                Select-Object -First 1
            if ($null -eq $Version) {
                $Version = $Versions |
                    Where-Object { $_.version_type -eq "beta" } |
                    Sort-Object date_published -Descending |
                    Select-Object -First 1
            }
            if ($null -eq $Version) {
                $Version = $Versions |
                    Sort-Object date_published -Descending |
                    Select-Object -First 1
            }
        }

        if ($Version.game_versions -notcontains $MinecraftVersion -or
            $Version.loaders -notcontains $Loader) {
            $Row.scanner_status = "PINNED_VERSION_MISMATCH"
            $Row.notes = "The selected Modrinth version ID does not match the requested game version/loader."
            continue
        }

        $JarFiles = @($Version.files | Where-Object {
            $_.filename.ToLowerInvariant().EndsWith(".jar") -and
            $_.filename -notmatch "(?i)(sources|dev|javadoc)\.jar$" -and
            $_.file_type -notin @("sources-jar", "dev-jar", "javadoc-jar")
        })
        $File = $JarFiles | Where-Object { $_.primary } | Select-Object -First 1
        if ($null -eq $File) {
            $File = $JarFiles | Select-Object -First 1
        }
        if ($null -eq $File) {
            $Row.scanner_status = "NO_JAR_FILE"
            $Row.notes = "Version metadata contained no JAR file."
            continue
        }

        [long]$FileSize = $File.size
        if ($FileSize -le 0 -or ($TotalBytes + $FileSize) -gt $MaxTotalBytes) {
            $Row.scanner_status = "SKIPPED_SIZE_LIMIT"
            $Row.notes = "Download would exceed the configured total byte budget."
            continue
        }

        $SafeSlug = $Slug -replace "[^A-Za-z0-9._-]", "_"
        $SafeFileName = [System.IO.Path]::GetFileName($File.filename)
        $LocalFileName = "$SafeSlug-$($Version.id)-$SafeFileName"
        if (-not [string]::IsNullOrWhiteSpace($Row.local_file_name)) {
            $LocalFileName = [System.IO.Path]::GetFileName($Row.local_file_name)
        }
        if ([System.IO.Path]::GetFileName($LocalFileName) -ne $LocalFileName) {
            throw "Unsafe local corpus file name for $Slug."
        }
        $Target = Join-Path $JarDir $LocalFileName
        if (Test-Path -LiteralPath $Target -PathType Leaf) {
            $Attributes = [System.IO.File]::GetAttributes($Target)
            if (($Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Refusing to overwrite a symbolic-link/reparse-point corpus file: $Target"
            }
            Remove-Item -LiteralPath $Target -Force
        }

        $Temp = "$Target.download-$([guid]::NewGuid().ToString('N'))"
        try {
            Invoke-WebRequest -Uri $File.url -Headers $Headers -Method Get -OutFile $Temp -TimeoutSec 90 -UseBasicParsing
            $ActualSize = (Get-Item -LiteralPath $Temp).Length
            if ($ActualSize -ne $FileSize) {
                throw "Downloaded size mismatch for $Slug (expected $FileSize, received $ActualSize)."
            }

            $Stream = [System.IO.File]::OpenRead($Temp)
            try {
                $Magic = New-Object byte[] 4
                $Read = $Stream.Read($Magic, 0, $Magic.Length)
            } finally {
                $Stream.Dispose()
            }
            if ($Read -lt 4 -or $Magic[0] -ne 0x50 -or $Magic[1] -ne 0x4b) {
                throw "Downloaded file is not a ZIP/JAR archive: $Slug."
            }

            $Sha256 = (Get-FileHash -LiteralPath $Temp -Algorithm SHA256).Hash.ToLowerInvariant()
            $Sha512 = (Get-FileHash -LiteralPath $Temp -Algorithm SHA512).Hash.ToLowerInvariant()
            if ($File.hashes.sha512 -and $Sha512 -ne $File.hashes.sha512.ToLowerInvariant()) {
                throw "SHA-512 verification failed for $Slug."
            }
            if ($File.hashes.sha1) {
                $Sha1 = (Get-FileHash -LiteralPath $Temp -Algorithm SHA1).Hash.ToLowerInvariant()
                if ($Sha1 -ne $File.hashes.sha1.ToLowerInvariant()) {
                    throw "SHA-1 verification failed for $Slug."
                }
            }
            if (-not [string]::IsNullOrWhiteSpace($Row.sha256) -and
                $Sha256 -ne $Row.sha256.ToLowerInvariant()) {
                throw "Pinned SHA-256 changed for $Slug; refusing to replace the recorded artifact."
            }
            if (-not [string]::IsNullOrWhiteSpace($Row.sha512) -and
                $Sha512 -ne $Row.sha512.ToLowerInvariant()) {
                throw "Pinned SHA-512 changed for $Slug; refusing to replace the recorded artifact."
            }
            if (-not [string]::IsNullOrWhiteSpace($Row.modrinth_file_name) -and
                $File.filename -ne $Row.modrinth_file_name) {
                throw "Pinned Modrinth file name changed for $Slug."
            }

            Move-Item -LiteralPath $Temp -Destination $Target
        } finally {
            if (Test-Path -LiteralPath $Temp -PathType Leaf) {
                Remove-Item -LiteralPath $Temp -Force
            }
        }

        $Row.loader_target = $Loader
        $Row.selected_minecraft_version = $MinecraftVersion
        $Row.modrinth_version_id = $Version.id
        $Row.download_url = $File.url
        $Row.sha256 = $Sha256
        $Row.sha512 = $Sha512
        $Row.modrinth_file_name = $File.filename
        $Row.local_file_name = $LocalFileName
        $Row.size_bytes = $ActualSize
        $Row.downloaded_at = [DateTime]::UtcNow.ToString("o")
        $Row.scanner_status = "DOWNLOADED"
        $Row.notes = "version=$($Version.version_number); channel=$($Version.version_type); loader=$Loader; file=$($File.filename)"
        $TotalBytes += $ActualSize
        $PinnedOrVerified++
    } catch {
        $Row.scanner_status = "DOWNLOAD_OR_API_ERROR"
        $Row.notes = $_.Exception.Message
        Write-Warning "$Slug failed: $($_.Exception.Message)"
    } finally {
        Start-Sleep -Milliseconds 350
    }
}

$Rows | Export-Csv -LiteralPath $UpdatedManifest -NoTypeInformation -Encoding UTF8
Write-Host "Pinned or verified artifacts this run: $PinnedOrVerified"
Write-Host "Bytes represented in this cohort: $TotalBytes"
Write-Host "Local JAR directory: $JarDir"
Write-Host "Updated manifest: $UpdatedManifest"
Write-Host "JARs remain local and are not copied into the Git repository."
