#!/usr/bin/env python3
"""
DRAW ME A FACT (@drawmeafact) — Autonomous Production Studio Engine (v1.0)
Implements MASTER_PROMPT.md end-to-end:
  1. Fact-checked 5-sentence flowing script + growing number ladder (80-110 words, <=45s)
  2. Exact §4 Voice & Audio DSP chain (+12% asetrate, 80Hz-11kHz, 0.05 reverb, tanh comp, Foley SFX + bed)
  3. Exact §5 Hand-Drawn S=2 Supersampled Animator (Paper #fdfdfb, Ink #1a1a1a, Acc #c63a30, Grey #7a7a76)
  4. Exact §7 Deliverables (.mp4, 5-cue .srt, youtube_pack.md, 6-tile QA contact sheet)
  5. Exact §9 Automated QA Gate (ffprobe stream/duration check, 16kHz per-cue RMS > 0.10, margin & SRT checks)
  6. Hands-free Cloud Auto-Upload to YouTube Shorts + optional Instagram Reels (100% free APIs)
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import logging
import math
import os
import random
import re
import shutil
import subprocess
import sys
import textwrap
import time
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import edge_tts
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("drawmeafact")

# ==============================================================================
# 1. LOCKED BRAND & TECHNICAL CONSTANTS (MASTER_PROMPT.md §1, §4, §5, §6)
# ==============================================================================
ROOT_DIR = Path(__file__).resolve().parent
FONTS_DIR = ROOT_DIR / "fonts"
BUILD_DIR = ROOT_DIR / "build"
BRAND_DIR = ROOT_DIR / "brand"
OUTPUT_DIR = ROOT_DIR / "output"
HISTORY_PATH = ROOT_DIR / "episodes_history.json"
MASTER_PROMPT_PATH = ROOT_DIR / "MASTER_PROMPT.md"

W, H = 1080, 1920
S = 2  # Supersample factor (draw at 2160x3840, box-downsample to 1080x1920)
SW, SH = W * S, H * S
FPS = 30
SR = 44100

# Strictly locked 4-colour palette (§5)
PAPER = (253, 253, 251)  # #fdfdfb
INK = (26, 26, 26)       # #1a1a1a
ACC = (198, 58, 48)      # #c63a30
GREY = (122, 122, 118)   # #7a7a76

# Safe margins (§9.6 & §9.7: >120px sides, >160px top, >220px bottom)
SAFE_X0, SAFE_X1 = 132, 948  # width = 816 px
SAFE_Y0, SAFE_Y1 = 176, 1692

# Audio constants (§4 — natural pitch-locked resample + warm studio tone)
FIRST_LINE_START = 0.28
INTER_LINE_GAP = 0.18
VOICE_SPEED_RATIO = 1.00
REVERB_MIX = 0.05
MUSIC_BED_LEVEL = 0.20
SFX_LEVEL = 0.34
MAX_RUNTIME_SEC = 45.0

# Narrator settings — LOCKED TO USER CHOICE: Option 5 (Ryan — Deep UK Documentary Baritone)
PRIMARY_VOICE = os.getenv("DMAF_VOICE", "en-GB-RyanNeural")
VOICE_RATE = os.getenv("DMAF_VOICE_RATE", "-8%")
VOICE_PITCH = os.getenv("DMAF_VOICE_PITCH", "-7Hz")
FALLBACK_VOICES = ["en-GB-ThomasNeural", "en-US-AndrewNeural", "en-US-ChristopherNeural"]

# Scheduling & API environment variables
TARGET_TIMEZONE = os.getenv("TARGET_TIMEZONE", "Asia/Calcutta")
TARGET_PUBLISH_HOUR = int(os.getenv("TARGET_PUBLISH_HOUR", "19"))
TARGET_PUBLISH_MINUTE = int(os.getenv("TARGET_PUBLISH_MINUTE", "0"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "").strip()
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "").strip()
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "").strip()

IG_USER_ID = os.getenv("IG_USER_ID", "").strip()
IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN", "").strip()
PUBLIC_VIDEO_URL = os.getenv("PUBLIC_VIDEO_URL", "").strip()

BALOO_URL = "https://github.com/google/fonts/raw/main/ofl/baloo2/Baloo2%5Bwght%5D.ttf"
MARKER_URL = "https://github.com/google/fonts/raw/main/apache/permanentmarker/PermanentMarker-Regular.ttf"


# ==============================================================================
# 2. PRE-VERIFIED EPISODE SLATE (Starts at EP 11 from §11 + 5 more gold episodes,
#    then seamlessly hands off to unlimited AI generation!)
# ==============================================================================
VERIFIED_SLATE: list[dict[str, Any]] = [
    {
        "slug": "mountains-10km-limit",
        "series": "Scale Check",
        "title": "Why Earth's mountains stop under 10 kilometres",
        "alt_titles": [
            "Gravity crushes any Earth mountain taller than 10 km",
            "Mount Everest is 8.85 km — Earth's rock limit is 10 km",
            "Why Mars has a 22 km mountain and Earth never could",
        ],
        "hook_130": "Mount Everest stands 8.85 km above sea level, perilously close to the 10 km limit where Earth's own gravity crushes granite.",
        "numbers_summary": "4.2 km (Mauna Kea above sea) -> 8.85 km (Mount Everest) -> 10 km (Earth rock-crush ceiling) -> 22 km (Olympus Mons on Mars)",
        "pinned_comment": "If Earth suddenly had Mars gravity tomorrow, which mountain range would you climb first?",
        "tags": "draw me a fact,scale check,mount everest,olympus mons,earth gravity,geology facts,science shorts,physics scale,hand drawn facts,shorts",
        "sentences": [
            "Mount Everest stops at eight point eight five kilometres high, not because plates stopped pushing, but because granite slowly liquefies at the base under its own weight.",
            "Stack rock any higher on Earth and gravity squeezes the bottom crust outward like putty, capping any dry peak near ten kilometres.",
            "Mauna Kea rises four point two kilometres above the waves, Everest climbs to eight point eight five, and ten kilometres is where bedrock gives way.",
            "Yet on Mars, Olympus Mons towers twenty two kilometres high, purely because Martian gravity pulls with thirty eight percent of Earth's strength.",
            "So Everest is not just a tall peak, it is the heaviest stack our planet refuses to sink, so subscribe, and tap like.",
        ],
        "scenes": [
            {
                "icon": "mountain",
                "headline": "EVEREST'S TRUE CEILING",
                "display_number": "8.85 km",
                "target_num": 8.85,
                "unit": "km",
                "caption": "peak elevation above sea level",
            },
            {
                "icon": "weight_crush",
                "headline": "GRANITE UNDER GRAVITY",
                "display_number": "10 km",
                "target_num": 10.0,
                "unit": "km",
                "caption": "bedrock yield ceiling on Earth",
            },
            {
                "icon": "ladder",
                "headline": "CLIMBING THE CEILING",
                "display_number": "10 km",
                "target_num": 10.0,
                "unit": "km",
                "caption": "height above datum in kilometres",
                "ladder": [
                    {"label": "Mauna Kea (dry)", "val": 4.2, "text": "4.2 km"},
                    {"label": "Mt. Everest", "val": 8.85, "text": "8.85 km"},
                    {"label": "Earth Rock Limit", "val": 10.0, "text": "10 km"},
                ],
            },
            {
                "icon": "mars_compare",
                "headline": "38% GRAVITY ON MARS",
                "display_number": "22 km",
                "target_num": 22.0,
                "unit": "km",
                "caption": "Olympus Mons above Mars datum",
                "compare": {"left_name": "Earth Max", "left_val": 10.0, "left_txt": "10 km", "right_name": "Olympus Mons", "right_val": 22.0, "right_txt": "22 km"},
            },
            {
                "icon": "mountain",
                "reframe": "NOT JUST A PEAK — EARTH'S WEIGHT LIMIT",
                "emphasis_word": "WEIGHT LIMIT",
                "ruler_label": "0 km                     10 km                     22 km",
            },
        ],
        "accuracy_table": [
            {"claim": "Mount Everest official elevation", "value": "8,848.86 m (8.85 km)", "source": "2020 China-Nepal Joint Survey / USGS"},
            {"claim": "Mauna Kea elevation above sea level", "value": "4,207 m (4.2 km)", "source": "USGS Hawaiian Volcano Observatory"},
            {"claim": "Theoretical max mountain height on Earth", "value": "~10 km (isostatic/compressive rock strength limit)", "source": "Weisskopf (1975), Science 187:605 'Of Atoms, Mountains, and Stars'"},
            {"claim": "Olympus Mons height & Mars surface gravity", "value": "~21.9 km (~22 km) at 0.38 g", "source": "NASA Mars Orbiter Laser Altimeter (MOLA)"},
        ],
    },
    {
        "slug": "fold-paper-42-times-moon",
        "series": "Fold It",
        "title": "42 folds of one sheet of paper reaches the Moon",
        "alt_titles": [
            "How 42 folds turns 0.1 mm of paper into 440,000 km",
            "Exponential thickness: folding one sheet to the Moon",
            "Why 23 folds of paper is already 838 metres tall",
        ],
        "hook_130": "One sheet of printer paper is 0.1 millimetres thick, yet doubling it 42 times stacks past the Moon.",
        "numbers_summary": "0.1 mm (0 folds) -> 10 cm (10 folds) -> 838 m (23 folds) -> 439,800 km (42 folds, past the Moon)",
        "pinned_comment": "How many folds do you think it takes to reach the Sun? (Hint: surprisingly few more.)",
        "tags": "draw me a fact,fold it,paper folding,exponential growth,distance to moon,math shorts,physics scale,hand drawn animation,shorts",
        "sentences": [
            "A fresh sheet of printer paper is zero point one millimetres thick, thin enough to slip under a locked door.",
            "Every time you fold that sheet in half you double every layer beneath your fingers into pure exponential growth.",
            "Ten folds reaches ten centimetres, twenty three folds towers eight hundred and thirty eight metres past the Burj Khalifa, and thirty folds hits one hundred and seven kilometres.",
            "Fold it a forty second time and your single stack stands four hundred and thirty nine thousand eight hundred kilometres tall, well past the Moon.",
            "So the paper never lacked the reach for space, it only refused to bend past fold seven, so subscribe, and tap like.",
        ],
        "scenes": [
            {
                "icon": "paper",
                "headline": "ONE PRINTER SHEET",
                "display_number": "0.1 mm",
                "target_num": 0.1,
                "unit": "mm",
                "caption": "standard 80 gsm sheet thickness",
            },
            {
                "icon": "fold_layers",
                "headline": "DOUBLING EVERY LAYER",
                "display_number": "10 cm",
                "target_num": 10.0,
                "unit": "cm",
                "caption": "thickness after just 10 folds (1,024 layers)",
            },
            {
                "icon": "ladder",
                "headline": "THE EXPONENTIAL CLIMB",
                "display_number": "107 km",
                "target_num": 107.0,
                "unit": "km",
                "caption": "stack height by fold count",
                "ladder": [
                    {"label": "14 Folds", "val": 1.6, "text": "1.6 m"},
                    {"label": "23 Folds", "val": 45.0, "text": "838 m"},
                    {"label": "30 Folds", "val": 100.0, "text": "107 km"},
                ],
            },
            {
                "icon": "moon_compare",
                "headline": "FOLD NUMBER FORTY-TWO",
                "display_number": "439,800 km",
                "target_num": 439800.0,
                "unit": "km",
                "caption": "0.1 mm x 2^42 vs Moon average 384,400 km",
                "compare": {"left_name": "Moon Orbit", "left_val": 384.4, "left_txt": "384,400 km", "right_name": "42 Folds", "right_val": 439.8, "right_txt": "439,800 km"},
            },
            {
                "icon": "paper",
                "reframe": "NEVER TOO THIN — JUST EXPONENTIAL",
                "emphasis_word": "EXPONENTIAL",
                "ruler_label": "0.1 mm                838 m                439,800 km",
            },
        ],
        "accuracy_table": [
            {"claim": "Standard copy paper caliper", "value": "0.10 mm (100 micrometres)", "source": "ISO 534 Paper Thickness Standard"},
            {"claim": "Thickness at 10, 23, and 30 folds", "value": "102.4 mm, 838.86 m, 107.37 km", "source": "Exact binary power 0.0001 m x 2^n"},
            {"claim": "Thickness at 42 folds", "value": "439,804.65 km", "source": "0.0001 m x 2^42 = 4.398 x 10^8 m"},
            {"claim": "Mean Earth-Moon distance", "value": "384,400 km", "source": "NASA Lunar Fact Sheet"},
        ],
    },
    {
        "slug": "single-cloud-500-tonnes",
        "series": "Wrong By Default",
        "title": "One white cumulus cloud weighs 500 tonnes",
        "alt_titles": [
            "Why a fluffy summer cloud weighs 500,000 kilograms",
            "How 500 tonnes of water floats above your head",
            "A 1 km cumulus cloud weighs as much as 100 elephants",
        ],
        "hook_130": "One fair-weather cumulus cloud holds half a gram of water per cubic metre, adding up to 500 metric tonnes overhead.",
        "numbers_summary": "0.5 g (per cubic metre) -> 500 kg (one bedroom of cloud) -> 50,000 kg (city block slice) -> 500 tonnes (1 km3 cloud)",
        "pinned_comment": "Before watching this, what would you have guessed a single white cloud weighed?",
        "tags": "draw me a fact,wrong by default,cloud weight,atmospheric physics,500 tonnes,weather facts,science shorts,shorts",
        "sentences": [
            "One cubic metre of summer cumulus cloud holds just zero point five grams of water, roughly ten small raindrops.",
            "It looks weightless only because that cloud stretches one kilometre wide, long, and tall across a billion cubic metres of sky.",
            "A bus pocket holds twenty five grams, a stadium carries five hundred kilograms, and one tenth of the cloud already tips fifty metric tonnes.",
            "Measure the whole cubic kilometre together and five hundred metric tonnes of liquid water hangs silently overhead, heavier than three jumbo jets.",
            "So a cloud never floats because it is light, it floats because dry air around it is denser, so subscribe, and tap like.",
        ],
        "scenes": [
            {
                "icon": "cloud",
                "headline": "ONE CUBIC METRE OF CLOUD",
                "display_number": "0.5 g",
                "target_num": 0.5,
                "unit": "g",
                "caption": "liquid water droplets per m3",
            },
            {
                "icon": "cube_grid",
                "headline": "ONE BILLION CUBIC METRES",
                "display_number": "1 km³",
                "target_num": 1.0,
                "unit": "km³",
                "caption": "typical fair-weather cumulus volume",
            },
            {
                "icon": "ladder",
                "headline": "ADDING UP THE MIST",
                "display_number": "50 t",
                "target_num": 50.0,
                "unit": "tonnes",
                "caption": "water mass as cloud volume scales",
                "ladder": [
                    {"label": "City Bus Box", "val": 8.0, "text": "25 g"},
                    {"label": "Stadium Box", "val": 38.0, "text": "500 kg"},
                    {"label": "1/10th Cloud", "val": 100.0, "text": "50 tonnes"},
                ],
            },
            {
                "icon": "mars_compare",
                "headline": "ONE WHOLE CUMULUS CLOUD",
                "display_number": "500 tonnes",
                "target_num": 500.0,
                "unit": "tonnes",
                "caption": "500,000 kg of suspended micro-droplets",
                "compare": {"left_name": "Boeing 747", "left_val": 183.0, "left_txt": "183 t", "right_name": "One Cloud", "right_val": 500.0, "right_txt": "500 t"},
            },
            {
                "icon": "cloud",
                "reframe": "NOT LIGHT — JUST SPREAD ACROSS A SKY",
                "emphasis_word": "500 TONNES",
                "ruler_label": "0.5 g                  500 kg                  500 tonnes",
            },
        ],
        "accuracy_table": [
            {"claim": "Cumulus liquid water content (LWC)", "value": "~0.5 g/m3", "source": "NOAA / National Center for Atmospheric Research (NCAR) Peggy LeMone measurement"},
            {"claim": "Typical fair-weather cumulus dimensions", "value": "~1 km x 1 km x 1 km (10^9 m3)", "source": "USGS Water Science School / NCAR"},
            {"claim": "Total liquid water mass", "value": "5 x 10^8 g = 500,000 kg (500 metric tonnes)", "source": "NCAR / USGS consensus calculation"},
        ],
    },
    {
        "slug": "cotton-tshirt-2700-litres",
        "series": "Cost Of One",
        "title": "One cotton T-shirt takes 2,700 litres of water",
        "alt_titles": [
            "Why there are 2,700 litres of water inside one T-shirt",
            "One 250-gram cotton shirt = 900 days of drinking water",
            "The hidden water ledger inside a single cotton shirt",
        ],
        "hook_130": "A plain cotton T-shirt weighs 250 grams on your shoulders, yet growing and dyeing its fibres took 2,700 litres of water.",
        "numbers_summary": "250 g (shirt mass) -> 200 litres (processing & dyeing) -> 1,200 litres (irrigation mid-season) -> 2,700 litres (total footprint)",
        "pinned_comment": "Look at the shirt you are wearing right now — cotton or polyester?",
        "tags": "draw me a fact,cost of one,water footprint,cotton tshirt,2700 litres,sustainability facts,numbers,shorts",
        "sentences": [
            "A plain white cotton T-shirt weighs two hundred and fifty grams dry, yet almost none of the water that made it stays inside.",
            "Cotton bolls transpire water through sunlit leaves for five straight months long before a spinning mill touches a thread.",
            "Bleaching and dyeing drinks two hundred litres, half the harvest takes twelve hundred, and one finished shirt climbs to two thousand seven hundred litres.",
            "At three litres of drinking water per day, that single folded shirt in your drawer holds nine hundred days of human hydration.",
            "So the tag shows what the cloth cost at the counter, never what the river paid first, so subscribe, and tap like.",
        ],
        "scenes": [
            {
                "icon": "tshirt",
                "headline": "ONE DRY COTTON SHIRT",
                "display_number": "250 g",
                "target_num": 250.0,
                "unit": "g",
                "caption": "finished garment dry fabric weight",
            },
            {
                "icon": "water",
                "headline": "DYEHOUSE + MILL WATER",
                "display_number": "200 L",
                "target_num": 200.0,
                "unit": "litres",
                "caption": "scouring, bleaching & wet processing",
            },
            {
                "icon": "ladder",
                "headline": "THE WATER LEDGER",
                "display_number": "2,700 L",
                "target_num": 2700.0,
                "unit": "litres",
                "caption": "cumulative virtual water per shirt",
                "ladder": [
                    {"label": "Mill & Dye", "val": 12.0, "text": "200 L"},
                    {"label": "Half Harvest", "val": 50.0, "text": "1,200 L"},
                    {"label": "Full Shirt", "val": 100.0, "text": "2,700 L"},
                ],
            },
            {
                "icon": "mars_compare",
                "headline": "DRINKING WATER EQUIVALENT",
                "display_number": "900 days",
                "target_num": 900.0,
                "unit": "days",
                "caption": "at 3 litres of drinking water per day",
                "compare"
