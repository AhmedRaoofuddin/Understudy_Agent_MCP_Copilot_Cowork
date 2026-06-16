import os
import sys
import unittest
from contextlib import asynccontextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crew.playwright_bridge import PlaywrightBridge, extract_text


class _Block:
    def __init__(self, text):
        self.text = text


class _Result:
    def __init__(self, text):
        self.content = [_Block(text)]


class _FakeSession:
    """Stands in for a live Playwright MCP session, no subprocess or browser."""

    def __init__(self):
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return _Result(name + " " + str(arguments))


class PlaywrightBridgeTests(unittest.TestCase):
    def test_extract_text_joins_text_blocks(self):
        self.assertEqual(extract_text(_Result("page state")), "page state")

    def test_bridge_calls_a_tool_synchronously(self):
        session = _FakeSession()

        @asynccontextmanager
        async def factory():
            yield session

        bridge = PlaywrightBridge(session_factory=factory).start()
        try:
            out = bridge.call_tool("browser_snapshot", {})
            self.assertEqual(out, "browser_snapshot {}")
        finally:
            bridge.close()

    def test_client_routes_capture_actions_to_the_session(self):
        session = _FakeSession()

        @asynccontextmanager
        async def factory():
            yield session

        bridge = PlaywrightBridge(session_factory=factory).start()
        try:
            client = bridge.client()
            client.snapshot()
            client.act("click", "Submit")
        finally:
            bridge.close()

        self.assertEqual(session.calls[0][0], "browser_snapshot")
        self.assertEqual(session.calls[1][0], "browser_click")
        self.assertEqual(session.calls[1][1], {"element": "Submit"})


if __name__ == "__main__":
    unittest.main()
