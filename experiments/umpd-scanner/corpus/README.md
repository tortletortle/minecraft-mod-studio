# Real-mod corpus

Do not commit downloaded mod JARs to this repository. Store the files in a local, read-only corpus directory and keep only the manifest, source/version identifiers, and SHA-256 fingerprints in Git.

The initial manifest is a **candidate sampling frame**, not a claim that every listed project currently publishes a Fabric file for Minecraft 26.2. Verify each exact artifact on Modrinth or the project's official release page before scanning. Record the exact game version, loader, Modrinth version ID, download URL, and SHA-256. If a project has no 26.2 Fabric artifact, mark it unavailable for the primary cohort and either replace it with a same-category project or place it in a separately labelled historical-version cohort.

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
