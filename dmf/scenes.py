"""Frame painter (§5).

Every beat is expressed as a fraction of *that scene's own measured window*, so
the film re-times itself when the voice changes. Nothing is ever expressed in
absolute seconds from the start of the film.
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image

from .config import ACC, GREY, H, INK, PAPER, S, SAFE_X0, SAFE_X1, SAFE_Y0, SAFE_Y1, W
from .icons import draw_icon
from .kit import Canvas, baloo, draw_heart, fit_font, marker_stack, paper_texture, text_size

EASE = lambda x: 1 - (1 - max(0.0, min(1.0, x))) ** 3  # noqa: E731
CLAMP = lambda x, a=0.0, b=1.0: max(a, min(b, x))  # noqa: E731


def _seg(frac: float, start: float, end: float) -> float:
    """Normalise frac within [start, end] to 0..1."""
    if end <= start:
        return 1.0 if frac >= end else 0.0
    return CLAMP((frac - start) / (end - start))


def format_number(value: float, unit: str = "") -> str:
    if value >= 10000:
        txt = f"{value:,.0f}"
    elif value >= 100:
        txt = f"{value:,.1f}".rstrip("0").rstrip(".")
    elif value >= 10:
        txt = f"{value:.1f}".rstrip("0").rstrip(".")
    elif value >= 1:
        txt = f"{value:.2f}".rstrip("0").rstrip(".")
    else:
        txt = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{txt} {unit}".strip()


def count_up(target: float, p: float) -> float:
    """One number that only grows (§2.5) — eased so it lands rather than stops."""
    return target * EASE(p)


# ---------------------------------------------------------------------------
# shared furniture
# ---------------------------------------------------------------------------
def _kicker(c: Canvas, text: str, y: float = SAFE_Y0 + 22) -> None:
    f = baloo(44)
    c.text(text.upper(), (W / 2, y), f, GREY, anchor="ma")


def _rule(c: Canvas, y: float, p: float, colour=INK) -> None:
    x0, x1 = SAFE_X0 + 60, SAFE_X1 - 60
    mid = (x0 + x1) / 2
    hw = (x1 - x0) / 2 * p
    if hw > 2:
        c.wobble_line((mid - hw, y), (mid + hw, y), color=colour, w=8, amp=1.2)


def _caption(c: Canvas, text: str, y: float, p: float = 1.0, colour=GREY, size: int = 42) -> None:
    """Secondary captions 38-44 px in GREY. Never placed under a red rule."""
    if p <= 0 or not text:
        return
    f = baloo(size)
    c.text(text, (W / 2, y), f, colour, anchor="ma")


def _number_block(c: Canvas, value: float, unit: str, y: float, p: float, colour=ACC, box_h: int = 210) -> None:
    txt = format_number(value, unit)
    f = fit_font(c.draw, txt, int((SAFE_X1 - SAFE_X0) * 1.0), box_h, lo=64, hi=190, max_lines=1)
    c.text(txt, (W / 2, y), f, colour, anchor="mm")


def zoom_punch(img: Image.Image, frac: float, window: float = 0.30, amount: float = 1.06) -> Image.Image:
    """§2.6 / §5: 1.06x settling to 1.0 inside the scene's own window."""
    if frac >= window:
        return img
    z = amount - (amount - 1.0) * EASE(frac / window)
    if z <= 1.0001:
        return img
    w, h = img.size
    cw, ch = int(w / z), int(h / z)
    cx, cy = w // 2, h // 2
    box = (cx - cw // 2, cy - ch // 2, cx + cw // 2, cy + ch // 2)
    return img.crop(box).resize((w, h), Image.LANCZOS)


# ---------------------------------------------------------------------------
# scene painters
# ---------------------------------------------------------------------------
def paint_hook(scene: dict, frac: float, ctx: dict) -> Image.Image:
    c = Canvas(W, H)
    paper_texture(c)
    icon_p = _seg(frac, 0.0, 0.34)
    num_p = _seg(frac, 0.18, 0.92)
    cap_p = _seg(frac, 0.55, 0.85)

    if ctx.get("kicker"):
        _kicker(c, ctx["kicker"])

    # icon, upper third
    draw_icon(scene.get("icon", "atom"), c, W / 2, 620, 200, 200, p=icon_p)

    head = scene.get("headline", "")
    if head:
        f = fit_font(c.draw, head, int((SAFE_X1 - SAFE_X0) * 0.94), 120, lo=40, hi=76, max_lines=2)
        c.text(head, (W / 2, 880), f, INK, anchor="ma")

    # caption sits ABOVE the number: small text under a red rule reads struck through
    _caption(c, str(scene.get("caption", "")), 975, cap_p)

    target = float(scene.get("target_num", 0.0))
    unit = str(scene.get("unit", ""))
    if num_p > 0 and (target or unit):
        _number_block(c, count_up(target, num_p), unit, 1140, num_p)

    _rule(c, 1300, _seg(frac, 0.62, 0.9), colour=ACC)
    return c.finish()


def paint_ladder(scene: dict, frac: float, ctx: dict) -> Image.Image:
    c = Canvas(W, H)
    paper_texture(c)
    if ctx.get("kicker"):
        _kicker(c, ctx["kicker"])

    head = scene.get("headline", "")
    if head:
        f = fit_font(c.draw, head, int((SAFE_X1 - SAFE_X0) * 0.94), 110, lo=40, hi=70, max_lines=2)
        c.text(head, (W / 2, 250), f, INK, anchor="ma")

    rungs = scene.get("ladder") or []
    vals = [float(r.get("val", 0)) for r in rungs] or [1.0]
    vmax = max(vals) or 1.0
    top, bottom = 470, 1210
    x_left = SAFE_X0 + 16
    x_right = SAFE_X1 - 200
    span = x_right - x_left
    for i, rung in enumerate(rungs):
        y = top + (bottom - top) * i / max(1, len(rungs) - 1) if len(rungs) > 1 else top
        local = _seg(frac, 0.06 + i * 0.12, 0.44 + i * 0.12)
        if local <= 0:
            continue
        ratio = float(rung.get("val", 0)) / vmax
        bar_w = max(28.0, span * ratio * EASE(local))
        accent = i == len(rungs) - 1
        lf = fit_font(c.draw, str(rung.get("label", "")), int(span * 0.92), 44, lo=26, hi=40, max_lines=1)
        c.text(str(rung.get("label", "")), (x_left, y - 52), lf, INK, anchor="la")
        c.draw.rounded_rectangle(
            [x_left * S, (y - 18) * S, (x_left + bar_w) * S, (y + 18) * S],
            radius=18 * S, fill=ACC if accent else (232, 230, 224),
        )
        c.draw.rounded_rectangle(
            [x_left * S, (y - 18) * S, (x_left + bar_w) * S, (y + 18) * S],
            radius=18 * S, outline=ACC if accent else GREY, width=int(5 * S / 2),
        )
        vf = baloo(44)
        c.text(str(rung.get("text", "")), (x_left + bar_w + 24, y), vf, ACC if accent else INK, anchor="lm")

    _rule(c, 1330, _seg(frac, 0.5, 0.9), colour=INK)
    _caption(c, str(scene.get("caption", "")), 1392, _seg(frac, 0.62, 0.95))
    return c.finish()


def paint_compare(scene: dict, frac: float, ctx: dict) -> Image.Image:
    c = Canvas(W, H)
    paper_texture(c)
    if ctx.get("kicker"):
        _kicker(c, ctx["kicker"])

    head = scene.get("headline", "")
    if head:
        f = fit_font(c.draw, head, int((SAFE_X1 - SAFE_X0) * 0.94), 110, lo=40, hi=70, max_lines=2)
        c.text(head, (W / 2, 250), f, INK, anchor="ma")

    cmp_ = scene.get("compare") or {}
    left_val = float(cmp_.get("left_val", 1) or 1)
    right_val = float(cmp_.get("right_val", 1) or 1)
    vmax = max(left_val, right_val) or 1.0
    base_y = 1150
    bar_max = 520.0
    cols = [(W * 0.30, left_val, cmp_.get("left_name", ""), cmp_.get("left_txt", ""), (228, 226, 220), INK),
            (W * 0.70, right_val, cmp_.get("right_name", ""), cmp_.get("right_txt", ""), ACC, ACC)]
    for i, (x, val, name, txt, fill, txt_col) in enumerate(cols):
        p = _seg(frac, 0.10 + i * 0.16, 0.62 + i * 0.16)
        if p <= 0:
            continue
        hgt = max(8.0, bar_max * (val / vmax) * EASE(p))
        w = 210
        c.draw.rounded_rectangle([(x - w / 2) * S, (base_y - hgt) * S, (x + w / 2) * S, base_y * S],
                                 radius=18 * S, fill=fill)
        c.wobble_line((x - w / 2, base_y), (x + w / 2, base_y), w=9, amp=1.0)
        vf = fit_font(c.draw, txt, 300, 62, lo=30, hi=54, max_lines=1)
        c.text(txt, (x, base_y - hgt - 56), vf, txt_col, anchor="mm")
        nf = baloo(40)
        c.text(name, (x, base_y + 62), nf, INK, anchor="ma")

    _rule(c, 1330, _seg(frac, 0.55, 0.9), colour=INK)
    cap = scene.get("caption", "")
    if cap:
        f = fit_font(c.draw, cap, int((SAFE_X1 - SAFE_X0) * 0.92), 130, lo=34, hi=42, max_lines=2)
        c.text(cap, (W / 2, 1392), f, GREY, anchor="ma")
    return c.finish()


def paint_end(scene: dict, frac: float, ctx: dict) -> Image.Image:
    """Mandatory beats, all inside the final sentence (§5)."""
    c = Canvas(W, H)
    paper_texture(c)
    if ctx.get("kicker"):
        _kicker(c, ctx["kicker"])

    reframe = str(scene.get("reframe", "THE RULER WAS THE POINT"))
    words = reframe.split()
    f_head = fit_font(c.draw, reframe, int((SAFE_X1 - SAFE_X0) * 0.90), 240, lo=44, hi=76, max_lines=3)

    # 1. reframe types on, word by word
    type_p = _seg(frac, 0.00, 0.34)
    shown = max(1, int(round(len(words) * type_p))) if type_p > 0 else 0
    if shown:
        c.text(" ".join(words[:shown]), (W / 2, 470), f_head, INK, anchor="ma")

    # emphasis word in ACC, once the reframe is complete
    emph = scene.get("emphasis_word")
    if emph and type_p >= 1.0:
        f_e = fit_font(c.draw, emph, int((SAFE_X1 - SAFE_X0) * 0.86), 150, lo=44, hi=96, max_lines=1)
        c.text(emph, (W / 2, 690), f_e, ACC, anchor="ma")

    # 2. the ruler draws under the subject
    ruler_p = _seg(frac, 0.30, 0.56)
    if ruler_p > 0:
        y = 880
        x0, x1 = SAFE_X0 + 40, SAFE_X1 - 40
        c.wobble_line((x0, y), (x0 + (x1 - x0) * EASE(ruler_p), y), w=9, amp=1.2, color=INK)
        ticks = scene.get("ruler_label", "")
        parts = [t.strip() for t in ticks.split("  ") if t.strip()] or []
        if not parts:
            parts = [s.strip() for s in ticks.split() if s.strip()][:3]
        for i, label in enumerate(parts[:3]):
            tx = x0 + (x1 - x0) * i / max(1, len(parts[:3]) - 1)
            if ruler_p > (i + 0.3) / 3:
                c.wobble_line((tx, y - 16), (tx, y + 16), w=7, amp=0.6)
                f_t = baloo(36)
                c.text(label, (tx, y + 52), f_t, GREY, anchor="ma")

    # 3. SUBSCRIBE button box
    btn_p = _seg(frac, 0.46, 0.64)
    if btn_p > 0:
        bw, bh = 430, 116
        cx, cy = W / 2 - 70, 1150
        grow = EASE(btn_p)
        w2, h2 = bw / 2 * grow, bh / 2 * grow
        c.draw.rounded_rectangle([(cx - w2) * S, (cy - h2) * S, (cx + w2) * S, (cy + h2) * S],
                                 radius=24 * S, fill=(250, 240, 238))
        c.wobble_rect(cx - w2 + 2, cy - h2 + 2, cx + w2 - 2, cy + h2 - 2, color=ACC, w=9, radius=24)
        if btn_p > 0.5:
            f_b = baloo(58)
            c.text("SUBSCRIBE", (cx, cy), f_b, ACC, anchor="mm")

    # 4. heart + tap like beside it
    like_p = _seg(frac, 0.58, 0.74)
    if like_p > 0:
        hx = W / 2 + 300
        draw_heart(c, hx, 1136, 70 * EASE(like_p), ACC)
        if like_p > 0.45:
            f_l = baloo(44)
            c.text("tap like", (hx, 1230), f_l, INK, anchor="ma")

    # 5. wordmark fades in
    mark_p = _seg(frac, 0.72, 1.0)
    if mark_p > 0:
        layer, mw, mh = marker_stack(size=78)          # layer is at S scale
        target_w = 0.26 * W * S                        # §5: width = 0.26 x W
        k = target_w / mw
        layer = layer.resize((max(1, int(mw * k)), max(1, int(mh * k))), Image.LANCZOS)
        alpha = layer.split()[-1].point(lambda v: int(v * (0.35 + 0.65 * EASE(mark_p))))
        layer.putalpha(alpha)
        x = int(W * S / 2 - layer.size[0] / 2)
        y = int(0.905 * H * S - layer.size[1])         # baseline at 0.905 x H
        c.img.paste(layer, (x, y), layer)
    return c.finish()


PAINTERS = {"hook": paint_hook, "ladder": paint_ladder, "compare": paint_compare, "end": paint_end}


def scene_kind(scene: dict, index: int, total: int) -> str:
    if index == total - 1:
        return "end"
    if scene.get("ladder"):
        return "ladder"
    if scene.get("compare"):
        return "compare"
    return "hook"


def paint(scene: dict, kind: str, frac: float, ctx: dict) -> Image.Image:
    img = PAINTERS[kind](scene, frac, ctx)
    return zoom_punch(img, frac)
