"""The production run: script -> voice -> score -> frames -> mux -> QA."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Callable

from . import audio, deliver, script, voice
from .config import (
    BRAND_DIR,
    BUILD_DIR,
    FIRST_LINE_START,
    INTER_LINE_GAP,
    OUTPUT_DIR,
    ensure_dirs,
)
from .qa_gate import as_table, run_checks
from .render import build_dir, extract_frame, loudnorm_two_pass, mux, render_frames
from .scenes import paint, scene_kind
from .slate import VERIFIED_SLATE, find_episode, next_from_slate

Progress = Callable[[str, float], None]


def _noop(stage: str, pct: float) -> None:  # pragma: no cover
    pass


def plan_scene_windows(scenes: list[dict], onsets: list[float], durations: list[float], tail: float = 0.55) -> list[dict]:
    """Cut the film into one window per sentence, measured from the real audio."""
    windows = []
    for i, (at, d) in enumerate(zip(onsets, durations)):
        start = 0.0 if i == 0 else at - INTER_LINE_GAP / 2
        end = onsets[i + 1] - INTER_LINE_GAP / 2 if i < len(onsets) - 1 else at + d + tail
        windows.append({
            "index": i,
            "kind": scene_kind(scenes[i], i, len(scenes)),
            "start": round(start, 4),
            "end": round(end, 4),
            "duration": round(end - start, 4),
        })
    return windows


def run_episode(
    topic: str | None = None,
    episode: str | int | None = None,
    publish_mode: str = "dry_run",
    voice_source: str = "auto",
    render: bool = True,
    progress: Progress | None = None,
    voice_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Produce one episode end to end. Returns a JSON-serialisable report."""
    report_progress = progress or _noop
    ensure_dirs()
    build_dir()
    tag = None

    # ---------------------------------------------------------------- script
    report_progress("script", 0.02)
    shipped = {e.get("slug") for e in _history().get("shipped_episodes", [])}
    ep = None
    if episode is not None:
        ep = find_episode(episode)
        provenance = "slate"
        if ep is None:
            raise ValueError(f"no episode {episode!r} in the slate")
    else:
        ep = next_from_slate(shipped)
        provenance = "slate"
    ep, provenance = script.generate(topic, preverified=ep)
    problems = script.validate_script(ep)
    if problems:
        raise RuntimeError("script does not meet §3: " + "; ".join(problems))

    # `or` would turn episode 0 into "next in history" — episode numbers are
    # explicit, so test for None instead of falsiness.
    raw_number = ep.get("ep")
    ep_number = int(raw_number if raw_number is not None else _history().get("next_episode_number", 99))
    slug = str(ep.get("slug") or "episode")
    tag = f"ep{ep_number:02d}_{slug}"
    sentences = ep["sentences"]
    scenes = ep["scenes"]

    # ---------------------------------------------------------------- voice
    report_progress("voice", 0.08)
    vdir = BUILD_DIR / tag / "voice"
    if voice_dir:
        provided = sorted(
            [f for f in Path(voice_dir).iterdir() if f.suffix.lower() in voice.AUDIO_SUFFIXES],
            key=lambda f: f.name,
        )
        if len(provided) != len(sentences):
            raise ValueError(
                f"voice_dir needs exactly one audio file per sentence "
                f"({len(sentences)}); found {len(provided)} in {voice_dir}"
            )
        lines = voice.lines_from_files(provided, vdir)
    else:
        lines = voice.synth_lines(sentences, vdir)
    speed = voice.enforce_runtime(lines, vdir)
    clips = [audio.load_audio(l.path) for l in lines]
    durations = [c.size / audio.SR for c in clips]
    voice_source_used = lines[0].source if lines else "none"

    # ---------------------------------------------------------------- score
    report_progress("score", 0.18)
    onsets_plan: list[float] = []
    t = FIRST_LINE_START
    for d in durations:
        onsets_plan.append(round(t, 4))
        t += d + INTER_LINE_GAP
    runtime = onsets_plan[-1] + durations[-1] + 0.55
    sfx_cues = [(onsets_plan[i], ["pop", "whoosh", "tick", "boom", "bell"][i % 5], 1.0) for i in range(len(onsets_plan))]
    if len(sfx_cues) >= 5:
        sfx_cues[-1] = (onsets_plan[-1] + max(0.0, durations[-1] - 0.9), "twinkle", 0.8)
    master, onsets, measured = audio.build_score(clips, FIRST_LINE_START, INTER_LINE_GAP, sfx_cues)
    score_wav = BUILD_DIR / tag / f"{tag}_score.wav"
    audio.write(score_wav, master)
    runtime = master.size / audio.SR

    windows = plan_scene_windows(scenes, onsets, measured)
    timing = {"tag": tag, "runtime": round(runtime, 4), "onsets": onsets,
              "durations": [round(d, 4) for d in measured], "windows": windows, "voice": voice_source_used}
    timing_path = BUILD_DIR / tag / "timing.json"
    timing_path.write_text(json.dumps(timing, indent=2), encoding="utf-8")

    report = {
        "episode": ep_number,
        "slug": slug,
        "title": ep.get("title", ""),
        "series": ep.get("series", ""),
        "provenance": provenance,
        "voice": voice_source_used,
        "speed": speed,
        "sentences": sentences,
        "word_count": sum(len(s.split()) for s in sentences),
        "onsets": onsets,
        "durations": [round(d, 3) for d in measured],
        "runtime": round(runtime, 3),
        "windows": windows,
        "publish_mode": publish_mode,
        "files": {},
    }

    if not render:
        report["files"]["timing"] = str(timing_path)
        report["files"]["score"] = str(score_wav)
        return report

    # ---------------------------------------------------------------- frames
    report_progress("frames", 0.22)

    def frame_fn(_i: int, time_s: float):
        win = windows[-1]
        for w in windows:
            if w["start"] <= time_s < w["end"]:
                win = w
                break
        frac = 0.0 if win["duration"] <= 0 else (time_s - win["start"]) / win["duration"]
        ctx = {"kicker": f"{ep.get('series','')}"}
        return paint(scenes[win["index"]], win["kind"], frac, ctx)

    raw = BUILD_DIR / tag / f"{tag}.mp4"
    info = render_frames(frame_fn, runtime, raw, on_progress=lambda p: report_progress("frames", 0.22 + 0.66 * p))

    report_progress("mux", 0.92)
    final = OUTPUT_DIR / "latest_episode.mp4"
    mux(raw, score_wav, final)
    report_progress("loudness", 0.94)
    loud = loudnorm_two_pass(final, final.with_suffix(".normalised.mp4"))
    if loud.get("normalised"):
        loud_measured = loud
        final.with_suffix(".normalised.mp4").replace(final)
    else:
        loud_measured = {"normalised": False, "reason": loud.get("reason", "")}

    # ---------------------------------------------------------------- deliverables
    report_progress("deliver", 0.95)
    brand_dir = BRAND_DIR / f"ep{ep_number:02d}"
    srt = deliver.write_srt(sentences, onsets, measured, brand_dir / f"ep{ep_number:02d}_en.srt")
    pack = deliver.write_youtube_pack(ep, onsets, measured, runtime, brand_dir / "youtube_pack.md")
    ig = deliver.write_ig_caption(ep, OUTPUT_DIR / "ig_caption.txt")
    shutil.copy2(srt, OUTPUT_DIR / "latest_episode.srt")
    shutil.copy2(pack, OUTPUT_DIR / "youtube_pack.md")

    # contact sheet: one frame per scene + the final frame
    frames: list[Path] = []
    for w in windows:
        at = w["start"] + (w["end"] - w["start"]) * 0.86
        p = BUILD_DIR / tag / f"qa_scene{w['index'] + 1}.png"
        try:
            extract_frame(final, at, p)
            frames.append(p)
        except Exception:
            pass
    end_p = BUILD_DIR / tag / "qa_final.png"
    try:
        from .render import probe as _probe

        video_dur = float(_probe(final).get("format", {}).get("duration", runtime) or runtime)
        extract_frame(final, max(0.0, video_dur - 0.30), end_p)
        frames.append(end_p)
    except Exception:
        pass
    sheet = BUILD_DIR / f"{tag}_sheet.png"
    try:
        deliver.contact_sheet(frames, sheet)
        shutil.copy2(sheet, OUTPUT_DIR / "qa_sheet.png")
    except Exception:
        sheet = Path("")

    # ---------------------------------------------------------------- QA gate
    report_progress("qa", 0.98)
    qa = run_checks(final, onsets, measured, sentences, frames=frames)
    report["loudness"] = loud_measured
    report["qa"] = qa
    report["qa_table"] = as_table(qa)
    (BRAND_DIR / f"ep{ep_number:02d}" / "qa_report.md").write_text(
        f"# QA — EP {ep_number} {slug}\n\n{as_table(qa)}\n", encoding="utf-8"
    )

    report["files"] = {
        "video": str(final),
        "srt": str(OUTPUT_DIR / "latest_episode.srt"),
        "youtube_pack": str(OUTPUT_DIR / "youtube_pack.md"),
        "qa_sheet": str(OUTPUT_DIR / "qa_sheet.png"),
        "ig_caption": str(ig),
        "timing": str(timing_path),
        "score": str(score_wav),
        "raw_video": str(raw),
        "brand_dir": str(brand_dir),
    }
    report["frames"] = info
    return report


def _history() -> dict:
    from .config import HISTORY_PATH

    for path in (HISTORY_PATH, Path(".github/workflows/episodes_history.json")):
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
    return {"next_episode_number": 11, "shipped_episodes": []}


def record_shipped(ep: dict, report: dict) -> dict:
    """Append the episode to history so the next run never repeats it."""
    from .config import HISTORY_PATH

    hist = _history()
    shipped = hist.setdefault("shipped_episodes", [])
    if not any(e.get("slug") == ep.get("slug") for e in shipped):
        shipped.append({
            "ep": report.get("episode"),
            "slug": ep.get("slug"),
            "title": ep.get("title"),
            "series": ep.get("series"),
            "runtime": report.get("runtime"),
            "produced_at": deliver.stamp(),
        })
    hist["next_episode_number"] = max(
        int(hist.get("next_episode_number", 11)),
        int(report.get("episode") or 0) + 1,
    )
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(hist, indent=2), encoding="utf-8")
    return hist


__all__ = ["run_episode", "record_shipped", "plan_scene_windows", "VERIFIED_SLATE"]
