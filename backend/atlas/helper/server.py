"""Unix-socket server for the root helper.

The peer identity is checked before a request is parsed. On Linux that check
is SO_PEERCRED. Tests pass their own lookup so the same refusal can run on
macOS, where that socket option does not exist.
"""

from __future__ import annotations

import json
import os
import socket
import struct
import subprocess  # nosec B404
import threading
from collections.abc import Callable
from pathlib import Path

from atlas.helper.protocol import Plan, ProtocolError, build_plan
from atlas.helper.sshkeys import change_key
from atlas.redact import mask_secrets

PeerLookup = Callable[[socket.socket], int | None]
Runner = Callable[[tuple[str, ...]], tuple[int, str, str]]


class HelperServer:
    """Accept one JSON request per connection and answer with one JSON object."""

    def __init__(
        self,
        path: Path,
        *,
        allowed_uids: frozenset[int],
        runner: Runner | None = None,
        peer_of: PeerLookup | None = None,
        keys_root: Path | None = None,
        delay_scale: float = 1.0,
    ) -> None:
        self.path = path
        self.allowed_uids = allowed_uids
        self.runner = runner or _subprocess_runner
        self.peer_of = peer_of or _peer_uid
        self.keys_root = keys_root or Path("/")
        self.delay_scale = delay_scale
        self._pending: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._sock: socket.socket | None = None

    def serve_forever(self) -> None:
        """Listen until :meth:`close` is called."""
        if self.path.exists():
            self.path.unlink()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(self.path))
        os.chmod(self.path, 0o660)  # nosec B103
        server.listen(4)
        server.settimeout(0.2)
        self._sock = server
        while not self._stop.is_set():
            try:
                conn, _addr = server.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def close(self) -> None:
        """Stop accepting and cancel a reboot that has not fired."""
        self._stop.set()
        with self._lock:
            for timer in self._pending.values():
                timer.cancel()
            self._pending.clear()
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    def _handle(self, conn: socket.socket) -> None:
        with conn:
            uid = self.peer_of(conn)
            if uid not in self.allowed_uids:
                _send(conn, {"ok": False, "error": "The peer is not allowed to call the helper."})
                return
            try:
                raw = _read_line(conn)
                request = json.loads(raw.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError, OSError):
                _send(conn, {"ok": False, "error": "The request is not JSON."})
                return
            if not isinstance(request, dict):
                _send(conn, {"ok": False, "error": "The request is not an object."})
                return
            _send(conn, self.dispatch(request))

    def dispatch(self, request: dict[str, object]) -> dict[str, object]:
        """Run one already-authenticated request."""
        op = request.get("op")
        if op == "host.cancel":
            return self._cancel(request.get("pending"))
        params = request.get("params")
        if not isinstance(op, str) or not isinstance(params, dict):
            return {"ok": False, "error": "The request needs an operation and parameters."}
        try:
            plan = build_plan(op, params)
        except ProtocolError as exc:
            return {"ok": False, "error": exc.message}
        if plan.op in {"ssh.add", "ssh.remove"}:
            key = params.get("key")
            username = plan.confirm
            if not isinstance(key, str):
                return {"ok": False, "error": "The SSH line is not a public key."}
            try:
                message = change_key(self.keys_root, username, key, remove=plan.op == "ssh.remove")
            except ProtocolError as exc:
                return {"ok": False, "error": exc.message}
            return {"ok": True, "result": message}
        if plan.delay_seconds:
            return self._schedule(plan)
        return self._run(plan)

    def _schedule(self, plan: Plan) -> dict[str, object]:
        token = os.urandom(8).hex()
        delay = plan.delay_seconds * self.delay_scale

        def fire() -> None:
            with self._lock:
                self._pending.pop(token, None)
            self.runner(plan.argv)

        timer = threading.Timer(delay, fire)
        with self._lock:
            self._pending[token] = timer
        timer.daemon = True
        timer.start()
        return {"ok": True, "pending": token, "delay_seconds": plan.delay_seconds}

    def _cancel(self, token: object) -> dict[str, object]:
        if not isinstance(token, str):
            return {"ok": False, "error": "A pending id is required."}
        with self._lock:
            timer = self._pending.pop(token, None)
        if timer is None:
            return {"ok": False, "error": "That pending action is not waiting."}
        timer.cancel()
        return {"ok": True, "result": "cancelled"}

    def _run(self, plan: Plan) -> dict[str, object]:
        code, stdout, stderr = self.runner(plan.argv)
        return {
            "ok": code == 0,
            "code": code,
            "stdout": mask_secrets(stdout)[:4000],
            "stderr": mask_secrets(stderr)[:4000],
        }


def _subprocess_runner(argv: tuple[str, ...]) -> tuple[int, str, str]:
    completed = subprocess.run(  # nosec B603
        list(argv),
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed.returncode, completed.stdout, completed.stderr


def _peer_uid(conn: socket.socket) -> int | None:
    """Read the peer uid. Returns ``None`` where the platform has no SO_PEERCRED."""
    try:
        option = socket.SO_PEERCRED  # type: ignore[attr-defined]
    except AttributeError:
        return None
    try:
        raw = conn.getsockopt(socket.SOL_SOCKET, option, struct.calcsize("3i"))
    except OSError:
        return None
    _pid, uid, _gid = struct.unpack("3i", raw)
    return int(uid)


def _read_line(conn: socket.socket) -> bytes:
    raw = b""
    while b"\n" not in raw and len(raw) < 65536:
        chunk = conn.recv(4096)
        if not chunk:
            break
        raw += chunk
    return raw.strip()


def _send(conn: socket.socket, payload: dict[str, object]) -> None:
    try:
        conn.sendall(json.dumps(payload).encode("utf-8") + b"\n")
    except OSError:
        return
