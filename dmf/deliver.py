"""Deliverables (§7): SRT, youtube_pack.md, contact sheet, IG caption."""

from __future__ import annotations

import textwrap
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .config import GREY, H, INK, PAPER, W
from .kit import baloo, text_size


def _ts(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def srt_cues(sentences: list[str], onsets: list[float], durations: list[float]) -> list[tuple[float, float, str]]:
    """One cue per sentence, spanning it exactly (§7)."""
    return [(onsets[i], onsets[i] + durations[i], sentences[i]) for i in range(len(sentences))]


def wrap_cue(text: str, width: int = 42) -> str:
    return "\n".join(textwrap.wrap(text, width=width, break_long_words=False)) or text


def write_srt(sentences: list[str], onsets: list[float], durations: list[float], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for i, (a, b, txt) in enumerate(srt_cues(sentences, onsets, durations), start=1):
        lines.append(f"{i}\n{_ts(a)} --> {_ts(b)}\n{wrap_cue(txt)}\n")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _tags_line(tags: str) -> tuple[str, int]:
    clean = ", ".join(t.strip() for t in tags.split(",") if t.strip())
    while len(clean) > 500:
        clean = clean.rsplit(",", 1)[0]
    return clean, len(clean)


def write_youtube_pack(ep: dict[str, Any], onsets: list[float], durations: list[float], runtime: float, path: Path) -> Path:
    title = str(ep.get("title", ""))[:100]
    alts = [str(t)[:100] for t in ep.get("alt_titles", [])][:3]
    hook = str(ep.get("hook_130", ""))[:130]
    tags, tag_len = _tags_line(str(ep.get("tags", "")))
    acc = ep.get("accuracy_table", [])
    sentences = ep.get("sentences", [])

    numbers = "\n".join(
        f"- Sentence {i}: `{round(onsets[i-1], 2)}s` → `{round(onsets[i-1] + durations[i-1], 2)}s`" for i in range(1, len(sentences) + 1)
    )
    acc_rows = "\n".join(f"| {r.get('claim','')} | {r.get('value','')} | {r.get('source','')} |" for r in acc)
    script_lines = "\n".join(f"> {s}" for s in sentences)

    body = f"""# {title}

**Series:** {ep.get('series','')} · **Runtime:** {runtime:.1f} s · **Format:** 1080×1920 · 30 fps

---

## 1. Title

{title}

## 2. Alternative titles

1. {alts[0] if len(alts) > 0 else title}
2. {alts[1] if len(alts) > 1 else title}
3. {alts[2] if len(alts) > 2 else title}

## 3. Description

{hook}

**The numbers in this film**
{numbers}

Full numbers ladder: {ep.get('numbers_summary','')}

Series: {ep.get('series','')} — one fact, one sheet, one minute.

**Sources**
{chr(10).join('- ' + str(r.get('claim','')) + ': ' + str(r.get('source','')) for r in acc) or '- see accuracy table'}

Drawn by hand on paper. New fact every week.
▶ Subscribe: `<YOUR_SUBSCRIBE_LINK>`

## 4. Tags

{tags}

*Tag length: {tag_len}/500 characters.*

## 5. Pinned comment

{ep.get('pinned_comment','')}

## 6. Accuracy table

| Claim | Value | Source |
|---|---|---|
{acc_rows}

---

### Script (as spoken)

{script_lines}
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def write_ig_caption(ep: dict[str, Any], path: Path) -> Path:
    tags, _ = _tags_line(str(ep.get("tags", "")))
    body = (
        f"{ep.get('title','')}\n\n"
        f"{ep.get('hook_130','')}\n\n"
        f"{ep.get('numbers_summary','')}\n\n"
        f"#drawmeafact #shorts #science\n{tags[:1500]}"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def contact_sheet(frames: list[Path], out_path: Path, cols: int = 3, tile_w: int = 540) -> Path:
    """QA contact sheet. Height must be rows x (tile_h + 8) or the last row clips."""
    if not frames:
        raise ValueError("no frames for contact sheet")
    tile_h = int(tile_w * H / W)
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tile_w + 8 * (cols + 1), rows * (tile_h + 34) + 8), PAPER)
    d = ImageDraw.Draw(sheet)
    f = baloo(24)
    for i, p in enumerate(frames):
        r, c = divmod(i, cols)
        x = 8 + c * (tile_w + 8)
        y = 8 + r * (tile_h + 34)
        try:
            img = Image.open(p).convert("RGB").resize((tile_w, tile_h), Image.LANCZOS)
        except Exception:
            continue
        sheet.paste(img, (x, y))
        d.rectangle([x, y, x + tile_w, y + tile_h], outline=GREY, width=2)
        d.text((x + 8, y + tile_h + 6), p.name, font=f, fill=INK)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    return out_path


def stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")
