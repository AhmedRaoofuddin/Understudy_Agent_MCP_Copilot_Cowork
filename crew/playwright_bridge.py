"""A live bridge from Understudy to the Playwright MCP server.

The capture loop in this package is written against a small synchronous client,
but the Playwright MCP speaks the asynchronous MCP protocol over stdio. This
bridge launches that server as a subprocess, holds one session open on a
background event loop, and exposes a plain synchronous call_tool the Watcher and
Hands can use. Connecting it is the wiring step the README describes: start the
bridge, take its client, and the same capture loop now drives a real browser.

The session is created through a factory so the bridge can be unit tested with a
fake session, without a subprocess or a browser. The default factory builds the
real stdio session and needs the mcp package and Node on the host.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable, Dict, List, Optional


def extract_text(result: Any) -> str:
    """Join the text of every text block in an MCP tool result."""
    parts: List[str] = []
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if text is not None:
            parts.append(text)
    return "".join(parts)


class PlaywrightBridge:
    """Run the Playwright MCP on a background loop and call it synchronously."""

    def __init__(
        self,
        command: str = "npx",
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        session_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self._command = command
        self._args = list(args) if args is not None else ["@playwright/mcp@latest"]
        self._env = env
        self._session_factory = session_factory
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._session: Any = None
        self._stop: Optional[asyncio.Event] = None
        self._ready = threading.Event()
        self._error: Optional[BaseException] = None

    def _default_session_factory(self):
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def factory():
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            params = StdioServerParameters(command=self._command, args=self._args, env=self._env)
            async with stdio_client(params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    yield session

        return factory()

    async def _main(self) -> None:
        self._stop = asyncio.Event()
        make = self._session_factory or self._default_session_factory
        try:
            async with make() as session:
                self._session = session
                self._ready.set()
                await self._stop.wait()
        except BaseException as error:  # surfaced to start()
            self._error = error
            self._ready.set()

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main())
        finally:
            self._loop.close()

    def start(self) -> "PlaywrightBridge":
        self._thread = threading.Thread(target=self._run, name="playwright-bridge", daemon=True)
        self._thread.start()
        self._ready.wait()
        if self._error is not None:
            raise self._error
        return self

    def call_tool(self, name: str, arguments: Optional[Dict[str, object]] = None) -> str:
        if self._session is None or self._loop is None:
            raise RuntimeError("the bridge is not started, call start first")
        future = asyncio.run_coroutine_threadsafe(
            self._session.call_tool(name, arguments or {}), self._loop
        )
        return extract_text(future.result())

    def client(self):
        """Return a capture client wired to the live Playwright MCP."""
        from crew.capture import PlaywrightMcpClient

        return PlaywrightMcpClient(self.call_tool)

    def close(self) -> None:
        if self._loop is not None and self._stop is not None:
            self._loop.call_soon_threadsafe(self._stop.set)
        if self._thread is not None:
            self._thread.join(timeout=5)

    def __enter__(self) -> "PlaywrightBridge":
        return self.start()

    def __exit__(self, *_: object) -> None:
        self.close()
