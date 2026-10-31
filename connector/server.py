#!/usr/bin/env python3
"""Draw Me a Fact — MCP connector server.

Exposes the studio as Model Context Protocol tools, so an MCP-capable client
(Arena, Claude Desktop, ChatGPT connectors, Cursor, n8n, ...) can drive the
whole episode pipeline by calling tools instead of shell commands.

Transports:
    stdio                python -m connector.server                (local clients)
    streamable-http      python -m connector.server --http --port 8765
    sse (legacy)         python -m connector.server --sse --port 8765

Point a client at http://<host>:8765/mcp for streamable HTTP. The manifest at
http://<host>:8765/.well-known/ai-connector.json describes the same server for
registries and marketplaces that expect a manifest before they will index it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from connector import tools  # noqa: E402

INSTRUCTIONS = """You are driving the Draw Me a Fact production studio (@drawmeafact).

The channel makes one 32-38 second vertical film per episode, hand-drawn on
paper, narrating one number that only grows. Five sentences, five scenes.

How to use these tools:
- Start with describe_studio() and list_episodes() to see the slate.
- get_episode("<number-or-slug>") returns the exact script, scene plan and the
  sourced accuracy table. Show the accuracy table when the operator asks what
  the film claims.
- plan_script(topic) drafts a new script WITHOUT rendering. Validate before
  spending a render.
- produce_episode(...) renders the film, muxes audio, writes the SRT and upload
  pack, and runs the QA gate. It refuses to report success if QA fails. It never
  uploads unless publish_mode is explicitly public_now / unlisted / private /
  schedule_target.
- run_qa() re-checks the last film; list_assets() shows what is on disk.

Never claim a film exists unless produce_episode returned a path and
qa_passed: true.
"""

mcp = MCPServer(
    name="draw-me-a-fact",
    title="Draw Me a Fact Studio",
    description="Autonomous production studio for the @drawmeafact YouTube Shorts channel.",
    instructions=INSTRUCTIONS,
    version="1.1.0",
)

READ = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)
PUBLISH = ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=True)


@mcp.tool(annotations=READ)
def describe_studio() -> dict:
    """What this connector is, and which integrations are configured right now."""
    return tools.describe_studio()


@mcp.tool(annotations=READ)
def list_episodes(include_shipped: bool = True) -> dict:
    """List the pre-verified episode slate, flagged with what has already shipped."""
    return tools.list_episodes(include_shipped=include_shipped)


@mcp.tool(annotations=READ)
def get_episode(identifier: str) -> dict:
    """Full package for one slate episode (number or slug): script, scenes, sources, word count."""
    return tools.get_episode(identifier)


@mcp.tool(annotations=READ)
def plan_script(topic: str, series: str | None = None) -> dict:
    """Draft a five-sentence script for a topic and check it against the §3 contract. No render."""
    return tools.plan_script(topic, series)


@mcp.tool(annotations=WRITE)
def produce_episode(
    episode: str | None = None,
    topic: str | None = None,
    publish_mode: str = "dry_run",
    render: bool = True,
) -> dict:
    """Produce one episode end to end: voice, score, frames, mux, SRT, upload pack, QA gate.

    Defaults to dry_run: render and QA only, never upload. A full render takes a
    minute or two of CPU. Pass render=False for a plan-only run.
    """
    return tools.produce_episode(episode=episode, topic=topic, publish_mode=publish_mode, render=render)


@mcp.tool(annotations=READ)
def run_qa(video_path: str | None = None) -> dict:
    """Re-run the §9 QA gate on the latest film (or a path you pass)."""
    return tools.run_qa(video_path)


@mcp.tool(annotations=READ)
def list_assets() -> dict:
    """Everything on disk: MP4, SRT, youtube_pack.md, contact sheet, voice WAVs, timing JSON."""
    return tools.list_assets()


@mcp.tool(annotations=READ)
def score_info() -> dict:
    """The locked audio chain, sample rate and timing constants — for explaining how it sounds."""
    return tools.score_info()


def _security() -> TransportSecuritySettings:
    # The sandbox preview proxies the app from a host the server cannot know in
    # advance, so DNS-rebinding protection is disabled for the hosted transport.
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
        allowed_hosts=["*"],
        allowed_origins=["*"],
    )


def create_app(host: str = "0.0.0.0"):
    """Starlette app: MCP at /mcp, plus the registry manifest and a health probe."""
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    app = mcp.streamable_http_app(host=host, transport_security=_security())
    manifest = json.loads((Path(__file__).parent / "manifest.json").read_text(encoding="utf-8"))

    async def well_known(_: Request) -> JSONResponse:
        return JSONResponse(manifest)

    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "server": "draw-me-a-fact", "version": "1.1.0"})

    async def index(_: Request) -> JSONResponse:
        return JSONResponse({
            "name": manifest["name"],
            "mcp_endpoint": "/mcp",
            "manifest": "/.well-known/ai-connector.json",
            "transport": "streamable-http",
            "tools": [t["name"] for t in manifest["tools"]],
        })

    app.add_route("/.well-known/ai-connector.json", well_known)
    app.add_route("/healthz", health)
    app.add_route("/", index)
    return app


def main(argv: list[str] | None = None) -> int:
    import uvicorn

    ap = argparse.ArgumentParser(description="Draw Me a Fact MCP connector")
    ap.add_argument("--http", action="store_true", help="serve streamable HTTP instead of stdio")
    ap.add_argument("--sse", action="store_true", help="serve the legacy SSE transport")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--manifest", action="store_true", help="print the connector manifest and exit")
    args = ap.parse_args(argv)

    tools.ensure()

    if args.manifest:
        print((Path(__file__).parent / "manifest.json").read_text(encoding="utf-8"))
        return 0
    if args.sse:
        uvicorn.run(mcp.sse_app(transport_security=_security()), host=args.host, port=args.port, log_level="info")
        return 0
    if args.http:
        uvicorn.run(create_app(args.host), host=args.host, port=args.port, log_level="info")
        return 0
    mcp.run("stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
