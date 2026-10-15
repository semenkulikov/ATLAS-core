# Security policy

ATLAS reads a map of one Linux server. A flaw in the panel is a flaw in that map.

## Reporting

Write to the address in the repository profile with the title "ATLAS security". Include the version, the affected path, and a way to reproduce the issue. Do not open a public issue for an unfixed vulnerability.

The maintainer aims to answer within 7 days and to publish a fix before describing the details. There is no bug bounty.

## What a release is

Version 1.0.0 ships a signed x86_64 archive on [GitHub Releases](https://github.com/semenkulikov/ATLAS-core/releases/latest). The one-line installer (`packaging/get-atlas.sh`) downloads that archive, checks SHA-256 (and minisign when available), then runs the archive `install.sh`. Prefer the published scripts from this repository or a release tag you trust.

## Scope

The panel protects against remote scanners, other unprivileged users on the host, a stolen session, and content in logs or README files. It does not protect against root. Root can read the database and the helper socket without using the panel.
