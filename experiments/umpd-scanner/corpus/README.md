# Real-mod corpus

Do not commit downloaded mod JARs to this repository. Store the files in a local, read-only corpus directory and keep only the manifest, source/version identifiers, and SHA-256 fingerprints in Git.

The initial manifest is a **candidate sampling frame**, not a claim that every listed project currently publishes a Fabric file for Minecraft 26.2. Verify each exact artifact on Modrinth or the project's official release page before scanning. Record the exact game version, loader, Modrinth version ID, download URL, and SHA-256. If a project has no 26.2 Fabric artifact, mark it unavailable for the primary cohort and either replace it with a same-category project or place it in a separately labelled historical-version cohort.

## Downloading a pinned Modrinth cohort

From PowerShell, run the helper with the default local corpus directory:

~~~powershell
.\\fetch-modrinth-corpus.ps1
~~~

The helper queries the official Modrinth project-version endpoint for the exact game version and loader, prefers stable releases, caps downloads at 42 projects and 2 GiB by default, verifies the API-provided SHA-512 when present, computes SHA-256, and writes a separate local manifest. Projects without a matching version are marked unavailable rather than silently substituted.

You can change the cohort and budget:

~~~powershell
.\\fetch-modrinth-corpus.ps1 -MinecraftVersion '26.2' -Loader 'fabric' -MaxDownloads 42 -MaxTotalBytes 2147483648
~~~

Official API contract: [List a project's versions](https://docs.modrinth.com/api/operations/getprojectversions/). Downloaded JARs stay outside Git; verify licenses and keep them for local research only.

Recommended local layout:

~~~text
umpd-corpus/
  jars/
    <project-slug>-<version-id>.jar
  reports/
    <project-slug>-scan.json
  manifest.csv
~~~

Keep JARs read-only. Never install the corpus into a normal player profile for scanner tests. The scanner reads archives without extracting or executing their contents.
