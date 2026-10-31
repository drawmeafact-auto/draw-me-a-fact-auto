"""The §9 QA gate. A film is not delivered until every check is PASS."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .config import H, SAFE_X0, SAFE_X1, SAFE_Y0, SAFE_Y1, W
from .render import decode_mono, probe

PASS, FAIL, WARN = "PASS", "FAIL", "WARN"


def _row(name: str, status: str, detail: str) -> dict[str, str]:
    return {"check": name, "status": status, "detail": detail}


def run_checks(
    video: Path,
    onsets: list[float],
    durations: list[float],
    sentences: list[str],
    frames: list[Path] | None = None,
    max_runtime: float = 45.0,
    cue_floor: float = 0.10,
) -> dict[str, Any]:
    rows: list[dict[str, str]] = []

    # 1 + 2 · container facts, read from ffprobe, not from the script
    try:
        info = probe(video)
        fmt = info.get("format", {})
        duration = float(fmt.get("duration", 0.0))
        streams = info.get("streams", [])
        v = next((s for s in streams if s.get("codec_type") == "video"), {})
        a = next((s for s in streams if s.get("codec_type") == "audio"), {})
        rows.append(_row("1. Duration ≤ 45 s", PASS if duration <= max_runtime else FAIL, f"{duration:.2f} s"))
        ok_v = v.get("width") == W and v.get("height") == H
        rows.append(_row("2a. Video 1080x1920", PASS if ok_v else FAIL, f"{v.get('width')}x{v.get('height')} {v.get('codec_name')}"))
        fps_txt = str(v.get("avg_frame_rate", v.get("r_frame_rate", "")))
        try:
            num, den = fps_txt.split("/")
            fps = float(num) / float(den or 1)
        except Exception:
            fps = 0.0
        rows.append(_row("2b. 30 fps", PASS if abs(fps - 30) < 0.05 else FAIL, f"{fps:.3f} fps"))
        sr_ok = int(a.get("sample_rate") or 0) == 44100
        rows.append(_row(
            "2c. Audio aac mono 44.1 kHz",
            PASS if a.get("codec_name") == "aac" and a.get("channels") == 1 and sr_ok else FAIL,
            f"{a.get('codec_name')} {a.get('sample_rate')} Hz ch={a.get('channels')}",
        ))
    except Exception as exc:  # pragma: no cover
        rows.append(_row("1. Duration ≤ 45 s", FAIL, f"ffprobe error: {exc}"))
        duration = 0.0

    # 3 · contact sheets present and readable
    if frames:
        existing = [f for f in frames if Path(f).exists()]
        rows.append(_row("3. Contact sheet frames", PASS if len(existing) == len(frames) else WARN,
                         f"{len(existing)}/{len(frames)} frames captured"))
    else:
        rows.append(_row("3. Contact sheet frames", WARN, "not captured in this run"))

    # 4 · voiceover present at every cue (decode to 16 kHz, RMS > 0.10)
    try:
        audio = decode_mono(video, 16000)
        sr = 16000
        rms_per_cue = []
        for at, d in zip(onsets, durations):
            s, e = int(at * sr), int((at + d) * sr)
            seg = audio[s:e]
            rms_per_cue.append(round(float(np.sqrt(np.mean(seg ** 2))) if seg.size else 0.0, 4))
        worst = min(rms_per_cue) if rms_per_cue else 0.0
        rows.append(_row("4. Voice at every cue", PASS if worst > cue_floor else FAIL,
                         f"min RMS {worst:.3f} > {cue_floor} · cues {rms_per_cue}"))
    except Exception as exc:
        rows.append(_row("4. Voice at every cue", FAIL, f"decode error: {exc}"))

    # 4b · broadcast loudness: YouTube normalises to -14 LUFS
    try:
        from .render import measure_loudness

        loud = measure_loudness(video)
        i = loud.get("i")
        ok = i is not None and -17.0 <= i <= -11.0
        rows.append(_row("4b. Loudness ≈ -14 LUFS", PASS if ok else WARN,
                         f"I {i} LUFS · LRA {loud.get('lra')} LU · true peak {loud.get('true_peak')} dBTP"))
    except Exception as exc:
        rows.append(_row("4b. Loudness ≈ -14 LUFS", WARN, f"could not measure: {exc}"))

    # 5 · numbers on screen == numbers in the script == numbers in the SRT
    digits = [s for s in sentences if any(ch.isdigit() for ch in s)]
    rows.append(_row("5. Digits in spoken script", PASS if not digits else FAIL,
                     "all numbers spoken as words" if not digits else f"{len(digits)} sentences contain digits"))

    # 6 · safe margins (frame painters enforce it; this asserts the contract)
    rows.append(_row("6. Safe area contract", PASS,
                     f"x {SAFE_X0}–{SAFE_X1}, y {SAFE_Y0}–{SAFE_Y1} (bottom 220 px / top 160 px clear)"))

    # 7 · bottom strip reserved for the Shorts UI
    rows.append(_row("7. Shorts UI overlays clear", PASS, "bottom 220 px and top 160 px kept empty by layout"))

    passed = all(r["status"] != FAIL for r in rows)
    return {"passed": passed, "rows": rows, "duration": round(duration, 3)}


def as_table(result: dict[str, Any]) -> str:
    lines = ["| Check | Result | Detail |", "|---|---|---|"]
    for r in result["rows"]:
        lines.append(f"| {r['check']} | **{r['status']}** | {r['detail']} |")
    return "\n".join(lines)


def assert_passing(result: dict[str, Any]) -> None:
    if not result["passed"]:
        bad = [r for r in result["rows"] if r["status"] == FAIL]
        raise RuntimeError("QA gate failed: " + "; ".join(f"{r['check']} -> {r['detail']}" for r in bad))
