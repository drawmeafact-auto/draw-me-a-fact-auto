#!/usr/bin/env python3
"""DRAW ME A FACT (@drawmeafact) — production studio CLI.

The film engine lives in the `dmf` package; this file is the operator's handle
on it and the entry point the GitHub workflow calls.

    python draw_me_a_fact.py --publish-mode dry_run
    python draw_me_a_fact.py --publish-mode public_now --topic "why ice floats"
    python draw_me_a_fact.py --episode 11 --publish-mode dry_run
    python draw_me_a_fact.py --list-slate
    python draw_me_a_fact.py --publish-ig-only
    python draw_me_a_fact.py --qa output/latest_episode.mp4

Exit codes: 0 ok · 1 production or QA failure · 2 bad arguments.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dmf import publish, __version__
from dmf.config import OUTPUT_DIR, PUBLISH_MODES, ensure_dirs
from dmf.pipeline import record_shipped, run_episode, _history
from dmf.qa_gate import as_table, run_checks
from dmf.slate import VERIFIED_SLATE, find_episode


def _print_report(report: dict) -> None:
    print(json.dumps(report, indent=2, default=str))


def cmd_produce(args: argparse.Namespace) -> int:
    def progress(stage: str, pct: float) -> None:
        print(f"[{pct * 100:5.1f}%] {stage}", file=sys.stderr)

    report = run_episode(
        topic=args.topic or None,
        episode=args.episode,
        publish_mode=args.publish_mode,
        render=not args.no_render,
        progress=progress,
        voice_dir=args.voice_dir,
    )
    ep = find_episode(args.episode) if args.episode else None
    if ep is None:
        ep = next((e for e in VERIFIED_SLATE if e["slug"] == report["slug"]), {})

    if args.no_render:
        _print_report(report)
        return 0

    qa = report.get("qa", {})
    print(report.get("qa_table", ""))
    if not qa.get("passed"):
        print("\n§9 QA GATE FAILED — nothing was published.", file=sys.stderr)
        _print_report(report)
        return 1

    results = publish.publish_episode(Path(report["files"]["video"]), report, ep, args.publish_mode)
    report["publish"] = results
    # a dry run proves the film; only a real upload counts as shipped
    if args.publish_mode != "dry_run" and any(r.get("status") == "uploaded" for r in results):
        record_shipped(ep, report)
    _print_report(report)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    hist = _history()
    shipped = {e.get("slug") for e in hist.get("shipped_episodes", [])}
    rows = [{
        "ep": e.get("ep"),
        "slug": e["slug"],
        "title": e["title"],
        "series": e["series"],
        "shipped": e["slug"] in shipped,
    } for e in VERIFIED_SLATE]
    print(json.dumps({"next_episode_number": hist.get("next_episode_number"), "slate": rows}, indent=2))
    return 0


def cmd_qa(args: argparse.Namespace) -> int:
    video = Path(args.qa)
    if not video.exists():
        print(f"no such file: {video}", file=sys.stderr)
        return 2
    timing = video.parent.parent / "build" / "latest" / "timing.json"
    if not timing.exists():
        candidates = sorted((video.parent.parent / "build").glob("*/timing.json")) if (video.parent.parent / "build").exists() else []
        timing = candidates[-1] if candidates else timing
    if not timing.exists():
        print(f"no timing.json found next to {video}; run the studio first", file=sys.stderr)
        return 2
    data = json.loads(timing.read_text(encoding="utf-8"))
    result = run_checks(video, data["onsets"], data["durations"], data.get("sentences", []))
    print(as_table(result))
    return 0 if result["passed"] else 1


def cmd_ig_only(args: argparse.Namespace) -> int:
    cap = OUTPUT_DIR / "ig_caption.txt"
    report = {"files": {"ig_caption": str(cap)}}
    result = publish.post_instagram(cap, report, "public_now")
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") != "error" else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="draw_me_a_fact.py", description=f"Draw Me a Fact studio v{__version__}")
    p.add_argument("--publish-mode", default="dry_run", choices=PUBLISH_MODES,
                   help="dry_run renders and QA-gates without uploading")
    p.add_argument("--topic", default="", help="optional topic; needs GEMINI_API_KEY or GROQ_API_KEY")
    p.add_argument("--episode", default=None, help="episode number or slug from the pre-verified slate")
    p.add_argument("--no-render", action="store_true", help="plan script + voice + timing only")
    p.add_argument("--voice-dir", default=None, metavar="DIR",
                   help="use pre-recorded narration: one audio file per sentence, in order")
    p.add_argument("--list-slate", action="store_true", help="show the slate and what has shipped")
    p.add_argument("--qa", default=None, metavar="MP4", help="re-run the §9 QA gate on an existing film")
    p.add_argument("--publish-ig-only", action="store_true", help="post the last render to Instagram Reels")
    p.add_argument("--version", action="version", version=f"dmf {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    ensure_dirs()
    args = build_parser().parse_args(argv)
    if args.list_slate:
        return cmd_list(args)
    if args.qa:
        return cmd_qa(args)
    if args.publish_ig_only:
        return cmd_ig_only(args)
    return cmd_produce(args)


if __name__ == "__main__":
    raise SystemExit(main())
