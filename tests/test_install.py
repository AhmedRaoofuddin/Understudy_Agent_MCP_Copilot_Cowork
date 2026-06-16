import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cli


def run_install(extra):
    handle, path = tempfile.mkstemp(suffix=".json")
    os.close(handle)
    try:
        cli.main(["install", "--out", path] + extra)
        with open(path, "r", encoding="utf-8") as out:
            return json.load(out)
    finally:
        os.remove(path)


class InstallTests(unittest.TestCase):
    def test_registers_understudy_and_playwright_by_default(self):
        config = run_install(["--usage", "balanced"])
        servers = config["mcpServers"]
        self.assertIn("understudy", servers)
        self.assertIn("playwright", servers)

    def test_playwright_block_uses_npx_and_the_official_package(self):
        config = run_install([])
        playwright = config["mcpServers"]["playwright"]
        self.assertEqual(playwright["command"], "npx")
        self.assertIn(cli.PLAYWRIGHT_PACKAGE, playwright["args"])

    def test_understudy_block_carries_the_model_tiers(self):
        config = run_install(["--usage", "balanced"])
        env = config["mcpServers"]["understudy"]["env"]
        self.assertEqual(env["UNDERSTUDY_FAST_MODEL"], "claude-haiku-4-5")
        self.assertEqual(env["UNDERSTUDY_STANDARD_MODEL"], "claude-sonnet-4-6")
        self.assertEqual(env["UNDERSTUDY_DEEP_MODEL"], "claude-opus-4-8")

    def test_no_playwright_writes_only_the_gate(self):
        config = run_install(["--no-playwright"])
        servers = config["mcpServers"]
        self.assertIn("understudy", servers)
        self.assertNotIn("playwright", servers)


if __name__ == "__main__":
    unittest.main()
