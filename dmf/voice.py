"""Voiceover: edge-tts narration with measured durations (§4).

Three tiers, tried in order:

1. edge-tts  — the locked `en-GB-RyanNeural` voice (rate -8%, pitch -7Hz)
2. gTTS      — only if edge-tts is unavailable and gtts is installed
3. placeholder — a syllable-shaped narration bed so the film still renders and
   every timing is real. Clearly labelled `voice_source="placeholder"` so nobody
   ships it by accident.

Nothing here guesses a duration: the MP3 is decoded to WAV and measured with
ffprobe/wave before any scene timing is written.
"""

from __future__ import annotations

import asyncio
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import audio
from .config import PRIMARY_VOICE, SR, VOICE_PITCH, VOICE_RATE

try:  # optional dependency
    import edge_tts  # type: ignore
except Exception:  # pragma: no cover
    edge_tts = None

try:
    from gtts import gTTS  # type: ignore
except Exception:  # pragma: no cover
    gTTS = None


@dataclass
class VoiceLine:
    index: int
    text: str
    path: Path
    duration: float
    source: str
    origin: Path | None = None   # file to re-decode from when time-stretching


def _ffmpeg() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # pragma: no cover
        return "ffmpeg"


def _decode(mp3: Path, out_wav: Path, speed: float = 1.0) -> Path:
    """MP3 -> mono 44.1 kHz WAV. No pitch shift: resample only."""
    ff = _ffmpeg()
    filters = ["aresample=44100"]
    if abs(speed - 1.0) > 0.005:
        filters.append(f"atempo={speed:.4f}")
    cmd = [ff, "-y", "-loglevel", "error", "-i", str(mp3), "-ac", "1", "-ar", "44100",
           "-af", ",".join(filters), str(out_wav)]
    subprocess.run(cmd, check=True)
    return out_wav


async def _edge_save(text: str, voice: str, out: Path, rate: str, pitch: str) -> None:
    assert edge_tts is not None
    comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await comm.save(str(out))


def _edge_synth(text: str, out: Path, voice: str, rate: str, pitch: str) -> None:
    loop = None
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None:  # we are inside an event loop (e.g. ASGI)
        import nest_asyncio  # type: ignore

        nest_asyncio.apply()
        loop.run_until_complete(_edge_save(text, voice, out, rate, pitch))
    else:
        asyncio.run(_edge_save(text, voice, out, rate, pitch))


def _placeholder(text: str, out_wav: Path) -> None:
    """Syllable-shaped narration bed. Not speech — a timing stand-in."""
    words = max(1, len(text.split()))
    # a documentary read lands near 2.4 words/second; match it so placeholder
    # timings exercise the same windows a real take will
    dur = max(2.4, min(9.5, words / 2.4))
    n = int(dur * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(len(text))
    f0 = 104 + rng.uniform(-4, 4)
    contour = f0 * (1 + 0.06 * np.sin(2 * np.pi * 0.7 * t) + 0.03 * np.sin(2 * np.pi * 2.3 * t))
    ph = 2 * np.pi * np.cumsum(contour) / SR
    sig = np.sin(ph) * 0.5 + np.sin(2 * ph) * 0.18 + np.sin(3 * ph) * 0.08
    syllables = np.zeros(n)
    pos = 0.05
    while pos < dur - 0.12:
        ln = rng.uniform(0.10, 0.22)
        a, b = int(pos * SR), int(min(dur, pos + ln) * SR)
        if b > a:
            syllables[a:b] = 1.0
        pos += ln + rng.uniform(0.03, 0.10)
    k = int(0.045 * SR)
    if k > 1:
        syllables = np.convolve(syllables, np.ones(k) / k, mode="same")
    sig = (sig * syllables).astype(np.float32)
    audio.write(out_wav, audio.normalise(sig, 0.8), SR)


def synth_lines(sentences: list[str], workdir: Path, voice: str = PRIMARY_VOICE) -> list[VoiceLine]:
    """Exactly one clip per sentence — never split a sentence across clips (§4)."""
    workdir.mkdir(parents=True, exist_ok=True)
    lines: list[VoiceLine] = []
    want_speed = 1.0

    for i, text in enumerate(sentences, start=1):
        mp3 = workdir / f"line{i:02d}.mp3"
        wav = workdir / f"line{i:02d}.wav"
        source = "edge-tts"
        ok = False

        if edge_tts is not None:
            for v in [voice, "en-GB-ThomasNeural", "en-US-AndrewNeural"]:
                try:
                    _edge_synth(text, mp3, v, VOICE_RATE, VOICE_PITCH)
                    _decode(mp3, wav, want_speed)
                    ok = True
                    source = f"edge-tts:{v}"
                    break
                except Exception:
                    continue

        if not ok and gTTS is not None:
            try:
                gTTS(text=text, lang="en", tld="co.uk").save(str(mp3))
                _decode(mp3, wav, want_speed)
                ok = True
                source = "gtts"
            except Exception:
                ok = False

        if not ok:
            _placeholder(text, wav)
            source = "placeholder"

        data = audio.load_audio(wav)
        lines.append(VoiceLine(i, text, wav, data.size / SR, source,
                               origin=mp3 if source.startswith(("edge-tts", "gtts")) else None))

    return lines


AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".opus"}


def lines_from_files(paths: list[Path], workdir: Path) -> list[VoiceLine]:
    """Wrap already-generated narration: one audio file per sentence, in order.

    Used when the operator (or another tool) supplies the voiceover. Every file
    is normalised to 44.1 kHz mono WAV and *measured*, so scene timing still
    comes from real audio and §4's "derive timing, never guess" holds.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    lines: list[VoiceLine] = []
    for i, src in enumerate(paths, start=1):
        src = Path(src)
        if src.suffix.lower() not in AUDIO_SUFFIXES:
            raise ValueError(f"unsupported audio file: {src.name}")
        wav = workdir / f"line{i:02d}.wav"
        try:
            _decode(src, wav)          # ffmpeg reads wav, mp3, m4a and everything else
        except Exception:
            wav = src                  # already a clean PCM wav
        data = audio.load_audio(wav)
        lines.append(VoiceLine(i, "", wav, data.size / SR, "provided", origin=src))
    return lines


def enforce_runtime(lines: list[VoiceLine], workdir: Path, max_runtime: float = 45.0) -> float:
    """§4: only if the film would exceed 43.8 s, speed up pitch-locked (atempo)."""
    from .config import FIRST_LINE_START, INTER_LINE_GAP, TARGET_ATTEMPO_RUNTIME

    total = FIRST_LINE_START + sum(l.duration for l in lines) + INTER_LINE_GAP * (len(lines) - 1)
    if total <= TARGET_ATTEMPO_RUNTIME:
        return 1.0
    target_speech = TARGET_ATTEMPO_RUNTIME - FIRST_LINE_START - INTER_LINE_GAP * (len(lines) - 1)
    speech = sum(l.duration for l in lines)
    speed = max(1.0, min(1.35, speech / max(0.1, target_speech)))
    if speed <= 1.001:
        return 1.0
    for line in lines:
        if line.source != "placeholder":
            src = line.origin or line.path
            if not Path(src).exists():
                continue
            try:
                _decode(Path(src), line.path, speed)
                line.duration = audio.load_audio(line.path).size / SR
            except Exception:
                continue
        else:
            # placeholder: tighten it the same way so the mix never gets clipped
            try:
                data = audio.load_audio(line.path)
                n_to = max(1, int(data.size / speed))
                squeezed = np.interp(
                    np.linspace(0, data.size, n_to, endpoint=False),
                    np.arange(data.size),
                    data,
                ).astype(np.float32)
                audio.write(line.path, squeezed, SR)
                line.duration = squeezed.size / SR
            except Exception:
                continue
    return speed
