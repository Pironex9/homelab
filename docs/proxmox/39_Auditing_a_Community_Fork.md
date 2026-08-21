# Auditing a Community Fork Before Running It, and Migrating to Calibre-Web-NextGen

**Date:** 2026-08-21
**Hostname:** docker-host (LXC 100), komodo (LXC 105)
**IP address:** 192.168.0.110, 192.168.0.105

---

## Overview

Calibre-Web-Automated (CWA) stopped publishing releases. The container on LXC 100 was running `v4.0.6`, built 2026-02-04 - the last release, six and a half months old, against 404 open issues upstream. A community fork, Calibre-Web-NextGen, ships regularly and fixes bugs that were hit directly during [38 - Calibre Metadata Cleanup](./38_Calibre_Metadata_Cleanup.md).

Switching to a fork maintained by a pseudonymous account under a year old, which openly states most of its code is AI-written, is not a decision to make from a README. This is the audit that preceded it - and the method transfers to any container image from a small project.

## The maintenance picture, measured

The GitHub API answers this in one loop, and the numbers are the whole argument:

| Project | Stars | Last release | Open issues | License |
|---|---|---|---|---|
| janeczku/calibre-web | 18018 | 0.6.27, 2026-08-08 | 394 | GPL-3.0 |
| crocodilestick/Calibre-Web-Automated | 6136 | **v4.0.6, 2026-02-04** | 404 | GPL-3.0 |
| new-usemame/Calibre-Web-NextGen | 200 | v4.1.39, 2026-08-21 | 189 | GPL-3.0 |
| Kareadita/Kavita | 11522 | v0.9.0.2, 2026-05-14 | 165 | GPL-3.0 |
| gotson/komga | 6587 | 1.26.3, 2026-08-12 | 21 | MIT |

The upstream repo still receives commits - last push 2026-08-07 - which is what makes "is it maintained" the wrong question. **Releases are what reach a container; commits are not.**

## Step 1: does the published image come from the published source?

This is the question that makes a source audit meaningful, and it is answerable without downloading the image. Resolve the tag to a digest at the registry, then ask GitHub what it attested for that digest:

```bash
T=$(curl -s "https://ghcr.io/token?scope=repository:<owner>/<image>:pull&service=ghcr.io" | jq -r .token)
curl -sI -H "Authorization: Bearer $T" -H "Accept: application/vnd.oci.image.index.v1+json" \
  https://ghcr.io/v2/<owner>/<image>/manifests/latest | grep -i docker-content-digest

curl -s "https://api.github.com/repos/<owner>/<repo>/attestations/<digest>"
```

The payload inside the DSSE envelope is base64 and decodes to a SLSA provenance statement:

```
latest digest:   sha256:4826c217a5167655ea5efa32c13a6e40c2f36d5563e7155ef5631ca55ee094b8
predicateType:   https://slsa.dev/provenance/v1
builder:         .../.github/workflows/docker-image-build-release.yml@refs/tags/v4.1.39
forras:          git+https://github.com/new-usemame/Calibre-Web-NextGen@refs/tags/v4.1.39
                 gitCommit: d59d00fd16a65205aaeaf9af648a0bddd0e75e09
```

That commit is the one a `git clone` of the repo lands on, so the source that can be read is the source that was built. The build workflow also signs with cosign keyless (Fulcio + Rekor), emits an SBOM, sets `provenance: mode=max`, and pins every GitHub Action to a commit SHA.

The same query against the incumbent:

```
upstream latest digest: sha256:c31a738b6d5ec6982c050063dd3f063b6943eb1051fc81144789f840d9093a8d
attesztaciok: 0 | Not Found
```

**The image already in production had no provenance at all.** On this axis the small fork is verifiable and the popular upstream is not, which is the opposite of the intuition that ranks projects by star count.

## Step 2: diff the source against the version being replaced

Clone both at the exact points being compared - the fork's HEAD and the tag currently running - and count the constructs that matter:

```bash
git clone --depth 1 --branch v4.0.6 https://github.com/crocodilestick/Calibre-Web-Automated.git upstream
git clone --depth 1 https://github.com/new-usemame/Calibre-Web-NextGen.git nextgen
```

```
eval(                    upstream=0  nextgen=0
exec(                    upstream=0  nextgen=0
subprocess shell=True    upstream=0  nextgen=0
pickle.loads             upstream=0  nextgen=0
os.system                upstream=3  nextgen=3
base64.b64decode         upstream=4  nextgen=7
urlopen                  upstream=4  nextgen=5
```

A count is a filter, not a verdict - every delta then gets read. The three new `b64decode` calls are FLAC cover art via `mutagen`, a kosync HTTP Basic header, and a `data:` URI cover. The extra `urlopen` is a DNB metadata provider. No committed secrets: a scan for AWS keys, `ghp_` tokens and PEM private-key headers returned nothing.

## Step 3: diff the outbound hostnames

More useful than any keyword scan, because a backdoor needs somewhere to talk to. Extract every URL host from both trees and take the set difference:

```bash
grep -rhoE "https?://[a-zA-Z0-9.-]+" <tree>/cps <tree>/scripts | sed -E 's|https?://||' | sort -u
```

Most of what appears is metadata providers and documentation examples. One entry was the project's own domain, and that is the one worth chasing:

```
cps/templates/cwng_feedback_popup.html:20   data-endpoint="https://app.calibrewebnextgen.com/feedback"
cps/web.py:170                              ["'self'", "https://app.calibrewebnextgen.com"]
```

The second line widens the application's Content-Security-Policy `connect-src` so the first line is allowed to fire. Reading the template and the design note settles what it is: the dialog appears only when a user clicks "Back to the classic view" in the new UI, the payload is `{type, reasons, comment}` - five checkboxes and a free-text box - and the Cloudflare Worker behind it stores `{type, reasons, comment, created_at}` in KV, hashing the connection IP with a salt for a 60-second rate limit without storing it.

That is user-initiated feedback, not telemetry. It is still an outbound third-party endpoint compiled into a self-hosted application, and the project's "no telemetry, and your library is not sent anywhere" line does not mention it. Blocking the host in AdGuard disables it with no side effects.

## Step 4: find the link the provenance does not cover

Provenance proves the image was built from public source by a public workflow. It says nothing about what that build downloaded.

```dockerfile
FROM ghcr.io/new-usemame/pbs-cache:cpython-3.13.14-20260623 AS pbs_ghcr
FROM ghcr.io/new-usemame/pbs-cache:kepubify-v4.0.4          AS kepubify_ghcr
```

The Python interpreter and the kepubify binary are copied from a private registry the maintainer controls. The documented reason is sound - GitHub's release CDN intermittently returns 404 to the Actions egress, which broke every build - but the script that populates the mirror has no integrity check:

```bash
grep -nE "sha256|shasum|checksum|digest|verify" scripts/ensure-python-mirror.sh   # no hits, 95 lines
```

So there is no cryptographic tie between what is in the mirror and what `astral-sh/python-build-standalone` published. **This is the one link taken on trust**, and it is exactly the kind of gap that a provenance badge can hide: everything downstream of the mirror is verifiable, the mirror itself is not.

## Step 5: who is the maintainer

```
login:       new-usemame  ("CWNG Maintainer nate")
letrehozva:  2025-12-06   (8.5 honapja)
kovetok:     8
repok:       5 (ebbol 3 nulla csillagos fork)
nev/ceg/email: nincs
```

The project's own notes record the domain as registered at Porkbun, paid via crypto, with WHOIS privacy. None of that is evidence of anything; plenty of competent developers work this way. It does mean there is no identity to hold accountable, and that belongs in the decision alongside the good engineering signals.

## The decision, and why the scope of the service is the deciding factor

The audit produced strong positives (verifiable provenance, cosign, SBOM, SHA-pinned actions, clean source diff, security fixes the incumbent lacks) and three named negatives (a feedback endpoint, an unverified build mirror, an anonymous maintainer under a year old).

What settles it is not the balance of those but **what the service holds**: a LAN-only ebook library on port 8085, no reverse-proxy entry in Caddy or Pangolin, no credentials, no payment data, no personal documents. The blast radius of being wrong is a book collection that exists in full on another machine.

The same evidence would not justify the switch for a password manager.

Two hardening choices follow from the negatives rather than despite them:

- **Pin the digest, not the tag.** A fast-moving project that states most of its code is AI-written should not be able to land a new build unreviewed. `:latest` allows exactly that.
- **Keep the audited digest in the compose file as a comment**, together with the previous image's digest, so the rollback target is not something to reconstruct later.

## Migration

The stack is deployed by Komodo from git, so the change is a commit, not a command on the host. Worth verifying which - the running container names its source:

```bash
docker inspect calibre-web-automated \
  --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}'
# /etc/komodo/repos/github/compose/proxmox-lxc-100/calibre-web-automated
```

Back up first. Three databases matter and they live in two different places:

```bash
cp /srv/docker-data/calibrewebauto/app.db /srv/docker-data/calibrewebauto/cwa.db <backup>/
cp /mnt/storage/media/konyvek/metadata.db <backup>/
docker inspect calibre-web-automated --format '{{index .RepoDigests 0}}' > <backup>/elozo-kep.txt
```

```diff
- image: crocodilestick/calibre-web-automated:latest
+ image: ghcr.io/new-usemame/calibre-web-nextgen@sha256:4826c217a5167655ea5efa32c13a6e40c2f36d5563e7155ef5631ca55ee094b8
```

Then commit, push, and drive Komodo through its API - `PullStack` to refresh the clone on LXC 100, then `DeployStack`. Both return `status: InProgress` immediately; the completion signal is the clone and the container themselves:

```bash
ssh root@192.168.0.110 'grep image: /etc/komodo/repos/.../docker-compose.yml'
ssh root@192.168.0.110 'docker inspect calibre-web-automated --format "{{.Image}}"'
```

## Verification after the switch

```
kep:      ghcr.io/new-usemame/calibre-web-nextgen@sha256:4826c217...
CWA_INSTALLED_VERSION=v4.1.39
HTTP 302 a :8085-on

konyvek: 93 | leirassal: 50 | borito nelkul: 0
felhasznalok: ['Guest', 'admin']
auto_convert_ignored_formats = pdf
inotifywait -m -r ... -e close_write -e moved_to -e create /cwa-book-ingest
```

The library, the users and the CWA settings carried over untouched - the data format is byte-compatible in both directions, which is what makes the rollback a one-line revert rather than a restore.

Two incidental findings:

- `/app/CWA_RELEASE` no longer exists; the version now comes from the `CWA_INSTALLED_VERSION` environment variable and `/app/calibre-web-automated/VERSION`. Any script reading the old path silently gets an empty string.
- `compose/CLAUDE.md` claimed this stack was UI-defined rather than git-based. Komodo's `ListStacks` and the container's own label both say otherwise. A deployment note that is wrong sends the next change to the wrong place.

## Lessons

1. **"Is it maintained" is the wrong question; "when was the last release" is the right one.** A repo with commits from last week and no release since February ships nothing to a container.
2. **Provenance is checkable from a shell, for free, before pulling anything.** Resolve the tag to a digest at the registry, then query `api.github.com/repos/{owner}/{repo}/attestations/{digest}`. An unsigned image from a popular project is weaker evidence than a signed one from an obscure fork.
3. **Provenance covers the build, not the build's inputs.** Read the Dockerfile for anything fetched from a source the attestation does not describe, and check whether that fetch verifies a hash.
4. **Diff the outbound hostnames, not just the keywords.** Exfiltration needs a destination, and the set difference against the version being replaced puts every new destination on one screen.
5. **Let the blast radius decide how much evidence is enough.** The identical audit result justifies running a LAN-only book server and does not justify running a password manager.
6. **Pin the digest when the project moves fast**, and keep the previous digest in the file next to it. The rollback path is worth writing down while it is still known to work.
