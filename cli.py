"""Understudy command line interface.

Subcommands:

  prove       run the deterministic core proof harness
  demo        run the end to end Understudy Loop demo
  serve-mcp   start the MCP server for Copilot, Cowork, and other MCP clients
  serve-api   start the REST surface and the trust dial dashboard
  install     write the MCP client config, with model tiers chosen by usage

The install command is the single step that wires Understudy into a Copilot or
Cowork style client. It writes a ready config and prints it, choosing which
model runs each risk tier based on how heavily you intend to use it, and it
registers the Playwright MCP server alongside the gate so browser tools are there
from the start. Pass --no-playwright to write only the Understudy server.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List, Optional

PLAYWRIGHT_PACKAGE = "@playwright/mcp@latest"


def playwright_server_block() -> Dict[str, object]:
    """The MCP server entry for the official Playwright MCP.

    The host launches it with npx, which fetches the package on first run, so the
    browser tools land alongside the gate without a separate install step.
    """
    return {"command": "npx", "args": [PLAYWRIGHT_PACKAGE]}


USAGE_PRESETS: Dict[str, Dict[str, str]] = {
    "light": {
        "UNDERSTUDY_FAST_MODEL": "claude-haiku-4-5",
        "UNDERSTUDY_STANDARD_MODEL": "claude-haiku-4-5",
        "UNDERSTUDY_DEEP_MODEL": "claude-sonnet-4-6",
    },
    "balanced": {
        "UNDERSTUDY_FAST_MODEL": "claude-haiku-4-5",
        "UNDERSTUDY_STANDARD_MODEL": "claude-sonnet-4-6",
        "UNDERSTUDY_DEEP_MODEL": "claude-opus-4-8",
    },
    "heavy": {
        "UNDERSTUDY_FAST_MODEL": "claude-sonnet-4-6",
        "UNDERSTUDY_STANDARD_MODEL": "claude-opus-4-8",
        "UNDERSTUDY_DEEP_MODEL": "claude-opus-4-8",
    },
}


def cmd_prove(_: argparse.Namespace) -> int:
    from simulations import harness

    return harness.main()


def cmd_demo(_: argparse.Namespace) -> int:
    from simulations import crew_demo

    return crew_demo.main()


def cmd_serve_mcp(args: argparse.Namespace) -> int:
    os.environ.setdefault("UNDERSTUDY_EVENT_LOG", args.event_log)
    from mcp_server import server

    server.main()
    return 0


def cmd_serve_api(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        print("uvicorn is required for serve-api. Install it with: pip install uvicorn")
        return 1
    os.environ.setdefault("UNDERSTUDY_EVENT_LOG", args.event_log)
    uvicorn.run("api.app:app", host=args.host, port=args.port)
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    models = dict(USAGE_PRESETS[args.usage])
    if args.fast_model:
        models["UNDERSTUDY_FAST_MODEL"] = args.fast_model
    if args.standard_model:
        models["UNDERSTUDY_STANDARD_MODEL"] = args.standard_model
    if args.deep_model:
        models["UNDERSTUDY_DEEP_MODEL"] = args.deep_model

    env = {"UNDERSTUDY_EVENT_LOG": args.event_log}
    env.update(models)

    servers = {
        "understudy": {
            "command": sys.executable,
            "args": ["-m", "mcp_server.server"],
            "env": env,
        }
    }
    if args.with_playwright:
        servers["playwright"] = playwright_server_block()

    config = {"mcpServers": servers}
    text = json.dumps(config, indent=2)
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(text + "\n")

    print(text)
    print("")
    print("Wrote " + args.out)
    print("Add these servers to your Copilot, Cowork, or other MCP client config.")
    print("Usage preset: " + args.usage + " (fast, standard, and deep tiers set above).")
    if args.with_playwright:
        print("Playwright MCP is registered too, so browser tools load next to the gate.")
        print("The host fetches it with npx on first run. Run 'npx playwright install' once for browsers.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="understudy", description="Understudy command line interface")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("prove", help="run the deterministic core proof harness").set_defaults(func=cmd_prove)
    sub.add_parser("demo", help="run the end to end Understudy Loop demo").set_defaults(func=cmd_demo)

    serve_mcp = sub.add_parser("serve-mcp", help="start the MCP server")
    serve_mcp.add_argument("--event-log", default="understudy_events.jsonl")
    serve_mcp.set_defaults(func=cmd_serve_mcp)

    serve_api = sub.add_parser("serve-api", help="start the REST surface and dashboard")
    serve_api.add_argument("--host", default="127.0.0.1")
    serve_api.add_argument("--port", type=int, default=8000)
    serve_api.add_argument("--event-log", default="understudy_events.jsonl")
    serve_api.set_defaults(func=cmd_serve_api)

    install = sub.add_parser("install", help="write the MCP client config")
    install.add_argument("--usage", choices=list(USAGE_PRESETS.keys()), default="balanced")
    install.add_argument("--event-log", default="understudy_events.jsonl")
    install.add_argument("--fast-model", default="")
    install.add_argument("--standard-model", default="")
    install.add_argument("--deep-model", default="")
    install.add_argument("--out", default="understudy.mcp.json")
    install.add_argument(
        "--with-playwright",
        dest="with_playwright",
        action="store_true",
        default=True,
        help="also register the Playwright MCP server (on by default)",
    )
    install.add_argument(
        "--no-playwright",
        dest="with_playwright",
        action="store_false",
        help="write only the Understudy server",
    )
    install.set_defaults(func=cmd_install)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
