# Contributing

Contributions are welcome as pull requests.

- Commit messages follow Conventional Commits.
- Add a `Signed-off-by` line to certify the [Developer Certificate of Origin](https://developercertificate.org/), version 1.1. There is no separate contributor license agreement.
- A new stack detector ships with a fixture and a test that cites the file and line of each claim.
- A bug fix ships with a test that failed before the fix.
- Run `uv run --project backend ruff check backend`, `mypy`, `pytest`, and `bandit` before opening a pull request. For the panel, run `npm test` and `npm run check` in `frontend/`.

The product does not send telemetry. Do not add a call that leaves the host unless it is an alert channel that stays disabled until the owner turns it on.
