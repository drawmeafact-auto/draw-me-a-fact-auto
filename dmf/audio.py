"""Audio engine — the exact §4 post chain, music bed and Foley.

Pure numpy/scipy-free implementation: a one-pole high-pass, an FFT low-pass, a
short convolution reverb, tanh compression. Every helper takes and returns float
arrays in [-1, 1] at 44.1 kHz mono.

Never run this module bare: `python -m dmf.audio` is blocked on purpose.
"""

from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np

from .config import INTER_LINE_GAP, MUSIC_BED_LEVEL, REVERB_MIX, SFX_LEVEL, SR


# ---------------------------------------------------------------------------
# io
# ---------------------------------------------------------------------------
def load_audio(path: Path | str | bytes) -> np.ndarray:
    """Read 16-bit PCM mono/stereo WAV into a mono float32 array."""
    import io

    src = io.BytesIO(path) if isinstance(path, (bytes, bytearray)) else str(path)
    with wave.open(src, "rb") as wf:
        n = wf.getnframes()
        ch = wf.getnchannels()
        raw = wf.readframes(n)
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    return data


def resample(a: np.ndarray, sr_from: int, sr_to: int = SR) -> np.ndarray:
    if sr_from == sr_to or a.size == 0:
        return a
    n_to = int(round(a.size * sr_to / sr_from))
    x_old = np.linspace(0, 1, a.size, endpoint=False)
    x_new = np.linspace(0, 1, n_to, endpoint=False)
    return np.interp(x_new, x_old, a).astype(np.float32)


def write(path: Path | str, data: np.ndarray, sr: int = SR) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    d = np.clip(data, -1.0, 1.0)
    pcm = (d * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    return path


def place(track: np.ndarray, clip: np.ndarray, at: float, gain: float = 1.0, sr: int = SR) -> np.ndarray:
    start = int(round(at * sr))
    if start + clip.size > track.size:
        track = np.pad(track, (0, start + clip.size - track.size))
    track[start:start + clip.size] += clip * gain
    return track


def rms(a: np.ndarray) -> float:
    if a.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(a, dtype=np.float64))))


# ---------------------------------------------------------------------------
# filters
# ---------------------------------------------------------------------------
def highpass(a: np.ndarray, cutoff: float = 65.0, sr: int = SR) -> np.ndarray:
    """One-pole high-pass, run twice for a 12 dB/oct slope."""
    x = a.astype(np.float64)
    rc = 1.0 / (2 * math.pi * cutoff)
    alpha = rc / (rc + 1.0 / sr)
    for _ in range(2):
        y = np.empty_like(x)
        prev_x = prev_y = 0.0
        for i in range(x.size):
            prev_y = alpha * (prev_y + x[i] - prev_x)
            prev_x = x[i]
            y[i] = prev_y
        x = y
    return x.astype(np.float32)


def fft_filter(a: np.ndarray, lo: float | None = None, hi: float | None = None, sr: int = SR, slope: float = 2.0) -> np.ndarray:
    """Zero-phase Butterworth-shaped band filter in the frequency domain."""
    if a.size == 0:
        return a
    n = int(2 ** math.ceil(math.log2(max(1024, a.size))))
    spec = np.fft.rfft(a, n)
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    gain = np.ones_like(freqs)
    if lo:
        gain *= 1.0 / np.sqrt(1.0 + (lo / np.maximum(freqs, 1e-6)) ** (2 * slope))
    if hi:
        gain *= 1.0 / np.sqrt(1.0 + (freqs / hi) ** (2 * slope))
    out = np.fft.irfft(spec * gain, n)[: a.size]
    return out.astype(np.float32)


def compress(a: np.ndarray, drive: float = 1.25, makeup: float = 0.82) -> np.ndarray:
    """§4: np.tanh(d * 1.25) * 0.82 — even, close delivery."""
    return (np.tanh(a * drive) * makeup).astype(np.float32)


def normalise(a: np.ndarray, peak: float = 1.0) -> np.ndarray:
    m = float(np.max(np.abs(a))) if a.size else 0.0
    if m < 1e-9:
        return a
    return (a * (peak / m)).astype(np.float32)


def reverb(a: np.ndarray, mix: float = REVERB_MIX, tail: float = 0.26, damp: float = 6000.0, sr: int = SR) -> np.ndarray:
    """A tight room: exponentially decaying noise impulse, damped, mixed low."""
    if mix <= 0:
        return a
    n = int(tail * sr)
    rng = np.random.default_rng(42)
    ir = rng.normal(0, 1, n).astype(np.float32)
    env = np.exp(-np.linspace(0, 6.5, n)).astype(np.float32)
    ir = ir * env
    ir = fft_filter(ir, hi=damp)
    ir = normalise(ir, 0.9)
    wet = np.convolve(a, ir)[: a.size]
    wet = normalise(wet, 0.9)
    return ((1 - mix) * a + mix * wet).astype(np.float32)


def fade(a: np.ndarray, ms: float = 20.0, at: str = "in", sr: int = SR) -> np.ndarray:
    n = max(1, int(sr * ms / 1000.0))
    n = min(n, a.size)
    ramp = np.linspace(0, 1, n) ** 1.4
    out = a.copy()
    if at == "in":
        out[:n] *= ramp
    else:
        out[-n:] *= ramp[::-1]
    return out


def voice_chain(a: np.ndarray, sr: int = SR) -> np.ndarray:
    """The locked post chain, in order (§4 table)."""
    a = resample(a, sr, SR) if sr != SR else a.astype(np.float32)
    a = highpass(a, 65.0)
    a = fft_filter(a, lo=None, hi=10500.0)
    a = normalise(a, 1.0)
    a = reverb(a, mix=REVERB_MIX, tail=0.26, damp=6000.0)
    a = compress(a, 1.25, 0.82)
    a = fade(a, 20.0, "in")
    a = fade(a, 30.0, "out")
    return a.astype(np.float32)


# ---------------------------------------------------------------------------
# generated music bed & Foley (no external assets needed)
# ---------------------------------------------------------------------------
def _env(n: int, attack: float, decay: float, sr: int = SR) -> np.ndarray:
    t = np.arange(n) / sr
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    d = np.exp(-t / max(decay, 1e-4))
    return (a * d).astype(np.float32)


def _tone(freq: float, dur: float, sr: int = SR, kind: str = "sine") -> np.ndarray:
    t = np.arange(int(dur * sr)) / sr
    if kind == "tri":
        return (2 / math.pi * np.arcsin(np.sin(2 * math.pi * freq * t))).astype(np.float32)
    return np.sin(2 * math.pi * freq * t).astype(np.float32)


def music_bed(duration: float, level: float = MUSIC_BED_LEVEL, sr: int = SR) -> np.ndarray:
    """A slow four-note loop on a minor pentatonic, low-passed and ducked.

    Deterministic (fixed seed) so re-renders are byte-comparable for QA.
    """
    n = int(duration * sr)
    out = np.zeros(n + sr * 2, dtype=np.float32)
    notes = [110.0, 130.81, 146.83, 164.81, 146.83, 130.81]
    bar = 2.4
    t = 0.0
    i = 0
    while t < duration:
        f = notes[i % len(notes)]
        for harmonic, amp in ((1.0, 0.55), (2.0, 0.16), (3.0, 0.07)):
            clip = _tone(f * harmonic, min(2.2, duration - t + 0.4), kind="tri") * amp
            clip *= _env(clip.size, 0.35, 1.5)
            start = int(t * sr)
            out[start:start + clip.size] += clip[: max(0, out.size - start)]
        if i % 2 == 0:
            pad = _tone(f * 1.5, 2.0) * 0.18
            pad *= _env(pad.size, 0.5, 1.8)
            start = int(t * sr)
            out[start:start + pad.size] += pad[: max(0, out.size - start)]
        t += bar
        i += 1
    out = fft_filter(out[:n], lo=60.0, hi=2200.0)
    out = normalise(out, 1.0) * level
    return fade(out, 900.0, "in") if out.size else out


def sfx_pop(sr: int = SR) -> np.ndarray:
    n = int(0.16 * sr)
    t = np.arange(n) / sr
    f = 150 + 520 * np.exp(-t * 26)
    ph = 2 * np.pi * np.cumsum(f) / sr
    return (np.sin(ph) * _env(n, 0.002, 0.06)).astype(np.float32)


def sfx_whoosh(sr: int = SR) -> np.ndarray:
    n = int(0.42 * sr)
    rng = np.random.default_rng(11)
    noise = rng.normal(0, 1, n).astype(np.float32)
    sweep = np.linspace(400, 3200, n)
    out = np.zeros(n, dtype=np.float32)
    block = 256
    for i in range(0, n, block):
        seg = noise[i:i + block]
        if seg.size == 0:
            break
        spec = np.fft.rfft(seg, 1024)
        freqs = np.fft.rfftfreq(1024, 1 / sr)
        c = sweep[min(i, n - 1)]
        g = np.exp(-((freqs - c) ** 2) / (2 * (c * 0.55) ** 2))
        out[i:i + seg.size] = np.fft.irfft(spec * g, 1024)[: seg.size]
    return (out * _env(n, 0.06, 0.18)).astype(np.float32)


def sfx_scribble(sr: int = SR) -> np.ndarray:
    n = int(0.55 * sr)
    rng = np.random.default_rng(5)
    noise = rng.normal(0, 1, n).astype(np.float32)
    noise = fft_filter(noise, lo=900.0, hi=5200.0)
    t = np.arange(n) / sr
    amp = (0.55 + 0.45 * np.sin(2 * np.pi * 7.5 * t)) * np.exp(-t * 2.6)
    return (noise * amp).astype(np.float32)


def sfx_tick(sr: int = SR) -> np.ndarray:
    n = int(0.07 * sr)
    t = np.arange(n) / sr
    out = np.sin(2 * np.pi * 1850 * t) * _env(n, 0.001, 0.018)
    return out.astype(np.float32)


def sfx_bell(sr: int = SR) -> np.ndarray:
    n = int(1.1 * sr)
    out = np.zeros(n, dtype=np.float32)
    for f, a in ((880.0, 0.5), (1320.0, 0.22), (1760.0, 0.12), (2640.0, 0.05)):
        out += _tone(f, n / sr) * a * _env(n, 0.004, 0.42)
    return normalise(out, 0.9)


def sfx_boom(sr: int = SR) -> np.ndarray:
    n = int(0.7 * sr)
    t = np.arange(n) / sr
    f = 90 * np.exp(-t * 2.4) + 34
    ph = 2 * np.pi * np.cumsum(f) / sr
    body = np.sin(ph) * _env(n, 0.004, 0.30)
    rng = np.random.default_rng(9)
    crack = fft_filter(rng.normal(0, 1, n).astype(np.float32), hi=900.0) * _env(n, 0.001, 0.08) * 0.4
    return normalise(body + crack, 0.95)


def sfx_crinkle(sr: int = SR) -> np.ndarray:
    n = int(0.32 * sr)
    rng = np.random.default_rng(21)
    noise = fft_filter(rng.normal(0, 1, n).astype(np.float32), lo=1800.0, hi=8000.0)
    t = np.arange(n) / sr
    gate = (np.sin(2 * np.pi * 24 * t) > 0.1).astype(np.float32)
    return (noise * gate * np.exp(-t * 5)).astype(np.float32)


def sfx_pen_tap(sr: int = SR) -> np.ndarray:
    n = int(0.09 * sr)
    t = np.arange(n) / sr
    return (np.sin(2 * np.pi * 640 * t) * _env(n, 0.001, 0.02)).astype(np.float32)


def sfx_twinkle(sr: int = SR) -> np.ndarray:
    parts = []
    for f in (1760.0, 2349.0, 3136.0, 4186.0):
        c = _tone(f, 0.30) * _env(int(0.30 * sr), 0.002, 0.09)
        parts.append(c)
    n = int(0.85 * sr)
    out = np.zeros(n + int(0.3 * sr), dtype=np.float32)
    for i, c in enumerate(parts):
        s = int(i * 0.075 * sr)
        out[s:s + c.size] += c * (0.55 - i * 0.08)
    return normalise(out[:n], 0.7)


_RAW_SFX = {
    "pop": sfx_pop, "whoosh": sfx_whoosh, "scribble": sfx_scribble, "tick": sfx_tick,
    "bell": sfx_bell, "boom": sfx_boom, "crinkle": sfx_crinkle, "pen_tap": sfx_pen_tap,
    "twinkle": sfx_twinkle,
}


def _bounded(fn):
    def wrapped(sr: int = SR) -> np.ndarray:
        return normalise(fn(sr), 0.95)

    wrapped.__name__ = fn.__name__
    return wrapped


SFX = {name: _bounded(fn) for name, fn in _RAW_SFX.items()}


# ---------------------------------------------------------------------------
# the score
# ---------------------------------------------------------------------------
def build_score(
    clips: list[np.ndarray],
    first_start: float,
    gap: float = INTER_LINE_GAP,
    sfx_cues: list[tuple[float, str, float]] | None = None,
    bed_level: float = MUSIC_BED_LEVEL,
) -> tuple[np.ndarray, list[float], list[float]]:
    """Assemble voice clips + bed + sfx into one master.

    Returns (master, onsets, durations). Scene timing is derived from the real
    measured onsets — never guessed (§4).
    """
    clips = [voice_chain(c) for c in clips]
    durations = [c.size / SR for c in clips]
    onsets, t = [], first_start
    for d in durations:
        onsets.append(round(t, 4))
        t += d + gap
    total = t - gap + 0.30

    voice = np.zeros(int(total * SR) + SR, dtype=np.float32)
    for clip, at in zip(clips, onsets):
        voice = place(voice, clip, at, gain=0.92)
    voice = voice[: int(total * SR)]

    bed = music_bed(total, level=bed_level)
    bed = bed[: voice.size]

    # sidechain-ish duck: pull the bed down under every spoken window
    duck = np.ones(voice.size, dtype=np.float32)
    for clip, at in zip(clips, onsets):
        a, b = int(at * SR), int((at + clip.size / SR) * SR)
        duck[a:b] = 0.45
    # smooth the ducking so it does not click
    k = int(0.08 * SR)
    kernel = np.ones(k, dtype=np.float32) / k
    duck = np.convolve(duck, kernel, mode="same").astype(np.float32)
    bed = bed * (0.55 + 0.45 * duck)

    mix = voice + bed
    for cue in sfx_cues or []:
        at, name, gain = cue
        clip = SFX.get(name)
        if clip is None:
            continue
        mix = place(mix, clip(), at, gain=gain * SFX_LEVEL)

    mix = mix[: voice.size]
    if mix.size > int(45.0 * SR):          # hard §2 ceiling, never exceeded
        mix = mix[: int(45.0 * SR)]
    mix = np.tanh(mix * 1.04).astype(np.float32)
    mix = normalise(mix, 0.92)
    mix = fade(mix, 300.0, "out")
    # gentle RMS target
    r = rms(mix)
    if r > 1e-6:
        mix = (mix * min(2.0, 0.20 / r * 0.92)).astype(np.float32)
        mix = normalise(mix, 0.92)
    return mix, onsets, durations


def decode_to_s16(a: np.ndarray, sr_out: int = 16000) -> np.ndarray:
    """QA helper: what a decoder would see, used for the per-cue RMS check."""
    return resample(a, SR, sr_out)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit("dmf.audio is a library. It has no __main__ cues on purpose (MASTER_PROMPT §6).")
