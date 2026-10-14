"""Root helper entry point. It does not import the web framework."""

from __future__ import annotations

import argparse
from pathlib import Path

from atlas.helper.server import HelperServer


def main(argv: list[str] | None = None) -> int:
    """Listen on the helper socket until the process is stopped."""
    parser = argparse.ArgumentParser(prog="atlas-helper")
    parser.add_argument("--socket", default="/run/atlas/helper.sock")
    parser.add_argument(
        "--uid", type=int, required=True, help="Uid of the unprivileged web process."
    )
    parser.add_argument("--keys-root", default="/")
    args = parser.parse_args(argv)
    server = HelperServer(
        Path(args.socket),
        allowed_uids=frozenset({args.uid, 0}),
        keys_root=Path(args.keys_root),
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 130
    finally:
        server.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
