"""Replace secret-shaped text before it is stored, logged, or rendered."""

from __future__ import annotations

import re

EXCERPT_LIMIT = 200

_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|"
    r"authorization|client[_-]?secret|private[_-]?key)\b"
    r"(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|\S+)"
)
_BEARER = re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9\-._~+/]+=*")
_PRIVATE_KEY = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL,
)
_URL_USERINFO = re.compile(
    r"(?i)\b((?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis|rediss|amqp|amqps|"
    r"https?)://)([^:/\s]+):([^@/\s]+)@"
)
_AUTH_HEADER = re.compile(r"(?i)(authorization\s*:\s*)(\S+)")
_GITHUB_TOKEN = re.compile(r"\b(ghp_|github_pat_|gho_|ghu_|ghs_|glpat-)[A-Za-z0-9_]+")


def mask_secrets(text: str) -> str:
    """Return ``text`` with secret-shaped values replaced by ``***``."""
    masked = _PRIVATE_KEY.sub("***", text)
    masked = _URL_USERINFO.sub(r"\1\2:***@", masked)
    masked = _BEARER.sub(r"\1 ***", masked)
    masked = _AUTH_HEADER.sub(r"\1***", masked)
    masked = _ASSIGNMENT.sub(r"\1\2***", masked)
    masked = _GITHUB_TOKEN.sub("***", masked)
    return masked


def excerpt(text: str, limit: int = EXCERPT_LIMIT) -> str:
    """Mask secrets, collapse whitespace, and clip text to the evidence limit."""
    masked = " ".join(mask_secrets(text).split())
    if len(masked) <= limit:
        return masked
    return masked[: limit - 1] + "…"


def env_key_names(text: str) -> list[str]:
    """Return environment variable names. Values are discarded."""
    names: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        name = line.split("=", 1)[0].strip()
        if name and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            names.append(name)
    return names
