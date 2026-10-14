"""RFC 9457 problem responses."""

from __future__ import annotations

from fastapi.responses import JSONResponse


class Problem(Exception):
    """An expected API failure with a stable code."""

    def __init__(self, status: int, title: str, code: str, detail: str = "") -> None:
        self.status = status
        self.title = title
        self.code = code
        self.detail = detail or title
        super().__init__(detail or title)


def problem_response(problem: Problem) -> JSONResponse:
    """Render a problem document. The body is JSON and the type is the RFC media type."""
    return JSONResponse(
        status_code=problem.status,
        media_type="application/problem+json",
        content={
            "type": "about:blank",
            "title": problem.title,
            "status": problem.status,
            "detail": problem.detail,
            "code": problem.code,
        },
    )
