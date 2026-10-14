# Detector guide

A stack claim is a derived fact. It names a rule and points at a file and a line. If the files are missing, the scan records `unknown` and the reason.

## Add a YAML rule

Rules live in `backend/atlas/detectors/rules/stacks.yaml`. A rule matches files under a project root that was found from a running anchor: a systemd working directory, a container bind, a cron path, or a site root. The knowledge file `backend/atlas/knowledge/services.yaml` is reference text. It is never stored as a fact.

## Prove it

1. Add a tree under `fixtures/` with the marker file and the line the rule should cite.
2. Add a test that runs `discover` on that tree and checks the fact value, the rule id, and the evidence path.
3. Run `uv run --project backend pytest`.

The same root can be more than one project when two anchors point at it. The project id is the first 16 hex characters of SHA-256 over the anchor kind and the normalized root.
