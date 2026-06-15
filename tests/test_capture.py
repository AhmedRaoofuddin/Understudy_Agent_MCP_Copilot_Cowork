import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crew.capture import BrowserCapture, OfflineBrowserClient, PlaywrightMcpClient


class CaptureTests(unittest.TestCase):
    def test_records_ordered_steps(self):
        capture = BrowserCapture(OfflineBrowserClient())
        steps = capture.record([("click", "Submit"), ("type", "Name")])
        self.assertEqual(steps, ["click Submit", "type Name"])

    def test_playwright_adapter_calls_the_right_tools(self):
        calls = []

        def call_tool(name, args):
            calls.append((name, args))
            return "ok"

        client = PlaywrightMcpClient(call_tool)
        client.snapshot()
        client.act("click", "Submit")

        self.assertEqual(calls[0][0], "browser_snapshot")
        self.assertEqual(calls[1][0], "browser_click")
        self.assertEqual(calls[1][1], {"element": "Submit"})


if __name__ == "__main__":
    unittest.main()
