"""Live capture for the Watcher.

The Watcher records how a person does a task by driving a browser client and
noting each step. With the offline client it runs in tests. With
PlaywrightMcpClient it records a real browser session through the Playwright MCP,
which the Scribe then turns into a playbook. Capture itself is deterministic: it
reads a snapshot, performs each action, and writes down what it did.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Protocol, Tuple


class BrowserClient(Protocol):
    def snapshot(self) -> str: ...
    def act(self, action: str, target: str) -> str: ...


@dataclass
class OfflineBrowserClient:
    """A scripted stand in for the Playwright MCP, for tests and local runs."""

    step_count: int = 0
    seen: List[str] = field(default_factory=list)

    def snapshot(self) -> str:
        return "screen state " + str(self.step_count)

    def act(self, action: str, target: str) -> str:
        self.step_count += 1
        self.seen.append(action + ":" + target)
        return "applied " + action + " on " + target


class PlaywrightMcpClient:
    """Adapter over a Playwright MCP tool caller.

    Pass a function that invokes an MCP tool by name with an argument dict, for
    example a thin wrapper around your MCP client. The capture loop calls
    browser_snapshot to read state and browser_click or browser_type to act.
    """

    def __init__(self, call_tool: Callable[[str, Dict[str, object]], str]) -> None:
        self._call_tool = call_tool

    def snapshot(self) -> str:
        return self._call_tool("browser_snapshot", {})

    def act(self, action: str, target: str) -> str:
        return self._call_tool("browser_" + action, {"element": target})


class BrowserCapture:
    def __init__(self, client: BrowserClient) -> None:
        self.client = client

    def record(self, actions: List[Tuple[str, str]]) -> List[str]:
        steps: List[str] = []
        self.client.snapshot()
        for action, target in actions:
            self.client.act(action, target)
            steps.append(action + " " + target)
        return steps
