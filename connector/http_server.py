#!/usr/bin/env python3
"""Hosted façade: the connector manifest, a JSON tool endpoint and MCP in one app.

Run it and hand the client base URL to whatever is registering the connector:

    python -m connector.http_server --port 8765

    GET  /                                   service summary + tool list
    GET  /.well-known/ai-connector.json      the registration manifest
    GET  /healthz                            liveness probe
    GET  /tools                              JSON tool index with JSON-Schema params
    POST /tools/{name}                       invoke a tool with a JSON body
    POST /mcp                                MCP streamable HTTP

`/tools/*` exists so registries and non-MCP clients (custom GPT actions, n8n,
curl) can exercise the same functions as MCP clients. No credentials live in
the client; publishing reads server-side environment secrets.
"""

from __future__ import annotations

import argparse
import inspect
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse

from connector import tools as T
from connector.server import create_app as mcp_app

MANIFEST = json.loads((Path(__file__).parent / "manifest.json").read_text(encoding="utf-8"))

JSON_TYPES = {
    "str": "string", "int": "integer", "float": "number", "bool": "boolean", "dict": "object", "list": "array",
}


def _schema(fn) -> dict:
    sig = inspect.signature(fn)
    props, required = {}, []
    for name, p in sig.parameters.items():
        ann = p.annotation
        py = ann.__name__ if isinstance(ann, type) else str(ann).replace(" | None", "")
        prop: dict = {"type": JSON_TYPES.get(py, "string")}
        if p.default is not inspect.Parameter.empty and p.default is not None:
            prop["default"] = p.default
        else:
            required.append(name)
        props[name] = prop
    return {"type": "object", "properties": props, "required": required}


def tool_index() -> dict:
    return {
        "server": {"name": MANIFEST["name"], "version": MANIFEST["version"], "transport": MANIFEST["transport"]},
        "tools": [
            {"name": n, "description": (fn.__doc__ or "").strip().splitlines()[0], "input_schema": _schema(fn)}
            for n, fn in T.TOOLS.items()
        ],
    }


def create_app():
    base = mcp_app("0.0.0.0")
    # keep only the MCP transport route; this app owns the rest of the surface.
    # The base app's lifespan must come along, or the MCP session manager is
    # never started and every /mcp request dies with "Task group is not initialized".
    mcp_routes = [r for r in base.routes if getattr(r, "path", "") == "/mcp"]
    app = Starlette(routes=[], lifespan=base.router.lifespan_context)

    async def index(_: Request) -> JSONResponse:
        return JSONResponse({
            "name": MANIFEST["name"],
            "version": MANIFEST["version"],
            "description": MANIFEST["description"],
            "manifest": "/.well-known/ai-connector.json",
            "tools": "/tools",
            "mcp": "/mcp",
            "health": "/healthz",
        })

    async def manifest(_: Request) -> JSONResponse:
        return JSONResponse(MANIFEST)

    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "name": MANIFEST["name"], "version": MANIFEST["version"]})

    async def tools_index(_: Request) -> JSONResponse:
        return JSONResponse(tool_index())

    async def call_tool(request: Request) -> JSONResponse:
        name = request.path_params["name"]
        fn = T.TOOLS.get(name)
        if fn is None:
            return JSONResponse({"error": f"unknown tool {name!r}", "available": list(T.TOOLS)}, status_code=404)
        try:
            body = await request.body()
            kwargs = json.loads(body) if body else {}
            if not isinstance(kwargs, dict):
                return JSONResponse({"error": "body must be a JSON object"}, status_code=400)
            sig = inspect.signature(fn)
            kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
            result = fn(**kwargs)
            return JSONResponse({"ok": True, "tool": name, "result": result})
        except ValueError as exc:
            return JSONResponse({"ok": False, "tool": name, "error": str(exc)}, status_code=400)
        except Exception as exc:  # pragma: no cover
            return JSONResponse({"ok": False, "tool": name, "error": f"{type(exc).__name__}: {exc}"}, status_code=500)

    app.router.routes.extend(mcp_routes)
    from starlette.routing import Route

    app.router.routes.extend([
        Route("/", index),
        Route("/.well-known/ai-connector.json", manifest),
        Route("/healthz", health),
        Route("/tools", tools_index),
        Route("/tools/{name}", call_tool, methods=["POST"]),
    ])
    return app


def main(argv: list[str] | None = None) -> int:
    import uvicorn

    ap = argparse.ArgumentParser(description="Draw Me a Fact connector HTTP server")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args(argv)
    T.ensure()
    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
