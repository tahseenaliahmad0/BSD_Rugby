"""Double-submit CSRF protection as a pure ASGI middleware.

State-changing requests under /api must carry a header equal to the CSRF cookie.
Session cookies are SameSite=Lax as well, so this is a second line of defence.
Login is exempt: it accepts JSON only, which cross-site forms cannot send.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, MutableMapping
from http.cookies import SimpleCookie
from typing import Any

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class CSRFMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        cookie_name: str,
        header_name: str,
        protected_prefix: str = "/api/",
        exempt_paths: frozenset[str] = frozenset({"/api/auth/login"}),
    ) -> None:
        self.app = app
        self.cookie_name = cookie_name
        self.header_name = header_name.lower().encode("latin-1")
        self.protected_prefix = protected_prefix
        self.exempt_paths = exempt_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self._needs_check(scope):
            await self.app(scope, receive, send)
            return

        headers: dict[bytes, bytes] = {k.lower(): v for k, v in scope.get("headers", [])}
        header_token = headers.get(self.header_name, b"").decode("latin-1")
        cookie_token = self._cookie_value(headers.get(b"cookie", b"").decode("latin-1"))
        if not header_token or not cookie_token or header_token != cookie_token:
            await self._reject(send)
            return
        await self.app(scope, receive, send)

    def _needs_check(self, scope: Scope) -> bool:
        path: str = scope.get("path", "")
        method: str = scope.get("method", "GET").upper()
        if method not in UNSAFE_METHODS:
            return False
        if not path.startswith(self.protected_prefix):
            return False
        return path not in self.exempt_paths

    def _cookie_value(self, raw: str) -> str:
        if not raw:
            return ""
        jar: SimpleCookie = SimpleCookie()
        try:
            jar.load(raw)
        except Exception:
            return ""
        morsel = jar.get(self.cookie_name)
        return morsel.value if morsel else ""

    async def _reject(self, send: Send) -> None:
        body = json.dumps(
            {"detail": "Your session needs refreshing. Reload the page and try again."}
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
