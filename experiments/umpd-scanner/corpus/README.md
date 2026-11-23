# Real-mod corpus

Do not commit downloaded mod JARs to this repository. Store the files in a local, read-only corpus directory and keep only the manifest, source/version identifiers, and SHA-256 fingerprints in Git.

The initial manifest is a **candidate sampling frame**, not a claim that every listed project currently publishes a Fabric file for Minecraft 26.2. Verify each exact artifact on Modrinth or the project's official release page before scanning. Record the exact game version, loader, Modrinth version ID, download URL, and SHA-256. If a project has no 26.2 Fabric artifact, mark it unavailable for the primary cohort and either replace it with a same-category project or place it in a separately labelled historical-version cohort.

## Downloading a pinned Modrinth cohort

From PowerShell, run the helper with the default local corpus directory:

~~~powershell
.\fetch-modrinth-corpus.ps1
~~~

The helper queries the official Modrinth project-version endpoint for the exact game version and loader, prefers stable releases, caps the cohort at 42 artifacts and 2 GiB by default, verifies API-provided SHA-1/SHA-512 when present, computes SHA-256/SHA-512, checks ZIP/JAR magic and file size, and writes a separate local manifest with the exact version ID, remote file name, local file name, size, hashes, and download timestamp. Downloads use temporary files and are moved into place only after verification. Re-running the helper reuses the local manifest, re-verifies existing bytes, and fetches the exact previously pinned version ID if a local JAR is missing or corrupt; it does not silently upgrade to a newer version. Projects without a matching version are marked unavailable rather than silently substituted.

You can change the cohort and budget:

~~~powershell
.\fetch-modrinth-corpus.ps1 -MinecraftVersion '26.2' -Loader 'fabric' -MaxDownloads 42 -MaxTotalBytes 2147483648
~~~

Official API contracts: [List a project's versions](https://docs.modrinth.com/api/operations/getprojectversions/) and [Get a version by ID](https://docs.modrinth.com/api/operations/getversion/). Downloaded JARs stay outside Git; verify licenses and keep them for local research only.

Recommended local layout:

~~~text
umpd-corpus/
  jars/
    <project-slug>-<version-id>.jar
  reports/
    <project-slug>-scan.json
  manifest.csv
~~~

Keep JARs read-only after download. Never install the corpus into a normal player profile for scanner tests. The scanner reads archives without extracting or executing their contents. If a pinned file fails its local hash check, the downloader replaces it only from the same recorded Modrinth version ID and refuses a changed recorded SHA-256/SHA-512.

## Scan and cross-check the pinned cohort

After downloading the cohort, scan only the local `jars/` directory and write the report beside the local manifest:

~~~powershell
$Corpus = Join-Path $env:LOCALAPPDATA "MMS\UMPD\corpus"
..\scan-mods.ps1 -ModsPath (Join-Path $Corpus "jars") -ReportPath (Join-Path $Corpus "reports\umpd-26.2-fabric.json")
~~~

Then cross-check every downloaded manifest row against the report and local bytes:

~~~bash
python3 ./audit-corpus-report.py --corpus-dir "$HOME/.local/share/MMS/UMPD/corpus" --minecraft-version 26.2 --loader fabric
~~~

The auditor verifies local SHA-256/SHA-512 and size, checks the report's input directory and per-artifact hash, flags missing/failed scans, and produces `cohort-crosscheck.csv`, `cohort-summary.json`, and `cohort-summary.md`. It also counts class/member evidence separately from `BYTECODE_CALL_SITE` evidence. These are scanner observations, not precision/recall; manual ground-truth labels are still required. On Windows, run the same Python command with the actual `-corpus-dir` path, for example `$env:LOCALAPPDATA\MMS\UMPD\corpus`.
