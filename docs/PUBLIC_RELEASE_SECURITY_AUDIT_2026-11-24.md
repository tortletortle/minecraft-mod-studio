# Public Release Security Audit — 2026-11-24

Repository: `tortletortle/minecraft-mod-studio`  
Current visibility: private  
Default branch: `main`  
Audited main SHA: `867e1bd37df2f039a395779493efb8cb20093287`  
Audit result: **DO NOT switch this existing repository to public yet.**

## Executive finding

A concrete privacy blocker exists in Git commit metadata.

- 38 branch heads were inspected.
- 31 of 38 branch-head commits have author and committer email metadata on a non-GitHub-noreply Outlook domain.
- The current `main` history contains 9 commits; 8 of 9 use that same non-noreply domain.
- The actual email address is deliberately not copied into this report.
- Git commit objects expose author/committer email metadata. Making this repository public would expose that address through public commit metadata/history.

Changing the GitHub account's "Keep my email addresses private" setting only affects future commits; it does not rewrite existing commit objects. Before public exposure, either rewrite all exposed history or create a separate sanitized public repository.

## Repository surface inspected

- 38 branch refs; all 38 recursive Git tree responses completed without truncation.
- 32 pull requests and 33 issue-list entries (including PR issue records) enumerated.
- 0 GitHub Releases returned by the Releases API.
- 21 distinct workflow files were inspected across active branch heads.
- Current main is a 16-file snapshot and has no workflow directory.
- Main SHA remains `867e1bd37df2f039a395779493efb8cb20093287`.

## Content and credential checks

### Path-level scan across 38 branch trees

No tracked paths matching common credential-bearing filenames were found, including:
- `.env*`, `.npmrc`, `.pypirc`, `.netrc`
- files named for secrets, credentials, tokens, passwords or private keys
- PEM/P12/PFX/JKS/keystore files
- Terraform state, SQLite/database files
- obvious compiled executables or archives in branch trees

The scan did find test evidence and logs, including Minecraft server logs, raw server logs, client console logs, and Gradle property files. Two `gradle.properties` files were inspected; both contained ordinary build/version configuration and no credential assignments.

### Manual content scan

Scanned:
- the three main HTML editor files;
- main README/project metadata and primary development/status docs;
- two Gradle properties files and selected runtime/readme files;
- 17 representative tracked test/server/client logs;
- two successful Actions job logs;
- two retained Actions artifacts, including nested material-source ZIP and two generated JARs.

No GitHub PAT, AWS key, Slack token, Google API key, private-key block, bearer token, basic-auth URL, or email address was detected in these sampled content files. Sampled Minecraft server IPs were loopback/private addresses. This is a targeted scan, **not a complete secret scan of every blob in every historical commit**.

The Actions logs contained a `server-password: GITHUB_TOKEN` literal placeholder; the actual `token` input was masked by GitHub as `***`. No raw token was found in the sampled logs.

GitHub code search returned no matches, but the repository metadata did not report an available code-search index. Therefore zero search results are not treated as proof of a clean repository.

### Pull requests and issues

The 32 PR titles/bodies and the one non-PR issue body returned by the issue listing were checked for common token patterns, email addresses and local user-profile paths. No matches were found in those bodies. Review comments and every historical issue comment were not exhaustively scanned.

## Actions/workflow exposure

Across 21 distinct workflow files:
- No `pull_request_target` or `workflow_run` trigger was found.
- No `secrets.*` references or explicit credential injection was found in the inspected workflow files.
- The inspected workflows use read-only `contents: read` permissions or empty permissions; no write permission was found in the inspected set.
- Workflows use version tags such as `actions/checkout@v4`; pinning third-party actions to full commit SHAs is recommended before accepting arbitrary public contributions.
- Several workflows are push-triggered on feature branches. Once public, standard GitHub-hosted runners are free for public repositories, but untrusted PRs and push-triggered jobs still need bounded concurrency, branch/path filters and least privilege.

## Actions artifacts/logs

Two non-expired artifacts were found on sampled successful runs:
- `mms-live-debugger-0.3.0.jar`
- `mms-v25-material-fixture`, containing a generated sample mod source ZIP, build result/log and JAR.

Both artifacts and their nested source/JAR contents were scanned for common credential patterns; no matches were found. Making the repository public will also make eligible Actions logs and artifacts publicly accessible, so future artifacts must be reviewed before upload.

## Public-readiness blockers

### P0 — Commit author email in history

Do not make the existing repository public while branch heads and main history still expose a non-noreply Outlook-domain email.

Safe choices:
1. Keep this repository private, create a new public mirror/repository from a sanitized snapshot, use a new root commit with GitHub noreply identity, and copy only reviewed branches/files. Keep the current repository as the private source/archive until the public mirror is validated.
2. If preserving all branches and PR history is essential, rewrite all refs locally with `git filter-repo` to replace author and committer email, preserve a private backup, validate every rewritten ref, then coordinate force-push/recreation of PRs. This changes commit SHAs and invalidates existing SHA-bound CI evidence. GitHub-managed PR refs and historical run/artifact visibility also need review; a rewrite should not be assumed to erase every previously exposed object.

### P1 — Incomplete historical secret scan

Before public visibility:
- run GitHub Secret Scanning / push protection if available, or an equivalent full-history scanner such as Gitleaks on every branch and tag;
- scan all historical commits, all 38 branch refs, PR refs, workflow logs and artifacts;
- rotate any credential found before publicizing. Deleting a file or rewriting history does not make a leaked credential safe; rotate it.

### P1 — Test logs and user-generated evidence

Review all raw logs/console captures for usernames, local paths, server addresses, world names and non-synthetic chat. The sampled logs showed loopback/private IPs and no email/user-profile path patterns, but not every log was content-scanned.

### P2 — Workflow hardening

Before opening the project to arbitrary external contributions:
- pin third-party actions to full commit SHAs;
- keep fork PR token permissions read-only and never expose secrets to untrusted PR code;
- add concurrency cancellation and narrow branch/path filters;
- avoid automatically running EULA-authorized or long-running game tests on untrusted PRs;
- review artifact contents and retention.

## Recommendation

**Keep the current repository private for now.** The existing repo has useful work and 38 branches, but the commit email finding is sufficient to block an immediate visibility flip.

Preferred low-risk route: preserve this repository as the private source-of-truth, create a clean public mirror with only reviewed source and sanitized commit identity, then use that public repository for free GitHub-hosted CI. Decide separately how reviewed feature branches will be promoted to the public mirror.

No visibility setting was changed. No branch was deleted or rewritten. No main commit was changed by this audit.
