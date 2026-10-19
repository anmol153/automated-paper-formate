"""ASGI body bounds apply before multipart parsing, including chunked requests."""
from fastapi import HTTPException
from starlette.responses import JSONResponse


class BodyLimitMiddleware:
    def __init__(self, app, limit):
        self.app = app
        self.limit = limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        size = 0
        started = False
        exceeded = False
        replaced = False
        async def limited_receive():
            nonlocal size, exceeded
            message = await receive()
            if message["type"] == "http.request":
                size += len(message.get("body", b""))
                if size > self.limit:
                    exceeded = True
                    raise HTTPException(status_code=413, detail="Request exceeds the configured byte limit")
            return message
        async def tracked_send(message):
            nonlocal started, replaced
            if exceeded:
                if not replaced:
                    replaced = True
                    started = True
                    await JSONResponse(status_code=413, content={"detail": "Request exceeds the configured byte limit"},
                                       headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})(scope, receive, send)
                return
            if message["type"] == "http.response.start":
                started = True
            await send(message)
        try:
            await self.app(scope, limited_receive, tracked_send)
        except HTTPException as exc:
            if started or exc.status_code != 413:
                raise
            await JSONResponse(status_code=413, content={"detail": exc.detail})(scope, receive, send)
