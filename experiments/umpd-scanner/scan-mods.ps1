param(
    [string]$ModsPath = (Join-Path $env:APPDATA ".minecraft\mods"),
    [string]$ReportPath = "",
    [string]$MappingsPath = "",
    [string]$FromNamespace = "intermediary",
    [string]$ToNamespace = "named"
)

$ErrorActionPreference = "Stop"
$ScannerDir = Split-Path -Parent $PSCommandPath

if (-not (Test-Path -LiteralPath $ModsPath -PathType Container)) {
    throw "Mods directory not found: $ModsPath. Pass -ModsPath for your launcher instance."
}
if (-not (Get-Command javac -ErrorAction SilentlyContinue) -or -not (Get-Command java -ErrorAction SilentlyContinue)) {
    throw "JDK 21+ was not found on PATH. Install a JDK and reopen PowerShell."
}
if (-not [string]::IsNullOrWhiteSpace($MappingsPath) -and -not (Test-Path -LiteralPath $MappingsPath -PathType Leaf)) {
    throw "Tiny v2 mapping file not found: $MappingsPath"
}
if ([string]::IsNullOrWhiteSpace($MappingsPath) -and ($FromNamespace -ne "intermediary" -or $ToNamespace -ne "named")) {
    throw "Namespace overrides require -MappingsPath."
}

$ModsFull = [System.IO.Path]::GetFullPath($ModsPath)
if ([string]::IsNullOrWhiteSpace($ReportPath)) {
    $Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $ReportPath = Join-Path $ScannerDir "build\reports\umpd-$Stamp.json"
}
$ReportFull = [System.IO.Path]::GetFullPath($ReportPath)
$ModsPrefix = $ModsFull.TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
if ($ReportFull.Equals($ModsFull, [System.StringComparison]::OrdinalIgnoreCase) -or
    $ReportFull.StartsWith($ModsPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Report output must be outside the scanned mods directory."
}

$BuildDir = Join-Path $ScannerDir "build\umpd"
$MainOutput = Join-Path $BuildDir "classes\main"
$TestOutput = Join-Path $BuildDir "classes\test"
$ReportParent = Split-Path -Parent $ReportFull
New-Item -ItemType Directory -Force -Path $MainOutput, $TestOutput, $ReportParent | Out-Null

$MainSources = @(Get-ChildItem -LiteralPath (Join-Path $ScannerDir "src\main\java") -Filter "*.java" -File -Recurse | ForEach-Object { $_.FullName })
$TestSources = @(Get-ChildItem -LiteralPath (Join-Path $ScannerDir "src\test\java") -Filter "*.java" -File -Recurse | ForEach-Object { $_.FullName })
if ($MainSources.Count -eq 0 -or $TestSources.Count -eq 0) {
    throw "Scanner source files were not found under src/main/java and src/test/java."
}

Push-Location $ScannerDir
try {
    & javac --release 21 -encoding UTF-8 -d $MainOutput @MainSources
    if ($LASTEXITCODE -ne 0) { throw "Main-source compilation failed: $LASTEXITCODE" }

    & javac --release 21 -encoding UTF-8 -cp $MainOutput -d $TestOutput @TestSources
    if ($LASTEXITCODE -ne 0) { throw "Test-source compilation failed: $LASTEXITCODE" }

    $TestClasspath = $MainOutput + ";" + $TestOutput
    & java -cp $TestClasspath dev.tortletortle.mms.umpd.ProtocolScannerSelfTest
    if ($LASTEXITCODE -ne 0) { throw "UMPD self-tests failed: $LASTEXITCODE" }

    $ScanArgs = @("scan", $ModsFull, "--out", $ReportFull)
    if (-not [string]::IsNullOrWhiteSpace($MappingsPath)) {
        $ScanArgs += @("--mappings", [System.IO.Path]::GetFullPath($MappingsPath),
                       "--from-namespace", $FromNamespace, "--to-namespace", $ToNamespace)
    }
    & java -cp $MainOutput dev.tortletortle.mms.umpd.ProtocolScanner @ScanArgs
    if ($LASTEXITCODE -ne 0) { throw "UMPD scan failed: $LASTEXITCODE" }
} finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $ReportFull -PathType Leaf)) {
    throw "Scanner completed without producing the expected report: $ReportFull"
}
Write-Host "UMPD report: $ReportFull"
