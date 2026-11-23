param(
    [string]$ModsPath = (Join-Path $env:APPDATA ".minecraft\mods"),
    [string]$ReportPath = ""
)

$ErrorActionPreference = "Stop"
$ScannerDir = Split-Path -Parent $PSCommandPath

if (-not (Test-Path -LiteralPath $ModsPath -PathType Container)) {
    throw "Mods directory not found: $ModsPath. Pass -ModsPath for your launcher instance."
}
if (-not (Get-Command gradle -ErrorAction SilentlyContinue)) {
    throw "Gradle was not found on PATH. Install Gradle 8.7+ or run the Gradle task from your IDE."
}

$ModsFull = [System.IO.Path]::GetFullPath($ModsPath)
if ([string]::IsNullOrWhiteSpace($ReportPath)) {
    $Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $ReportPath = Join-Path $ScannerDir "build\reports\umpd-$Stamp.json"
}
$ReportFull = [System.IO.Path]::GetFullPath($ReportPath)
if ($ReportFull.StartsWith($ModsFull, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Report output must be outside the scanned mods directory."
}

$ReportParent = Split-Path -Parent $ReportFull
New-Item -ItemType Directory -Force -Path $ReportParent | Out-Null
$AppArgs = 'scan "' + $ModsFull + '" --out "' + $ReportFull + '"'

Push-Location $ScannerDir
try {
    & gradle --no-daemon verifyScanner run "--args=$AppArgs"
    if ($LASTEXITCODE -ne 0) {
        throw "UMPD Gradle task failed with exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $ReportFull -PathType Leaf)) {
    throw "Scanner completed without producing the expected report: $ReportFull"
}
Write-Host "UMPD report: $ReportFull"
