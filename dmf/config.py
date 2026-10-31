"""Locked brand, audio and technical constants (MASTER_PROMPT.md §1, §4, §5, §6)."""

from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
FONTS_DIR = ROOT_DIR / "fonts"
BUILD_DIR = ROOT_DIR / "build"
BRAND_DIR = ROOT_DIR / "brand"
OUTPUT_DIR = ROOT_DIR / "output"
HISTORY_PATH = Path(os.getenv("DMAF_HISTORY", ROOT_DIR / "episodes_history.json"))
MASTER_PROMPT_PATH = ROOT_DIR / "MASTER_PROMPT.md"
EPISODES_HISTORY_IN_WORKFLOWS = ROOT_DIR / ".github" / "workflows" / "episodes_history.json"

# Canvas (§5, §6)
W, H = 1080, 1920
S = 2  # internal supersample: draw at 2x, box-downsample on finish
SW, SH = W * S, H * S
FPS = 30
SR = 44100

# Palette — these four values only (§5)
PAPER = (253, 253, 251)  # #fdfdfb
INK = (26, 26, 26)       # #1a1a1a
ACC = (198, 58, 48)      # #c63a30
GREY = (122, 122, 118)   # #7a7a76

# Safe area (§9.6, §9.7): 120px sides, 160px top, 220px bottom
SAFE_X0, SAFE_X1 = 132, 948
SAFE_Y0, SAFE_Y1 = 176, 1692

# Audio (§4)
FIRST_LINE_START = 0.28
INTER_LINE_GAP = 0.18
VOICE_SPEED_RATIO = 1.0
REVERB_MIX = 0.05
MUSIC_BED_LEVEL = 0.20
SFX_LEVEL = 0.34
MAX_RUNTIME_SEC = 45.0
TARGET_PEAK = 0.92
TARGET_MIX_RMS = 0.20
TARGET_ATTEMPO_RUNTIME = 43.8

# Narrator — locked (§4)
PRIMARY_VOICE = os.getenv("DMAF_VOICE", "en-GB-RyanNeural")
VOICE_RATE = os.getenv("DMAF_VOICE_RATE", "-8%")
VOICE_PITCH = os.getenv("DMAF_VOICE_PITCH", "-7Hz")
FALLBACK_VOICES = ["en-GB-ThomasNeural", "en-US-AndrewNeural", "en-US-ChristopherNeural"]

# Encoding (§6)
VIDEO_CRF = "18"
VIDEO_PRESET = "medium"
AUDIO_BITRATE = "192k"

FONT_BALOO = FONTS_DIR / "baloo2.ttf"
FONT_MARKER = FONTS_DIR / "pm.ttf"
BALOO_URL = "https://github.com/google/fonts/raw/main/ofl/baloo2/Baloo2%5Bwght%5D.ttf"
MARKER_URL = "https://github.com/google/fonts/raw/main/apache/permanentmarker/PermanentMarker-Regular.ttf"

# ---------------------------------------------------------------------------
# Runtime configuration (all optional; the engine degrades gracefully)
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "").strip()
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "").strip()
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "").strip()
IG_USER_ID = os.getenv("IG_USER_ID", "").strip()
IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN", "").strip()
PUBLIC_VIDEO_URL = os.getenv("PUBLIC_VIDEO_URL", "").strip()

TARGET_TIMEZONE = os.getenv("TARGET_TIMEZONE", "Asia/Calcutta")
TARGET_PUBLISH_HOUR = int(os.getenv("TARGET_PUBLISH_HOUR", "19"))
TARGET_PUBLISH_MINUTE = int(os.getenv("TARGET_PUBLISH_MINUTE", "0"))

# Hard ceiling on rendered frames — protects the connector from runaway jobs.
MAX_FRAMES = int(os.getenv("DMAF_MAX_FRAMES", str(FPS * 45)))

PUBLISH_MODES = ("dry_run", "private", "unlisted", "public_now", "schedule_target")


def ensure_dirs() -> None:
    for d in (FONTS_DIR, BUILD_DIR, BRAND_DIR, OUTPUT_DIR):
        d.mkdir(parents=True, exist_ok=True)
