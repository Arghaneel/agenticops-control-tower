"""ASGI request-size enforcement that runs before FastAPI parses a body."""

from __future__ import annotations

from typing import Any

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class _BodyTooLargeError(Exception):
    pass


class BodySizeLimit:
    """Require Content-Length and count received bytes for selected POST paths."""

    def __init__(self, app: ASGIApp, *, paths: frozenset[str], max_bytes: int) -> None:
        self.app = app
        self.paths = paths
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"] not in self.paths:
            await self.app(scope, receive, send)
            return
        length = dict(scope["headers"]).get(b"content-length")
        if length is None:
            await self._reject(scope, receive, send, 411, "Content-Length is required")
            return
        if not length.isdigit() or int(length) > self.max_bytes:
            await self._reject(scope, receive, send, 413, self._limit_message)
            return
        received = 0
        started = False

        async def counted_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _BodyTooLargeError
            return message

        async def tracked_send(message: Message) -> None:
            nonlocal started
            started = started or message["type"] == "http.response.start"
            await send(message)

        try:
            await self.app(scope, counted_receive, tracked_send)
        except _BodyTooLargeError:
            if started:
                raise
            await self._reject(scope, receive, send, 413, self._limit_message)

    @property
    def _limit_message(self) -> str:
        return f"Request bodies are limited to {self.max_bytes} bytes"

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send, status: int, detail: Any) -> None:
        await JSONResponse({"detail": detail}, status_code=status)(scope, receive, send)
