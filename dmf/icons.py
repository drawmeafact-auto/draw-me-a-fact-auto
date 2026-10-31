"""Hand-drawn icon set (§5).

Each icon draws inside a box centred on (cx, cy) with half-extents (hw, hh).
`p` is 0..1 draw-on progress, so every icon animates rather than popping in.
Nothing is a perfect circle, a perfect straight line, or a decoration without
information.
"""

from __future__ import annotations

import math

import numpy as np

from .config import ACC, GREY, INK
from .kit import Canvas, draw_heart


def _curve(c: Canvas, pts, color=INK, w: int = 13, p: float = 1.0) -> None:
    n = max(2, int(len(pts) * max(0.02, p)))
    seq = pts[:n]
    if len(seq) < 2:
        return
    for a, b in zip(seq, seq[1:]):
        c.draw.line([(a[0] * c.S, a[1] * c.S), (b[0] * c.S, b[1] * c.S)], fill=color, width=int(w * c.S / 2))


def mountain(c: Canvas, cx: float, cy: float, hw: float, hh: float, p: float = 1.0) -> None:
    base = cy + hh
    peak = cy - hh
    left = (cx - hw, base)
    top = (cx - hw * 0.05, peak)
    right = (cx + hw, base)
    c.wobble_line(left, top, w=17, amp=3.0)
    c.wobble_line((top[0], top[1]), (right[0], right[1]), w=17, amp=3.0)
    # snow cap
    cap_y = peak + hh * 0.34
    t = (cap_y - peak) / max(1e-6, base - peak)
    cl = (top[0] + (left[0] - top[0]) * t, cap_y)
    cr = (top[0] + (right[0] - top[0]) * t, cap_y)
    pts = [cl, (cl[0] + (cr[0] - cl[0]) * 0.25, cap_y - hh * 0.10), (cl[0] + (cr[0] - cl[0]) * 0.5, cap_y),
           (cl[0] + (cr[0] - cl[0]) * 0.75, cap_y - hh * 0.08), cr]
    _curve(c, pts, w=8, p=p)
    # a second, smaller ridge for scale
    c.wobble_line((cx - hw * 0.95, base), (cx - hw * 0.55, cy + hh * 0.05), w=12, amp=2.0)
    c.wobble_line((cx - hw * 0.55, cy + hh * 0.05), (cx - hw * 0.25, base), w=12, amp=2.0)
    c.wobble_line((cx - hw * 1.15, base), (cx + hw * 1.15, base), w=9, amp=1.4)


def weight_crush(c: Canvas, cx: float, cy: float, hw: float, hh: float, p: float = 1.0) -> None:
    """A block being squashed: gravity arrows down, base bulging out."""
    bw, bh = hw * 0.62, hh * 0.34
    top_y = cy - hh * 0.62
    c.wobble_rect(cx - bw, top_y, cx + bw, top_y + bh * 2, w=11, radius=10)
    # arrows
    for dx in (-bw * 0.55, 0, bw * 0.55):
        c.wobble_line((cx + dx, top_y - hh * 0.44 * p - 4), (cx + dx, top_y - 10), w=10, amp=1.6)
        c.fill_poly([(cx + dx - 14, top_y - 22), (cx + dx + 14, top_y - 22), (cx + dx, top_y - 2)], INK)
    # bulging base
    base = top_y + bh * 2
    bulge = hh * 0.10 * min(1.0, p * 1.4)
    c.wobble_line((cx - bw, base - 4), (cx - bw - bulge * 0.4, base + bulge), w=12)
    c.wobble_line((cx - bw - bulge * 0.4, base + bulge), (cx + bw + bulge * 0.4, base + bulge), w=12)
    c.wobble_line((cx + bw + bulge * 0.4, base + bulge), (cx + bw, base - 4), w=12)
    # accent slab of overburden
    c.draw.rounded_rectangle(
        [(cx - bw * 0.92) * c.S, (top_y - hh * 0.30) * c.S, (cx + bw * 0.92) * c.S, (top_y - hh * 0.16) * c.S],
        radius=8 * c.S, fill=ACC,
    )


def cloud(c: Canvas, cx: float, cy: float, hw: float, hh: float, p: float = 1.0) -> None:
    r = hh * 0.62
    lobes = [(-hw * 0.52, 6, r * 0.92), (-hw * 0.16, -hh * 0.22, r * 1.05),
             (hw * 0.26, -hh * 0.10, r * 0.90), (hw * 0.56, 8, r * 0.72)]
    for i, (dx, dy, rr) in enumerate(lobes):
        if p < (i + 0.2) / (len(lobes) + 1):
            continue
        c.wobble_ellipse(cx + dx, cy + dy, rr, rr * 0.86, w=12, amp=1.8)
    c.wobble_line((cx - hw * 0.86, cy + r * 0.62), (cx + hw * 0.86, cy + r * 0.62), w=12, amp=1.6)


def cube_grid(c: Canvas, cx: float, cy: float, hw: float, hh: float, p: float = 1.0) -> None:
    """A wireframe cube with a speckled interior = a volume of air."""
    h = hh * 0.92
    w = hw * 0.92
    ox, oy = cx, cy
    d = w * 0.30
    front = [(ox - w, oy - h * 0.55), (ox + w * 0.55, oy - h * 0.55), (ox + w * 0.55, oy + h * 0.62), (ox - w, oy + h * 0.62)]
    back = [(x + d, y - d) for x, y in front]
    c.wobble_poly(front, w=11, closed=True)
    c.wobble_poly(back, w=11, closed=True)
    for a, b in zip(front, back):
        c.wobble_line(a, b, w=9, amp=1.2)
    rng = np.random.default_rng(3)
    for _ in range(90):
        x = rng.uniform(ox - w * 0.95, ox + w * 0.5)
        y = rng.uniform(oy - h * 0.5, oy + h * 0.58)
        rr = rng.uniform(1.5, 3.4) * p
        c.draw.ellipse([(x - rr) * c.S, (y - rr) * c.S, (x + rr) * c.S, (y + rr) * c.S], fill=GREY)


def paper(c: Canvas, cx: float, cy: float, hw: float, hh: float, p: float = 1.0) -> None:
    w, h = hw * 0.72, hh * 0.92
    pts = [(cx - w, cy - h + 18), (cx + w - 30, cy - h), (cx + w, cy - h + 34), (cx + w, cy + h), (cx - w, cy + h)]
    c.wobble_poly(pts, w=12, closed=True)
    c.wobble_line((cx + w - 32, cy - h + 2), (cx + w - 32, cy - h + 34), w=8, amp=1.0)
    c.wobble_line((cx + w - 32, cy - h + 34), (cx + w - 2, cy - h + 34), w=8, amp=1.0)
    for i in range(3):
        y = cy - h * 0.30 + i * h * 0.28
        if p > (i + 1) / 4:
            c.wobble_line((cx - w * 0.62, y), (cx + w * 0.55, y), w=7, amp=1.0, color=GREY)
    # accent thickness marker on the edge
    c.draw.rectangle([(cx + w - 4) * c.S, (cy - h * 0.2) * c.S, (cx + w + 6) * c.S, (cy + h * 0.2) * c.S], fill=ACC)


def fold_layers(c: Canvas, cx: float, cy: float, hw: float, hh: float, p: float = 1.0) -> None:
    """A stack of doubling sheets seen edge-on."""
    layers = 9
    w = hw * 0.95
    for i in range(layers):
        if p < i / layers:
            break
        y = cy + hh * 0.8 - i * (hh * 1.6 / layers)
        inset = i * w * 0.035
        c.wobble_line((cx - w + inset, y), (cx + w - inset, y), w=10, amp=1.3,
                      color=ACC if i == layers - 1 else INK)
    c.wobble_line((cx - w * 1.02, cy + hh * 0.92), (cx + w * 1.02, cy + hh * 0.92), w=8, amp=1.0, color=GREY)


def tshirt(c: Canvas, cx: float, cy: float, hw: float, hh: float, p: float = 1.0) -> None:
    w, h = hw * 0.92, hh * 0.86
    pts = [
        (cx - w * 0.34, cy - h), (cx - w * 0.10, cy - h * 1.12), (cx + w * 0.10, cy - h * 1.12),
        (cx + w * 0.34, cy - h), (cx + w, cy - h * 0.52), (cx + w * 0.76, cy - h * 0.20),
        (cx + w * 0.58, cy - h * 0.34), (cx + w * 0.58, cy + h), (cx - w * 0.58, cy + h),
        (cx - w * 0.58, cy - h * 0.34), (cx - w * 0.76, cy - h * 0.20), (cx - w, cy - h * 0.52),
    ]
    c.wobble_poly(pts, w=13, closed=True)
    # collar
    _curve(c, [(cx - w * 0.16, cy - h * 1.06), (cx, cy - h * 0.86), (cx + w * 0.16, cy - h * 1.06)], w=8, p=p)
    if p > 0.5:
        c.draw.rectangle([(cx - w * 0.46) * c.S, (cy + h * 0.30) * c.S, (cx + w * 0.46) * c.S, (cy + h * 0.44) * c.S], fill=ACC)


def water(c: Canvas, cx: float, cy: float, hw: float, hh: float, p: float = 1.0) -> None:
    """A droplet with a fill line — the litre counter."""
    top = (cx, cy - hh * 0.92)
    pts = [top, (cx + hw * 0.62, cy + hh * 0.10), (cx + hw * 0.34, cy + hh * 0.72),
           (cx, cy + hh * 0.88), (cx - hw * 0.34, cy + hh * 0.72), (cx - hw * 0.62, cy + hh * 0.10)]
    c.wobble_poly(pts, w=13, closed=True)
    fill_y = cy + hh * 0.88 - (hh * 1.5 * min(1.0, p))
    fill_y = max(fill_y, cy - hh * 0.30)
    c.draw.rectangle([(cx - hw * 0.46) * c.S, fill_y * c.S, (cx + hw * 0.46) * c.S, (cy + hh * 0.74) * c.S], fill=ACC)
    c.wobble_line((cx - hw * 0.46, fill_y), (cx + hw * 0.46, fill_y), w=7, amp=0.8, color=INK)


def atom(c: Canvas, cx: float, cy: float, hw: float, hh: float, p: float = 1.0) -> None:
    c.wobble_ellipse(cx, cy, hw * 0.9, hh * 0.55, w=11)
    c.wobble_ellipse(cx, cy, hw * 0.55, hh * 0.9, w=11)
    c.wobble_ellipse(cx - hw * 0.2, cy + hh * 0.1, hw * 0.75, hh * 0.35, w=9)
    draw_heart(c, cx, cy, hh * 0.55, ACC)


def strands(c: Canvas, cx: float, cy: float, hw: float, hh: float, p: float = 1.0) -> None:
    """A head's crown with hairs growing out of it — states the subject, no decoration."""
    base = cy + hh * 0.55
    # scalp line: a shallow dome, never a perfect arc
    dome = [(cx - hw, base)] + [
        (cx - hw + 2 * hw * u, base - hh * 0.34 * math.sin(math.pi * u))
        for u in np.linspace(0.05, 0.95, 18)
    ] + [(cx + hw, base)]
    c.draw.line([(x * c.S, y * c.S) for x, y in dome], fill=INK, width=int(13 * c.S / 2), joint="curve")
    hairs = [(-0.78, 0.62), (-0.42, 0.94), (0.02, 1.0), (0.44, 0.9), (0.79, 0.58)]
    for i, (ux, tall) in enumerate(hairs):
        if p < (i + 1) / (len(hairs) + 2):
            continue
        x0 = cx + ux * hw
        y0 = base - hh * 0.34 * math.sin(math.pi * (ux + 1) / 2)
        length = hh * 1.5 * tall
        pts = [(x0 + math.sin(u * 3.1 + i) * hw * 0.10 * u, y0 - length * u) for u in np.linspace(0, 1, 14)]
        c.draw.line([(x * c.S, y * c.S) for x, y in pts], fill=INK, width=int(7 * c.S / 2), joint="curve")
    c.wobble_line((cx - hw * 1.1, base + hh * 0.16), (cx + hw * 1.1, base + hh * 0.16), w=9, amp=1.2)


def ruler(c: Canvas, cx: float, cy: float, hw: float, hh: float, p: float = 1.0) -> None:
    w = hw * 0.98
    c.draw.rounded_rectangle([(cx - w) * c.S, (cy - hh * 0.34) * c.S, (cx + w) * c.S, (cy + hh * 0.34) * c.S],
                             radius=10 * c.S, fill=(238, 238, 232))
    c.wobble_rect(cx - w, cy - hh * 0.34, cx + w, cy + hh * 0.34, w=9, radius=12)
    for i in range(11):
        x = cx - w + (2 * w) * i / 10
        ln = hh * (0.44 if i % 5 == 0 else 0.26)
        if p > i / 12:
            c.wobble_line((x, cy - hh * 0.34), (x, cy - hh * 0.34 + ln), w=6, amp=0.6)


ICONS = {
    "strands": strands,
    "mountain": mountain,
    "weight_crush": weight_crush,
    "cloud": cloud,
    "cube_grid": cube_grid,
    "paper": paper,
    "fold_layers": fold_layers,
    "tshirt": tshirt,
    "water": water,
    "atom": atom,
    "ruler": ruler,
}


def draw_icon(name: str, c: Canvas, cx: float, cy: float, hw: float, hh: float, p: float = 1.0) -> None:
    fn = ICONS.get(name, atom)
    fn(c, cx, cy, hw, hh, p)
