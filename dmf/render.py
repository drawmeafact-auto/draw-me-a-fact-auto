"""Frame pipeline (§6): PIL frames piped as raw RGB24 into ffmpeg over stdin.

No per-frame PNGs — that is ten times slower. ffmpeg always comes from
imageio_ffmpeg, because no system ffmpeg is assumed to exist.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Callable

import json

from .config import AUDIO_BITRATE, BUILD_DIR, FPS, H, MAX_FRAMES, SR, VIDEO_CRF, VIDEO_PRESET, W


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # pragma: no cover
        return "ffmpeg"


def ffprobe_exe() -> str:
    """ffprobe next to the imageio ffmpeg binary, if it ships one."""
    ff = Path(ffmpeg_exe())
    for cand in (ff.with_name("ffprobe"), ff.with_name("ffprobe.exe")):
        if cand.exists():
            return str(cand)
    return "ffprobe"


def probe(path: Path) -> dict:
    """Duration and stream facts, read from the file — never from the script.

    Uses ffprobe when the box has one; otherwise parses the banner ffmpeg always
    prints, because imageio-ffmpeg ships no ffprobe.
    """
    import json
    import re

    path = Path(path)
    try:
        out = subprocess.run(
            [ffprobe_exe(), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
            capture_output=True, text=True,
        )
        if out.returncode == 0 and out.stdout.strip():
            return json.loads(out.stdout)
    except (FileNotFoundError, OSError):
        pass

    banner = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(path)],
                            capture_output=True, text=True).stderr
    info: dict = {"format": {}, "streams": []}
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", banner)
    if m:
        h, mi, se = m.groups()
        info["format"]["duration"] = str(int(h) * 3600 + int(mi) * 60 + float(se))
    info["format"]["size"] = str(path.stat().st_size) if path.exists() else "0"

    for line in banner.splitlines():
        if "Video:" in line:
            v = {"codec_type": "video", "codec_name": line.split("Video:")[1].strip().split()[0].strip(",")}
            r = re.search(r"(\d{2,5})x(\d{2,5})", line)
            if r:
                v["width"], v["height"] = int(r.group(1)), int(r.group(2))
            f = re.search(r"(\d+(?:\.\d+)?)\s*fps", line)
            if f:
                v["avg_frame_rate"] = f"{float(f.group(1)):.0f}/1"
            info["streams"].append(v)
        elif "Audio:" in line:
            a = {"codec_type": "audio", "codec_name": line.split("Audio:")[1].strip().split()[0].strip(",")}
            sr = re.search(r"(\d+)\s*Hz", line)
            if sr:
                a["sample_rate"] = sr.group(1)
            a["channels"] = 2 if "stereo" in line else 1
            info["streams"].append(a)
    return info


def render_frames(
    frame_fn: Callable[[int, float], "object"],
    duration: float,
    out_path: Path,
    fps: int = FPS,
    on_progress: Callable[[float], None] | None = None,
) -> dict:
    """Paint `duration` seconds of frames and encode them to H.264 1080x1920."""
    total_frames = min(MAX_FRAMES, max(1, int(round(duration * fps))))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ff = ffmpeg_exe()
    cmd = [
        ff, "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
        "-an",
        "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-crf", VIDEO_CRF, "-preset", VIDEO_PRESET,
        "-movflags", "+faststart",
        str(out_path),
    ]
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for i in range(total_frames):
            t = i / fps
            img = frame_fn(i, t)
            proc.stdin.write(img.tobytes() if hasattr(img, "tobytes") else bytes(img))
            if on_progress and i % 15 == 0:
                on_progress(i / total_frames)
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
    err = proc.stderr.read().decode("utf-8", "ignore") if proc.stderr else ""
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg encode failed ({rc}): {err[-800:]}")
    return {
        "path": str(out_path),
        "frames": total_frames,
        "seconds": round(time.time() - t0, 2),
        "fps": fps,
    }


def measure_loudness(path: Path) -> dict:
    """Integrated loudness, loudness range and true peak (EBU R128)."""
    import re

    ff = ffmpeg_exe()
    out = subprocess.run(
        [ff, "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True,
    ).stderr
    summary = out.rsplit("Summary:", 1)[-1] if "Summary:" in out else out

    def grab(label: str) -> float | None:
        m = re.search(rf"{label}:\s*(-?\d+(?:\.\d+)?)", summary)
        return float(m.group(1)) if m else None

    return {"i": grab("I"), "lra": grab("LRA"), "true_peak": grab("Peak")}


def loudnorm_two_pass(src: Path, dst: Path, target_i: float = -14.0,
                      target_tp: float = -1.5, target_lra: float = 11.0) -> dict:
    """Broadcast-normalise to Target LUFS. YouTube normalises to -14, so we sit there."""
    import re

    ff = ffmpeg_exe()
    probe_run = subprocess.run(
        [ff, "-hide_banner", "-nostats", "-i", str(src), "-af",
         f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:print_format=json",
         "-f", "null", "-"],
        capture_output=True, text=True,
    )
    blob = re.findall(r'\{[^{}]*"input_i"[^{}]*\}', probe_run.stderr, re.S)
    if not blob:
        subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(src), "-c", "copy", str(dst)], check=True)
        return {"normalised": False, "reason": "loudnorm probe failed"}

    m = json.loads(blob[-1])
    af = (
        f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}"
        f":measured_I={m['input_i']}:measured_TP={m['input_tp']}"
        f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}"
        f":offset={m.get('target_offset', 0)}:linear=true:print_format=summary"
    )
    res = subprocess.run(
        [ff, "-y", "-loglevel", "error", "-i", str(src), "-af", af,
         "-c:v", "copy", "-c:a", "aac", "-b:a", AUDIO_BITRATE,
         "-ar", str(SR), "-ac", "1", "-movflags", "+faststart", str(dst)],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(src), "-c", "copy", str(dst)], check=True)
        return {"normalised": False, "reason": res.stderr.strip()[:200]}
    return {"normalised": True, "target_lufs": target_i, "measured_before": float(m["input_i"]),
            "gain_db": round(target_i - float(m["input_i"]), 2)}


def mux(video: Path, score_wav: Path, out_path: Path) -> Path:
    """The exact mux from §6."""
    ff = ffmpeg_exe()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ff, "-y", "-loglevel", "error",
        "-i", str(video), "-i", str(score_wav),
        "-c:v", "copy", "-c:a", "aac", "-b:a", AUDIO_BITRATE,
        "-shortest", "-movflags", "+faststart",
        str(out_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"mux failed: {res.stderr.strip()[:600]}")
    return out_path


def extract_frame(video: Path, at: float, out_png: Path) -> Path:
    ff = ffmpeg_exe()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [ff, "-y", "-loglevel", "error", "-ss", f"{at:.3f}", "-i", str(video), "-frames:v", "1", str(out_png)],
        check=True,
    )
    return out_png


def decode_mono(video_or_wav: Path, sr: int = 16000) -> "object":
    """Decode the muxed audio to s16le mono at 16 kHz for the per-cue RMS gate."""
    import numpy as np

    ff = ffmpeg_exe()
    res = subprocess.run(
        [ff, "-v", "error", "-i", str(video_or_wav), "-f", "s16le", "-acodec", "pcm_s16le",
         "-ac", "1", "-ar", str(sr), "-"],
        capture_output=True,
    )
    if res.returncode != 0:
        raise RuntimeError("audio decode failed")
    return np.frombuffer(res.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def build_dir() -> Path:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    return BUILD_DIR
