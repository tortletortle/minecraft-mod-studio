param(
    [string]$CorpusDir = (Join-Path $env:LOCALAPPDATA "MMS\UMPD\corpus"),
    [string]$MinecraftVersion = "26.2",
    [string]$Loader = "fabric",
    [int]$MaxDownloads = 42,
    [long]$MaxTotalBytes = 2147483648
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSCommandPath
$ManifestPath = Join-Path $ProjectRoot "manifest.csv"
if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
    throw "Candidate manifest not found: $ManifestPath"
}
if ($MaxDownloads -lt 1 -or $MaxDownloads -gt 100) {
    throw "MaxDownloads must be between 1 and 100."
}

$CorpusDir = [System.IO.Path]::GetFullPath($CorpusDir)
$JarDir = Join-Path $CorpusDir "jars"
New-Item -ItemType Directory -Force -Path $JarDir | Out-Null
$Rows = @(Import-Csv -LiteralPath $ManifestPath)
$Headers = @{ "User-Agent" = "MMS-UMPD/0.1.0 (https://github.com/tortletortle/minecraft-mod-studio)" }
$GameFilter = [System.Uri]::EscapeDataString((ConvertTo-Json @($MinecraftVersion) -Compress))
$LoaderFilter = [System.Uri]::EscapeDataString((ConvertTo-Json @($Loader) -Compress))
$Downloaded = 0
[long]$TotalBytes = 0

foreach ($Row in $Rows) {
    if ($Downloaded -ge $MaxDownloads) { break }
    if ($Row.scanner_status -eq "DOWNLOADED" -and $Row.sha256) { continue }

    $Slug = $Row.modrinth_slug
    Write-Host "Checking $Slug for $Loader / Minecraft $MinecraftVersion ..."
    try {
        $Url = "https://api.modrinth.com/v2/project/$Slug/version?game_versions=$GameFilter&loaders=$LoaderFilter"
        $Versions = @(Invoke-RestMethod -Uri $Url -Headers $Headers -Method Get)
        if ($Versions.Count -eq 0) {
            $Row.scanner_status = "NOT_AVAILABLE_FOR_COHORT"
            $Row.notes = "No $Loader version published for Minecraft $MinecraftVersion."
            continue
        }

        $Version = $Versions | Where-Object { $_.version_type -eq "release" } | Select-Object -First 1
        if ($null -eq $Version) {
            $Version = $Versions | Where-Object { $_.version_type -eq "beta" } | Select-Object -First 1
        }
        if ($null -eq $Version) {
            $Version = $Versions | Select-Object -First 1
        }
        $JarFiles = $Version.files | Where-Object {
            $_.filename.ToLowerInvariant().EndsWith(".jar") -and
            $_.filename -notmatch "(?i)(sources|dev|javadoc)\\.jar$" -and
            $_.file_type -notin @("sources-jar", "dev-jar", "javadoc-jar")
        }
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
        $Target = Join-Path $JarDir "$SafeSlug-$($Version.id)-$($File.filename)"
        if (-not (Test-Path -LiteralPath $Target -PathType Leaf)) {
            Invoke-WebRequest -Uri $File.url -Headers $Headers -OutFile $Target
        }

        $ActualSize = (Get-Item -LiteralPath $Target).Length
        if ($ActualSize -ne $FileSize) {
            Remove-Item -LiteralPath $Target -Force
            throw "Downloaded size mismatch for $Slug (expected $FileSize, received $ActualSize)."
        }
        $Sha256 = (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($File.hashes.sha512) {
            $Sha512 = (Get-FileHash -LiteralPath $Target -Algorithm SHA512).Hash.ToLowerInvariant()
            if ($Sha512 -ne $File.hashes.sha512.ToLowerInvariant()) {
                Remove-Item -LiteralPath $Target -Force
                throw "SHA-512 verification failed for $Slug."
            }
        }

        $Row.selected_minecraft_version = $MinecraftVersion
        $Row.modrinth_version_id = $Version.id
        $Row.download_url = $File.url
        $Row.sha256 = $Sha256
        $Row.scanner_status = "DOWNLOADED"
        $Row.notes = "version=$($Version.version_number); channel=$($Version.version_type); loader=$Loader; file=$($File.filename)"
        $Downloaded++
        $TotalBytes += (Get-Item -LiteralPath $Target).Length
    } catch {
        $Row.scanner_status = "DOWNLOAD_OR_API_ERROR"
        $Row.notes = $_.Exception.Message
        Write-Warning "$Slug failed: $($_.Exception.Message)"
    }
    Start-Sleep -Milliseconds 350
}

$UpdatedManifest = Join-Path $CorpusDir "manifest-$MinecraftVersion-$Loader.csv"
$Rows | Export-Csv -LiteralPath $UpdatedManifest -NoTypeInformation -Encoding UTF8
Write-Host "Downloaded this run: $Downloaded"
Write-Host "Bytes downloaded this run: $TotalBytes"
Write-Host "Local JAR directory: $JarDir"
Write-Host "Updated manifest: $UpdatedManifest"
Write-Host "JARs remain local and are not copied into the Git repository."
