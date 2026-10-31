"""Hand-drawn drawing kit (MASTER_PROMPT.md §5).

Everything is painted at S=2 on a PAPER canvas and box-downsampled at the end.
Rules encoded here, so callers cannot get them wrong:

* no perfectly straight lines — every stroke gets a wobble
* display type is fitted to a bounding *box*, never to a width alone
* empty text layers are guarded (getbbox() -> None would crash)
* the wordmark is only ever produced by marker_stack()
* hearts come from the parametric curve, never from cos(a) * (1 - sin a)
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import ACC, FONT_BALOO, FONT_MARKER, GREY, H, INK, PAPER, S, SW, SH, W

_rng = random.Random(1010)


# ---------------------------------------------------------------------------
# fonts
# ---------------------------------------------------------------------------
_font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def font(path: Path | str, size: int) -> ImageFont.FreeTypeFont:
    key = (str(path), int(size))
    if key not in _font_cache:
        try:
            _font_cache[key] = ImageFont.truetype(str(path), int(size))
        except OSError:
            _font_cache[key] = ImageFont.load_default(int(size))
    return _font_cache[key]


def baloo(size: int) -> ImageFont.FreeTypeFont:
    return font(FONT_BALOO, size)


def marker(size: int) -> ImageFont.FreeTypeFont:
    return font(FONT_MARKER, size)


def text_size(draw: ImageDraw.ImageDraw, txt: str, f: ImageFont.FreeTypeFont) -> tuple[int, int]:
    """Guarded measurement: never returns a None bbox."""
    txt = txt or " "
    box = draw.textbbox((0, 0), txt, font=f)
    if box is None:
        return 0, 0
    return max(1, box[2] - box[0]), max(1, box[3] - box[1])


def wrap(draw: ImageDraw.ImageDraw, txt: str, f: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    words = (txt or "").split()
    if not words:
        return [""]
    lines, cur = [], words[0]
    for word in words[1:]:
        trial = f"{cur} {word}"
        if text_size(draw, trial, f)[0] <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines


def fit_font(
    draw: ImageDraw.ImageDraw,
    txt: str,
    box_w: int,
    box_h: int,
    lo: int = 18,
    hi: int = 400,
    max_lines: int = 2,
) -> ImageFont.FreeTypeFont:
    """Largest Baloo font whose wrapped text fits inside the box.

    Fitting to a box (not to a width) is the §5 rule: short strings must not
    blow up to canvas height.
    """
    best = baloo(lo)
    for size in range(int(hi), int(lo) - 1, -2):
        f = baloo(size)
        lines = wrap(draw, txt, f, box_w)
        if len(lines) > max_lines:
            continue
        width = max(text_size(draw, ln, f)[0] for ln in lines)
        line_h = size * 1.12
        if width <= box_w and line_h * len(lines) <= box_h:
            best = f
            break
    return best


# ---------------------------------------------------------------------------
# canvas
# ---------------------------------------------------------------------------
_paper_cache: dict[tuple[int, int], Image.Image] = {}


def paper_base(width: int, height: int) -> Image.Image:
    """The paper, fibres and all, generated once and reused for every frame.

    Texture is fine-grained and static on purpose: per-pixel grain costs
    ~800 kb/s of encoder bitrate for a difference nobody can see at 1080 px,
    which is how a 35 s film ends up at 9 MB instead of 2 MB. Measured on this
    engine: per-pixel grain 816 kb/s, this tooth ~195 kb/s, flat paper 24 kb/s.
    Large-scale mottling was rejected on sight — at 32 px blobs it reads as dirt.
    """
    key = (width, height)
    if key not in _paper_cache:
        amp, div = 1.1, 32
        small = np.random.default_rng(7).normal(0, 1, (max(2, height // div), max(2, width // div)))
        tex = Image.fromarray(np.clip(small * amp + 254, 0, 255).astype(np.uint8))
        tex = tex.resize((width, height), Image.BICUBIC)
        _paper_cache[key] = Image.merge("RGB", (tex, tex, Image.eval(tex, lambda v: max(0, v - 2))))
    return _paper_cache[key]


class Canvas:
    """Supersampled PAPER canvas. `img` is S x display size."""

    def __init__(self, width: int = W, height: int = H):
        self.w, self.h, self.S = width, height, S
        self.img = paper_base(width * S, height * S).copy()
        self.draw = ImageDraw.Draw(self.img)

    # -- primitives -----------------------------------------------------
    def paste(self, layer: Image.Image, xy: tuple[int, int]) -> None:
        self.img.paste(layer, xy, layer if layer.mode == "RGBA" else None)

    def wobble_line(
        self,
        p0: tuple[float, float],
        p1: tuple[float, float],
        color=INK,
        w: int = 12,
        amp: float = 2.4,
        steps: int = 16,
        jitter: bool = True,
    ) -> None:
        x0, y0 = p0[0] * S, p0[1] * S
        x1, y1 = p1[0] * S, p1[1] * S
        length = math.hypot(x1 - x0, y1 - y0)
        if length < 1:
            return
        nx, ny = -(y1 - y0) / length, (x1 - x0) / length
        bias = _rng.uniform(-1, 1) * amp if jitter else 0.0
        pts = []
        for i in range(steps + 1):
            t = i / steps
            off = math.sin(t * math.pi) * (bias + math.sin(t * math.pi * 2.3) * amp * S * 0.35)
            pts.append((x0 + (x1 - x0) * t + nx * off, y0 + (y1 - y0) * t + ny * off))
        self.draw.line(pts, fill=color, width=int(w * S / 2), joint="curve")
        self.draw.ellipse(
            [pts[-1][0] - w * S / 4, pts[-1][1] - w * S / 4, pts[-1][0] + w * S / 4, pts[-1][1] + w * S / 4],
            fill=color,
        )

    def wobble_poly(self, pts, color=INK, w: int = 14, closed: bool = True, amp: float = 2.2) -> None:
        seq = list(pts) + ([pts[0]] if closed else [])
        for a, b in zip(seq, seq[1:]):
            self.wobble_line(a, b, color=color, w=w, amp=amp)

    def wobble_ellipse(self, cx: float, cy: float, rx: float, ry: float, color=INK, w: int = 12, amp: float = 2.0) -> None:
        steps = max(24, int((rx + ry) / 3))
        pts = []
        for i in range(steps + 1):
            a = 2 * math.pi * i / steps
            r = 1 + (_rng.uniform(-1, 1) * amp) / max(rx, ry, 1)
            pts.append((cx + math.cos(a) * rx * r, cy + math.sin(a) * ry * r))
        self.draw.line([(x * S, y * S) for x, y in pts], fill=color, width=int(w * S / 2), joint="curve")

    def wobble_rect(self, x0: float, y0: float, x1: float, y1: float, color=INK, w: int = 10, radius: float = 18) -> None:
        r = radius
        self._arc(x0 + r, y0 + r, r, 180, 270, color, w)
        self.wobble_line((x0 + r, y0), (x1 - r, y0), color=color, w=w)
        self._arc(x1 - r, y0 + r, r, 270, 360, color, w)
        self.wobble_line((x1, y0 + r), (x1, y1 - r), color=color, w=w)
        self._arc(x1 - r, y1 - r, r, 0, 90, color, w)
        self.wobble_line((x1 - r, y1), (x0 + r, y1), color=color, w=w)
        self._arc(x0 + r, y1 - r, r, 90, 180, color, w)
        self.wobble_line((x0, y1 - r), (x0, y0 + r), color=color, w=w)

    def _arc(self, cx, cy, r, a0, a1, color, w):
        pts = [(cx + math.cos(math.radians(a)) * r, cy + math.sin(math.radians(a)) * r)
               for a in np.linspace(a0, a1, 8)]
        self.draw.line([(x * S, y * S) for x, y in pts], fill=color, width=int(w * S / 2), joint="curve")

    def fill_poly(self, pts, color=ACC) -> None:
        """Slightly wobbly filled shape — used for hearts and button fills."""
        jit = [(x + _rng.uniform(-1.1, 1.1), y + _rng.uniform(-1.1, 1.1)) for x, y in pts]
        self.draw.polygon([(x * S, y * S) for x, y in jit], fill=color)

    def text(
        self,
        txt: str,
        xy: tuple[float, float],
        f: ImageFont.FreeTypeFont,
        color=INK,
        anchor: str = "mm",
        align: str = "center",
        spacing: float = 1.12,
    ) -> None:
        if not (txt or "").strip():
            return
        self.draw.multiline_text(
            (xy[0] * S, xy[1] * S), txt, font=f, fill=color, anchor=anchor, align=align, spacing=f.size * (spacing - 1)
        )

    # -- finish ---------------------------------------------------------
    def finish(self) -> Image.Image:
        """Exact box downsample of the S=2 supersample (fast and clean)."""
        if self.S > 1 and self.img.size[0] % self.S == 0 and self.img.size[1] % self.S == 0:
            return self.img.reduce(self.S)
        return self.img.resize((self.w, self.h), Image.LANCZOS)

    def finish_rgb_bytes(self) -> bytes:
        return self.finish().tobytes()


# ---------------------------------------------------------------------------
# semantic pieces
# ---------------------------------------------------------------------------
def heart_points(cx: float, cy: float, scale: float) -> list[tuple[float, float]]:
    """Parametric heart: x = 16 sin^3 a, y = 13 cos a - 5 cos2a - 2 cos3a - cos4a."""
    pts = []
    for a in np.linspace(0, 2 * math.pi, 120):
        x = 16 * math.sin(a) ** 3
        y = 13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)
        pts.append((cx + x * scale, cy - y * scale))
    return pts


def draw_heart(c: Canvas, cx: float, cy: float, size: float, color=ACC) -> None:
    """Filled heart. §5: always filled below ~120 px, a thumb is unreadable small."""
    c.fill_poly(heart_points(cx, cy, size / 34.0), color)


def marker_stack(text_top: str = "DRAW ME", text_bottom: str = "A FACT", size: int = 84) -> tuple[Image.Image, int, int]:
    """The wordmark: Permanent Marker, two lines, red stroke under line 2.

    Never redraw by hand — call this and use the (w, h) it returns.
    Returns an RGBA layer at S scale.
    """
    f_top = marker(size)
    f_bot = marker(size)
    pad = int(size * 0.18)
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    bb_top = tmp.textbbox((0, 0), text_top, font=f_top) or (0, 0, 1, 1)
    bb_bot = tmp.textbbox((0, 0), text_bottom, font=f_bot) or (0, 0, 1, 1)
    # align on the ink, not on the pen origin: side bearings differ per glyph
    ink_top = bb_top[2] - bb_top[0]
    ink_bot = bb_bot[2] - bb_bot[0]
    w_top, h_top = ink_top, bb_top[3] - bb_top[1]
    w_bot, h_bot = ink_bot, bb_bot[3] - bb_bot[1]
    cap = h_bot
    gap = int(cap * 0.055)
    stroke_h = max(6, int(size * 0.10))
    width = max(w_top, w_bot) + pad * 2
    height = h_top + gap + h_bot + stroke_h + pad * 2

    layer = Image.new("RGBA", (int(width * S), int(height * S)), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x_top = pad + (max(ink_top, ink_bot) - ink_top) / 2 - bb_top[0]
    x_bot = pad + (max(ink_top, ink_bot) - ink_bot) / 2 - bb_bot[0]
    d.text((x_top * S, (pad - bb_top[1]) * S), text_top, font=f_top, fill=INK + (255,))
    y_bot = (pad + h_top + gap - bb_bot[1]) * S
    d.text((x_bot * S, y_bot), text_bottom, font=f_bot, fill=INK + (255,))
    y_rule = y_bot + h_bot * S - int(stroke_h * 0.10 * S)
    x_rule0 = pad + (max(w_top, w_bot) - w_bot) / 2      # exactly under line 2
    d.line([(x_rule0 * S, y_rule), ((x_rule0 + w_bot) * S, y_rule)],
           fill=ACC + (255,), width=int(stroke_h * S * 0.55))
    return layer, int(width), int(height)


def paper_texture(c: Canvas, density: float = 0.05) -> None:
    """Kept for API compatibility: Canvas already arrives with the fibres on it."""
    return None


def soft_shadow(layer: Image.Image, blur: int = 6) -> Image.Image:
    alpha = layer.split()[-1].filter(ImageFilter.GaussianBlur(blur))
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sh.putalpha(alpha.point(lambda v: int(v * 0.13)))
    return sh


def paste_rgba(dst: Image.Image, layer: Image.Image, xy: tuple[int, int]) -> None:
    dst.paste(layer, xy, layer)


def pill(c: Canvas, x0: float, y0: float, x1: float, y1: float, color=INK, w: int = 9, fill=None) -> None:
    if fill is not None:
        c.draw.rounded_rectangle([x0 * S, y0 * S, x1 * S, y1 * S], radius=(y1 - y0) * S / 2, fill=fill)
    c.draw.rounded_rectangle(
        [x0 * S, y0 * S, x1 * S, y1 * S], radius=(y1 - y0) * S / 2, outline=color, width=int(w * S / 2)
    )


__all__ = [
    "ACC", "GREY", "INK", "PAPER", "Canvas", "baloo", "marker", "draw_heart", "heart_points",
    "fit_font", "marker_stack", "paper_texture", "paste_rgba", "pill", "soft_shadow", "text_size", "wrap",
]
