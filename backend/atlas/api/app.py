"""The HTTP API. Every route except credential exchange requires an actor."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from atlas.api.problems import Problem, problem_response
from atlas.api.settings import Settings
from atlas.application.actions import (
    ActionError,
    control_enabled,
    request_action,
    restart_risks,
    scanned_hostname,
)
from atlas.application.alerts import (
    AlertError,
    list_channels,
    list_events,
    save_channel,
)
from atlas.application.audit import list_audit, verify_chain
from atlas.application.logs import LogError, read_log
from atlas.application.report import build_report, render_html, render_json, render_markdown
from atlas.application.scan import run_scan
from atlas.collectors.view import open_view
from atlas.logging import log_event
from atlas.metrics.sampler import default_sampler
from atlas.metrics.series import list_series, query_series, write_sample
from atlas.security.accounts import (
    AccessError,
    Actor,
    actor_from_api_token,
    actor_from_session,
    begin_enrollment,
    begin_member,
    confirm_enrollment,
    issue_api_token,
    login,
)
from atlas.security.tokens import provisioning_uri
from atlas.storage.db import Store

_LOG = logging.getLogger("atlas.api")
_READ = frozenset({"viewer", "operator", "owner"})
_CONTROL = frozenset({"operator", "owner"})
_ADMIN = frozenset({"owner"})
_SESSION_COOKIE = "atlas_session"
_CSRF_COOKIE = "atlas_csrf"
_SECURITY_HEADERS = {
    "content-security-policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; font-src 'self'; frame-ancestors 'none'; "
        "base-uri 'none'; form-action 'self'"
    ),
    "referrer-policy": "no-referrer",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
}


@dataclass
class AppState:
    """Dependencies for one API process."""

    store: Store
    settings: Settings
    sleeper: Callable[[float], None]
    clock: Callable[[], datetime]


def create_app(
    store: Store,
    settings: Settings,
    *,
    sleeper: Callable[[float], None] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> FastAPI:
    """Build the API. OpenAPI is not mounted publicly; owners fetch it explicitly."""
    app = FastAPI(title="ATLAS", version="1.0.0", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.atlas = AppState(
        store,
        settings,
        sleeper or time.sleep,
        clock or (lambda: datetime.now(UTC)),
    )
    app.add_exception_handler(Problem, _handle_problem)
    app.middleware("http")(_guard)
    app.add_api_route("/api/v1/auth/bootstrap", bootstrap, methods=["POST"])
    app.add_api_route("/api/v1/auth/enroll", enroll, methods=["POST"])
    app.add_api_route("/api/v1/auth/login", sign_in, methods=["POST"])
    app.add_api_route("/api/v1/auth/logout", logout, methods=["POST"])
    app.add_api_route("/api/v1/me", me, methods=["GET"])
    app.add_api_route("/api/v1/accounts", create_account, methods=["POST"])
    app.add_api_route("/api/v1/tokens", create_token, methods=["POST"])
    app.add_api_route("/api/v1/openapi.json", openapi, methods=["GET"])
    app.add_api_route("/api/v1/host", host, methods=["GET"])
    app.add_api_route("/api/v1/services", services, methods=["GET"])
    app.add_api_route("/api/v1/services/{unit}", service_one, methods=["GET"])
    app.add_api_route("/api/v1/containers", containers, methods=["GET"])
    app.add_api_route("/api/v1/containers/{container_id}", container_one, methods=["GET"])
    app.add_api_route("/api/v1/schedules", schedules, methods=["GET"])
    app.add_api_route("/api/v1/ports", ports, methods=["GET"])
    app.add_api_route("/api/v1/users", users, methods=["GET"])
    app.add_api_route("/api/v1/ssh-keys", ssh_keys, methods=["GET"])
    app.add_api_route("/api/v1/projects", projects, methods=["GET"])
    app.add_api_route("/api/v1/projects/{project_id}", project_one, methods=["GET"])
    app.add_api_route("/api/v1/projects/{project_id}/docs", project_docs, methods=["GET"])
    app.add_api_route("/api/v1/facts/{fact_id}/evidence", evidence, methods=["GET"])
    app.add_api_route("/api/v1/search", search, methods=["GET"])
    app.add_api_route("/api/v1/changes", changes, methods=["GET"])
    app.add_api_route("/api/v1/edges", edges, methods=["GET"])
    app.add_api_route("/api/v1/scans", scans, methods=["GET"])
    app.add_api_route("/api/v1/scans", start_scan, methods=["POST"])
    app.add_api_route("/api/v1/metrics/series", metric_series, methods=["GET"])
    app.add_api_route("/api/v1/metrics/query", metrics, methods=["GET"])
    app.add_api_route("/api/v1/logs", logs, methods=["GET"])
    app.add_api_route("/api/v1/export", export, methods=["GET"])
    app.add_api_route("/api/v1/control", control_status, methods=["GET"])
    app.add_api_route("/api/v1/audit", audit_log, methods=["GET"])
    app.add_api_route("/api/v1/actions/{op}", perform_action, methods=["POST"])
    app.add_api_route("/api/v1/alerts", alerts, methods=["GET"])
    app.add_api_route("/api/v1/alerts/channels", create_channel, methods=["POST"])
    app.add_api_websocket_route("/api/v1/stream", stream)
    _mount_panel(app)
    return app


def _handle_problem(_request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, Problem):
        return problem_response(exc)
    return problem_response(Problem(500, "The request failed.", "server.error"))


async def _guard(request: Request, call_next: Callable[[Request], Any]) -> Response:
    state = _state(request)
    host_name = request.headers.get("host", "").split(":", 1)[0]
    if host_name not in state.settings.allowed_hosts:
        return problem_response(Problem(400, "The Host header is not allowed.", "http.host"))
    if state.settings.allowed_ips:
        client = request.client.host if request.client else ""
        if client not in state.settings.allowed_ips:
            return problem_response(Problem(403, "This address is not allowed.", "http.address"))
    origin = request.headers.get("origin")
    if (
        origin
        and request.method not in {"GET", "HEAD", "OPTIONS"}
        and not _origin_ok(origin, request.headers.get("host", ""))
    ):
        return problem_response(Problem(403, "The Origin header does not match.", "http.origin"))
    response: Response = await call_next(request)
    for key, value in _SECURITY_HEADERS.items():
        response.headers.setdefault(key, value)
    return response


async def bootstrap(request: Request) -> Response:
    """Exchange the install token for a pending owner and a TOTP URI."""
    state = _state(request)
    body = await _body(request)
    try:
        pending = begin_enrollment(
            state.store.conn,
            token=str(body.get("token") or ""),
            username=str(body.get("username") or ""),
            password=str(body.get("password") or ""),
            now=state.clock(),
            ttl_seconds=state.settings.bootstrap_ttl_seconds,
        )
    except AccessError as exc:
        raise _access(exc) from exc
    log_event(
        _LOG, logging.INFO, "enrollment.started", username=pending.username, role=pending.role
    )
    return _json(
        request,
        {
            "enrollment_token": pending.token,
            "otpauth_uri": provisioning_uri(pending.totp_secret, pending.username),
        },
    )


async def enroll(request: Request) -> Response:
    """Confirm a TOTP code and, for a first owner, open a session."""
    state = _state(request)
    body = await _body(request)
    try:
        actor = confirm_enrollment(
            state.store.conn,
            token=str(body.get("token") or ""),
            code=str(body.get("code") or ""),
            now=state.clock(),
        )
    except AccessError as exc:
        raise _access(exc) from exc
    log_event(_LOG, logging.INFO, "account.created", username=actor.username, role=actor.role)
    return _with_session(request, actor, {"username": actor.username, "role": actor.role})


async def sign_in(request: Request) -> Response:
    """Open a session from a username, password, and TOTP code."""
    state = _state(request)
    body = await _body(request)
    try:
        actor = login(
            state.store.conn,
            username=str(body.get("username") or ""),
            password=str(body.get("password") or ""),
            code=str(body.get("code") or ""),
            now=state.clock(),
            sleeper=state.sleeper,
        )
    except AccessError as exc:
        log_event(_LOG, logging.INFO, "login.rejected")
        raise _access(exc) from exc
    log_event(_LOG, logging.INFO, "login.accepted", username=actor.username)
    return _with_session(request, actor, {"username": actor.username, "role": actor.role})


async def logout(request: Request) -> Response:
    actor = _require(request, _READ)
    _csrf(request, actor)
    if actor.session_id is not None:
        _state(request).store.conn.execute("DELETE FROM sessions WHERE id = ?", (actor.session_id,))
        _state(request).store.conn.commit()
    response = _json(request, {"status": "signed-out"})
    response.delete_cookie(_SESSION_COOKIE)
    response.delete_cookie(_CSRF_COOKIE)
    return response


async def me(request: Request) -> Response:
    actor = _require(request, _READ)
    return _json(request, {"username": actor.username, "role": actor.role, "via": actor.via})


async def create_account(request: Request) -> Response:
    actor = _require(request, _ADMIN)
    _csrf(request, actor)
    state = _state(request)
    body = await _body(request)
    try:
        pending = begin_member(
            state.store.conn,
            username=str(body.get("username") or ""),
            password=str(body.get("password") or ""),
            role=str(body.get("role") or "viewer"),
            now=state.clock(),
            ttl_seconds=state.settings.bootstrap_ttl_seconds,
        )
    except AccessError as exc:
        raise _access(exc) from exc
    return _json(
        request,
        {
            "enrollment_token": pending.token,
            "otpauth_uri": provisioning_uri(pending.totp_secret, pending.username),
            "role": pending.role,
        },
    )


async def create_token(request: Request) -> Response:
    actor = _require(request, _ADMIN)
    _csrf(request, actor)
    state = _state(request)
    body = await _body(request)
    scope = str(body.get("scope") or "viewer")
    ttl = body.get("ttl_seconds")
    try:
        raw = issue_api_token(
            state.store.conn,
            account_id=actor.account_id,
            name=str(body.get("name") or "api"),
            scope=scope,
            now=state.clock(),
            ttl_seconds=int(ttl) if isinstance(ttl, int) else None,
        )
    except AccessError as exc:
        raise _access(exc) from exc
    return _json(request, {"token": raw, "scope": scope})


async def control_status(request: Request) -> Response:
    _require(request, _READ)
    state = _state(request)
    return _json(
        request,
        {
            "enabled": control_enabled(state.store),
            "risks": restart_risks(state.store),
            "hostname": scanned_hostname(state.store),
        },
    )


async def audit_log(request: Request) -> Response:
    _require(request, _ADMIN)
    state = _state(request)
    return _json(
        request,
        {"items": list_audit(state.store.conn), "intact": verify_chain(state.store.conn)},
    )


async def alerts(request: Request) -> Response:
    _require(request, _READ)
    state = _state(request)
    return _json(
        request,
        {"events": list_events(state.store.conn), "channels": list_channels(state.store.conn)},
    )


async def create_channel(request: Request) -> Response:
    actor = _require(request, _ADMIN)
    _csrf(request, actor)
    body = await _body(request)
    try:
        save_channel(
            _state(request).store.conn,
            str(body.get("kind") or ""),
            str(body.get("target") or ""),
            enabled=body.get("enabled") is True,
        )
    except AlertError as exc:
        raise Problem(400, exc.message, "alert.channel") from exc
    return _json(request, {"status": "saved"})


async def perform_action(request: Request, op: str) -> Response:
    actor = _require(request, _READ)
    _csrf(request, actor)
    state = _state(request)
    body = await _body(request)
    raw_params = body.get("params")
    params = raw_params if isinstance(raw_params, dict) else {}
    client = request.client.host if request.client else ""
    try:
        outcome = request_action(
            state.store,
            username=actor.username,
            role=actor.role,
            ip=client,
            op=op,
            params=params,
            confirm=str(body.get("confirm") or ""),
            code=str(body.get("code") or ""),
            helper_socket=state.settings.helper_socket,
            now=state.clock(),
        )
    except ActionError as exc:
        raise Problem(exc.status, exc.message, exc.code) from exc
    status = 200 if outcome.get("ok") else 409
    encoded = json.dumps(outcome, sort_keys=True, default=str).encode("utf-8")
    return Response(
        encoded, status_code=status, media_type="application/json", headers=_SECURITY_HEADERS
    )


async def openapi(request: Request) -> Response:
    _require(request, _ADMIN)
    return _json(request, request.app.openapi())


async def host(request: Request) -> Response:
    _require(request, _READ)
    return _entities(request, "os", extra=True)


async def services(request: Request) -> Response:
    _require(request, _READ)
    return _entities(request, "service")


async def service_one(request: Request, unit: str) -> Response:
    _require(request, _READ)
    return _one_entity(request, "service", unit)


async def containers(request: Request) -> Response:
    _require(request, _READ)
    return _entities(request, "container")


async def container_one(request: Request, container_id: str) -> Response:
    _require(request, _READ)
    return _one_entity(request, "container", container_id)


async def schedules(request: Request) -> Response:
    _require(request, _READ)
    return _entities(request, "schedule")


async def ports(request: Request) -> Response:
    _require(request, _READ)
    return _entities(request, "port")


async def users(request: Request) -> Response:
    _require(request, _READ)
    return _entities(request, "user")


async def ssh_keys(request: Request) -> Response:
    _require(request, _READ)
    return _entities(request, "ssh_key")


async def projects(request: Request) -> Response:
    _require(request, _READ)
    state = _state(request)
    scan_id = _scan(state)
    rows = state.store.projects(scan_id)
    return _page(request, rows, "key")


async def project_one(request: Request, project_id: str) -> Response:
    _require(request, _READ)
    state = _state(request)
    scan_id = _scan(state)
    row = state.store.project(scan_id, project_id)
    if row is None:
        raise Problem(404, "That project is not in the latest scan.", "project.missing")
    facts = state.store.facts(scan_id, f"project:{project_id}")
    return _json(request, {"scan_id": scan_id, "project": row, "facts": facts})


async def project_docs(request: Request, project_id: str) -> Response:
    _require(request, _READ)
    state = _state(request)
    scan_id = _scan(state)
    return _json(
        request, {"scan_id": scan_id, "docs": state.store.project_docs(scan_id, project_id)}
    )


async def evidence(request: Request, fact_id: int) -> Response:
    _require(request, _READ)
    rows = _state(request).store.evidence_for_fact(fact_id)
    if not rows:
        raise Problem(404, "That fact has no evidence.", "fact.missing")
    return _json(request, {"fact_id": fact_id, "evidence": rows})


async def search(request: Request) -> Response:
    _require(request, _READ)
    state = _state(request)
    scan_id = _scan(state)
    query = request.query_params.get("q", "")
    return _json(request, {"scan_id": scan_id, "hits": state.store.search_docs(scan_id, query)})


async def changes(request: Request) -> Response:
    _require(request, _READ)
    state = _state(request)
    scan_id = _scan(state)
    return _json(request, {"scan_id": scan_id, "changes": state.store.changes(scan_id)})


async def edges(request: Request) -> Response:
    _require(request, _READ)
    state = _state(request)
    scan_id = _scan(state)
    return _json(request, {"scan_id": scan_id, "edges": state.store.edges(scan_id)})


async def scans(request: Request) -> Response:
    _require(request, _ADMIN)
    return _json(request, {"scans": _state(request).store.list_scans()})


async def start_scan(request: Request) -> Response:
    actor = _require(request, _ADMIN)
    _csrf(request, actor)
    state = _state(request)
    helper = state.settings.helper_socket or None
    if helper and not Path(helper).exists():
        helper = None
    view = open_view(state.settings.root, helper_socket=helper)
    scan_id = run_scan(view, state.store, "manual", lower_priority=True, helper_socket=helper)
    log_event(_LOG, logging.INFO, "scan.finished", scan_id=scan_id, username=actor.username)
    return _json(request, {"scan_id": scan_id})


async def metric_series(request: Request) -> Response:
    _require(request, _READ)
    return _json(request, {"series": list_series(_state(request).store.conn)})


async def metrics(request: Request) -> Response:
    _require(request, _READ)
    series = request.query_params.get("series", "")
    try:
        start = int(request.query_params.get("start", "0"))
        end = int(request.query_params.get("end", "0"))
        step = int(request.query_params.get("step", "1"))
        points = query_series(_state(request).store.conn, series, start, end, step)
    except ValueError as exc:
        raise Problem(400, "The metrics query is not valid.", "metrics.query") from exc
    return _json(request, {"series": series, "points": points})


async def logs(request: Request) -> Response:
    _require(request, _READ)
    source = request.query_params.get("source", "")
    try:
        limit = int(request.query_params.get("limit", "200"))
        payload = read_log(
            _state(request).settings.root,
            source,
            limit,
            query=request.query_params.get("q", ""),
            pattern=request.query_params.get("pattern", ""),
        )
    except (LogError, ValueError) as exc:
        message = exc.message if isinstance(exc, LogError) else "The log query is not valid."
        raise Problem(400, message, "logs.source") from exc
    return _json(request, payload)


async def export(request: Request) -> Response:
    _require(request, _READ)
    state = _state(request)
    scan_id = _scan(state)
    fmt = request.query_params.get("format", "md")
    report = build_report(state.store, scan_id)
    writers = {"md": render_markdown, "json": render_json, "html": render_html}
    if fmt not in writers:
        raise Problem(400, "The export format is md, json, or html.", "export.format")
    media = {"md": "text/markdown", "json": "application/json", "html": "text/html"}[fmt]
    return Response(writers[fmt](report), media_type=media)


async def stream(websocket: WebSocket) -> None:
    """Push one subscribed channel. The socket closes when the peer goes away."""
    state: AppState = websocket.app.state.atlas
    host_name = websocket.headers.get("host", "").split(":", 1)[0]
    origin = websocket.headers.get("origin", "")
    if host_name not in state.settings.allowed_hosts or (
        origin and not _origin_ok(origin, websocket.headers.get("host", ""))
    ):
        await websocket.close(code=1008)
        return
    raw = websocket.cookies.get(_SESSION_COOKIE, "")
    actor = actor_from_session(
        state.store.conn,
        raw,
        now=state.clock(),
        idle_seconds=state.settings.session_idle_seconds,
        touch=False,
    )
    if actor is None or actor.role not in _READ:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    try:
        message = await websocket.receive_json()
    except Exception:
        await websocket.close(code=1003)
        return
    channel = str(message.get("subscribe") or "") if isinstance(message, dict) else ""
    if channel == "metrics.live":
        import asyncio

        try:
            while True:
                sample = default_sampler().sample()
                await websocket.send_json(
                    {
                        "channel": channel,
                        "collected_at": sample.collected_at,
                        "loadavg": sample.loadavg,
                        "memory_available": None
                        if sample.memory is None
                        else sample.memory.available_bytes,
                        "cpu_idle": None if sample.cpu is None else sample.cpu.idle,
                        "units": [
                            {
                                "name": unit.name,
                                "memory_bytes": unit.memory_bytes,
                                "cpu_usage_usec": unit.cpu_usage_usec,
                            }
                            for unit in sample.units[:8]
                        ],
                        "containers": [
                            {
                                "name": item.name,
                                "memory_bytes": item.memory_bytes,
                                "cpu_usage_usec": item.cpu_usage_usec,
                            }
                            for item in sample.containers[:8]
                        ],
                    }
                )
                await asyncio.sleep(1)
        except Exception:
            return
    elif channel == "logs.follow":
        import asyncio

        source = str(message.get("source") or "")
        try:
            while True:
                try:
                    payload = read_log(state.settings.root, source, 100)
                except LogError as exc:
                    payload = {"status": "unavailable", "reason": exc.message, "lines": []}
                await websocket.send_json({"channel": channel, "payload": payload})
                await asyncio.sleep(2)
        except Exception:
            return
    elif channel == "events":
        await websocket.send_json({"channel": channel, "events": []})
    else:
        await websocket.send_json({"channel": channel, "error": "unknown channel"})


def _state(request: Request) -> AppState:
    state = request.app.state.atlas
    if not isinstance(state, AppState):
        raise Problem(500, "The API is not configured.", "server.state")
    return state


def _require(request: Request, roles: frozenset[str]) -> Actor:
    actor = _authenticate(request, _state(request))
    if actor.role not in roles:
        raise Problem(403, "This action is outside the current role.", "auth.forbidden")
    return actor


def _authenticate(request: Request, state: AppState) -> Actor:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        actor = actor_from_api_token(state.store.conn, header[7:].strip(), now=state.clock())
        if actor is None:
            raise Problem(401, "Credentials were rejected.", "auth.rejected")
        return actor
    raw = request.cookies.get(_SESSION_COOKIE, "")
    if not raw:
        raise Problem(401, "Credentials were rejected.", "auth.rejected")
    actor = actor_from_session(
        state.store.conn,
        raw,
        now=state.clock(),
        idle_seconds=state.settings.session_idle_seconds,
        touch=True,
    )
    if actor is None:
        raise Problem(401, "Credentials were rejected.", "auth.rejected")
    return actor


def _csrf(request: Request, actor: Actor) -> None:
    if actor.via != "session":
        return
    header = request.headers.get("x-csrf-token", "")
    cookie = request.cookies.get(_CSRF_COOKIE, "")
    if not header or header != cookie or header != (actor.csrf_token or ""):
        raise Problem(403, "The CSRF token does not match this session.", "auth.csrf")


def _entities(request: Request, kind: str, extra: bool = False) -> Response:
    state = _state(request)
    scan_id = _scan(state)
    rows = state.store.entities(scan_id, kind)
    if extra:
        return _json(
            request,
            {
                "scan_id": scan_id,
                "entities": rows,
                "sources": state.store.sources(scan_id),
            },
        )
    return _page(request, rows, "key")


def _one_entity(request: Request, kind: str, key: str) -> Response:
    state = _state(request)
    scan_id = _scan(state)
    rows = [row for row in state.store.entities(scan_id, kind) if row["key"] == key]
    if not rows:
        raise Problem(404, "That record is not in the latest scan.", "record.missing")
    facts = state.store.facts(scan_id, f"{kind}:{key}")
    return _json(request, {"scan_id": scan_id, "entity": rows[0], "facts": facts})


def _scan(state: AppState) -> int:
    scan_id = state.store.latest_scan_id()
    if scan_id is None:
        raise Problem(404, "There is no completed scan yet.", "scan.missing")
    return scan_id


def _page(request: Request, rows: list[dict[str, Any]], key: str) -> Response:
    try:
        limit = min(int(request.query_params.get("limit", "50")), 200)
    except ValueError as exc:
        raise Problem(400, "The page size is not a number.", "http.limit") from exc
    cursor = request.query_params.get("cursor", "")
    start = 0
    if cursor:
        for index, row in enumerate(rows):
            if str(row.get(key)) == cursor:
                start = index + 1
                break
    chunk = rows[start : start + limit]
    nxt = str(chunk[-1][key]) if chunk and start + limit < len(rows) else None
    return _json(request, {"items": chunk, "next": nxt})


def _json(request: Request, payload: object) -> Response:
    body = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    tag = '"' + hashlib.sha256(body).hexdigest()[:32] + '"'
    headers = {"etag": tag, **_SECURITY_HEADERS}
    if request.headers.get("if-none-match") == tag:
        return Response(status_code=304, headers=headers)
    return Response(body, media_type="application/json", headers=headers)


def _with_session(request: Request, actor: Actor, payload: dict[str, str]) -> Response:
    response = _json(request, payload)
    state = _state(request)
    secure = state.settings.tls
    if actor.raw_session:
        response.set_cookie(
            _SESSION_COOKIE,
            actor.raw_session,
            httponly=True,
            secure=secure,
            samesite="strict",
            path="/",
        )
    if actor.csrf_token:
        response.set_cookie(
            _CSRF_COOKIE,
            actor.csrf_token,
            httponly=False,
            secure=secure,
            samesite="strict",
            path="/",
        )
    return response


async def _body(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception as exc:
        raise Problem(400, "The request body is not JSON.", "http.body") from exc
    if not isinstance(payload, dict):
        raise Problem(400, "The request body is not an object.", "http.body")
    return payload


def _access(exc: AccessError) -> Problem:
    status = 401 if exc.code == "auth.rejected" else 400
    return Problem(status, exc.message, exc.code, exc.message)


def _origin_ok(origin: str, host: str) -> bool:
    if not host:
        return False
    return origin == f"https://{host}" or origin == f"http://{host}"


_PANEL = Path(__file__).resolve().parents[3] / "frontend" / "dist"


def _mount_panel(app: FastAPI) -> None:
    """Serve the built panel from the same origin as the API when it has been built."""
    if (_PANEL / "index.html").is_file():
        app.mount("/", StaticFiles(directory=_PANEL, html=True), name="panel")
