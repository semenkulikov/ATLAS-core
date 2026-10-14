# Security policy

ATLAS reads a map of one Linux server. A flaw in the panel is a flaw in that map.

## Reporting

Write to the address in the repository profile with the title "ATLAS security". Include the version, the affected path, and a way to reproduce the issue. Do not open a public issue for an unfixed vulnerability.

The maintainer aims to answer within 7 days and to publish a fix before describing the details. There is no bug bounty.

## What a release is

Version 0.1.0 is not a signed release. `packaging/install.sh` refuses `--url` until a release is signed and published with a checksum. Do not pipe a downloaded script into a shell for this project until that exists.

## Scope

The panel protects against remote scanners, other unprivileged users on the host, a stolen session, and content in logs or README files. It does not protect against root. Root can read the database and the helper socket without using the panel.
