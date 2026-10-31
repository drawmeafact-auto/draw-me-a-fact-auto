"""Draw Me a Fact — connector tools.

One source of truth for every operation the studio exposes. The MCP server
(`connector/server.py`) and the HTTP server (`connector/http_server.py`) both
call *these* functions, so a connector client and the CLI can never drift.

Read-only tools are safe to expose to any model. Anything that renders or
publishes costs a render or an upload, so it is gated behind `allow_render` /
`publish_mode`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dmf import __version__, audio, publish, script
from dmf.config import (
    BUILD_DIR,
    FONTS_DIR,
    OUTPUT_DIR,
    PUBLISH_MODES,
    SR,
    ensure_dirs,
)
from dmf.pipeline import _history, run_episode
from dmf.qa_gate import as_table, run_checks
from dmf.slate import TOPIC_BANK, VERIFIED_SLATE, find_episode


# ---------------------------------------------------------------------------
# read-only
# ---------------------------------------------------------------------------
def describe_studio() -> dict[str, Any]:
    """What this connector is, what it can do, and what is currently configured."""
    return {
        "name": "Draw Me a Fact",
        "version": __version__,
        "channel": {
            "handle": "@drawmeafact",
            "tagline": "one fact, one sheet, one minute",
            "format": "vertical 1080x1920, 30 fps, hand-drawn on paper",
            "runtime_ceiling_seconds": 45,
        },
        "capabilities": [
            "episode.get / episode.list — the pre-verified slate",
            "script_plan — write + validate a five-sentence script (no render)",
            "episode.produce — full film: voice, score, frames, mux, QA gate",
            "qa.run — re-run the §9 gate on any existing film",
            "publish.upload — YouTube Shorts (dry_run by default)",
            "assets.list — SRT, upload pack, contact sheet, MP4",
        ],
        "configured": {
            "voice": "edge-tts en-GB-RyanNeural",
            "tts_available": _can_reach(["edge_tts"]),
            "gemini_key": _env_true("GEMINI_API_KEY"),
            "groq_key": _env_true("GROQ_API_KEY"),
            "youtube": publish.youtube_configured(),
            "instagram": publish.instagram_configured(),
        },
        "fonts_present": {
            "baloo2": (FONTS_DIR / "baloo2.ttf").exists(),
            "permanent_marker": (FONTS_DIR / "pm.ttf").exists(),
        },
        "publish_modes": list(PUBLISH_MODES),
    }


def _env_true(name: str) -> bool:
    import os

    return bool(os.getenv(name, "").strip())


def _can_reach(mods: list[str]) -> bool:
    for m in mods:
        try:
            __import__(m)
            return True
        except Exception:
            continue
    return False


def list_episodes(include_shipped: bool = True) -> dict[str, Any]:
    """The pre-verified slate, flagged with what has already shipped."""
    hist = _history()
    shipped = {e.get("slug") for e in hist.get("shipped_episodes", [])}
    rows = []
    for ep in VERIFIED_SLATE:
        if not include_shipped and ep["slug"] in shipped:
            continue
        rows.append({
            "episode": ep.get("ep"),
            "slug": ep["slug"],
            "title": ep["title"],
            "series": ep["series"],
            "sentences": len(ep.get("sentences", [])),
            "shipped": ep["slug"] in shipped,
        })
    pending = next((r for r in rows if not r["shipped"]), None)
    return {
        "next_episode_number": hist.get("next_episode_number"),
        "next_in_queue": pending,
        "episodes": rows,
        "topic_bank": TOPIC_BANK,
    }


def get_episode(identifier: str) -> dict[str, Any]:
    """Full package for one slate episode: script, scenes, sources, timing plan."""
    ep = find_episode(identifier)
    if ep is None:
        raise ValueError(f"no episode {identifier!r} in the slate; call list_episodes()")
    problems = script.validate_script(ep)
    words = sum(len(s.split()) for s in ep.get("sentences", []))
    return {
        "episode": ep.get("ep"),
        "slug": ep["slug"],
        "title": ep["title"],
        "alt_titles": ep.get("alt_titles", []),
        "series": ep.get("series"),
        "sentences": ep.get("sentences"),
        "scenes": ep.get("scenes"),
        "accuracy_table": ep.get("accuracy_table"),
        "hook_130": ep.get("hook_130"),
        "numbers_summary": ep.get("numbers_summary"),
        "pinned_comment": ep.get("pinned_comment"),
        "word_count": words,
        "estimated_runtime_s": round(max(2.4, min(9.5, words / 2.4)) + 0.28 + 4 * 0.18, 1),
        "contract_passed": not problems,
        "contract_problems": problems,
    }


def plan_script(topic: str, series: str | None = None) -> dict[str, Any]:
    """Write and validate a script without touching the renderer.

    Needs GEMINI_API_KEY or GROQ_API_KEY; without one it returns topic
    suggestions instead of inventing facts (the channel's edge is honesty).
    """
    try:
        ep, provenance = script.generate(topic)
    except RuntimeError as exc:
        return {
            "ok": False,
            "reason": str(exc),
            "suggestion": TOPIC_BANK,
            "note": "Set GEMINI_API_KEY or GROQ_API_KEY, or use an already-verified episode.",
        }
    if series:
        ep["series"] = series
    problems = script.validate_script(ep)
    return {"ok": not problems, "provenance": provenance, "episode": ep, "problems": problems}


# ---------------------------------------------------------------------------
# render / publish
# ---------------------------------------------------------------------------
def produce_episode(
    episode: str | None = None,
    topic: str | None = None,
    publish_mode: str = "dry_run",
    render: bool = True,
) -> dict[str, Any]:
    """Produce one episode. Defaults to render + QA, never upload.

    This is the expensive call: a full film is ~1–2 minutes of CPU here and
    longer on a small runner. Use render=False for a plan only.
    """
    if publish_mode not in PUBLISH_MODES:
        raise ValueError(f"publish_mode must be one of {PUBLISH_MODES}")
    report = run_episode(
        topic=topic or None,
        episode=episode,
        publish_mode=publish_mode,
        render=render,
    )
    if not render:
        return report

    ep = find_episode(episode) if episode else next(
        (e for e in VERIFIED_SLATE if e["slug"] == report["slug"]), {}
    )
    qa = report.get("qa", {})
    summary = {
        "episode": report["episode"],
        "slug": report["slug"],
        "title": report["title"],
        "runtime_s": report["runtime"],
        "voice": report["voice"],
        "qa_passed": qa.get("passed", False),
        "qa_table": report.get("qa_table", ""),
        "files": report.get("files", {}),
    }
    if publish_mode != "dry_run" and qa.get("passed"):
        summary["publish"] = publish.publish_episode(Path(report["files"]["video"]), report, ep, publish_mode)
        if any(r.get("status") == "uploaded" for r in summary["publish"]):
            from dmf.pipeline import record_shipped

            record_shipped(ep, report)
    else:
        summary["publish"] = [{"platform": "all", "status": "skipped", "reason": publish_mode if publish_mode == "dry_run" else "QA gate failed"}]
    return summary


def run_qa(video_path: str | None = None) -> dict[str, Any]:
    """Re-run the §9 gate on an already-rendered film."""
    video = Path(video_path) if video_path else OUTPUT_DIR / "latest_episode.mp4"
    if not video.exists():
        return {"passed": False, "error": f"no such file: {video}"}
    candidates = sorted(BUILD_DIR.glob("*/timing.json"), key=lambda p: p.stat().st_mtime)
    timing = candidates[-1] if candidates else None
    if timing is None:
        return {"passed": False, "error": "no timing.json in build/ — produce an episode first"}
    data = json.loads(timing.read_text(encoding="utf-8"))
    result = run_checks(video, data["onsets"], data["durations"], data.get("sentences", []))
    result["table"] = as_table(result)
    result["video"] = str(video)
    return result


def list_assets() -> dict[str, Any]:
    """Every deliverable currently on disk, with sizes."""
    out: dict[str, Any] = {"output": [], "brand": [], "build": []}
    for folder, key in ((OUTPUT_DIR, "output"), (BUILD_DIR, "build")):
        if not folder.exists():
            continue
        for p in sorted(folder.rglob("*")):
            if p.is_file() and p.suffix.lower() in {".mp4", ".srt", ".md", ".png", ".wav", ".json", ".txt"}:
                out[key].append({"path": str(p.relative_to(folder.parent)), "bytes": p.stat().st_size})
    brand = OUTPUT_DIR.parent / "brand"
    if brand.exists():
        for p in sorted(brand.rglob("*")):
            if p.is_file():
                out["brand"].append({"path": str(p.relative_to(brand.parent)), "bytes": p.stat().st_size})
    return out


def score_info() -> dict[str, Any]:
    """Sanity facts about the audio engine — useful for a smoke test."""
    bed = audio.music_bed(4.0)
    return {
        "sample_rate": SR,
        "bed_rms": round(audio.rms(bed), 4),
        "chain": ["aresample 44100", "highpass 65 Hz", "lowpass 10.5 kHz", "normalise 1.0",
                  "reverb mix 0.05 tail 0.26 s damp 6 kHz", "tanh(x*1.25)*0.82", "fade in 20 ms"],
        "first_line_start_s": 0.28,
        "inter_line_gap_s": 0.18,
    }


def ensure() -> None:
    ensure_dirs()


TOOLS = {
    "describe_studio": describe_studio,
    "list_episodes": list_episodes,
    "get_episode": get_episode,
    "plan_script": plan_script,
    "produce_episode": produce_episode,
    "run_qa": run_qa,
    "list_assets": list_assets,
    "score_info": score_info,
}
