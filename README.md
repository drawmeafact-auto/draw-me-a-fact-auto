# Draw Me a Fact — Auto Studio

Autonomous production studio for **@drawmeafact**, a YouTube Shorts channel that
tells one true number per episode, hand-drawn on paper, in under 45 seconds.

The studio writes the five-sentence script, generates the voiceover, animates
every frame, mixes the audio, muxes the film, runs a QA gate, and prepares the
upload package — and it is exposed as an **MCP connector**, so a model can drive
all of it through tools.

[![Connector CI](https://github.com/drawmeafact-auto/draw-me-a-fact-auto/actions/workflows/connector_ci.yml/badge.svg)](https://github.com/drawmeafact-auto/draw-me-a-fact-auto/actions/workflows/connector_ci.yml)

---

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python draw_me_a_fact.py --list-slate                   # what is queued
python draw_me_a_fact.py --episode 11 --publish-mode dry_run
```

That writes:

```
output/latest_episode.mp4      the film (1080x1920, 30 fps, H.264 + AAC)
output/latest_episode.srt      five cues, one per sentence
output/youtube_pack.md         title, alternatives, description, tags, pinned comment, sources
output/qa_sheet.png            contact sheet: one frame per scene + the final frame
```

## Run it as a connector

```bash
pip install -r requirements-connector.txt
python -m connector.http_server --host 0.0.0.0 --port 8765
```

| Endpoint | Purpose |
|---|---|
| `POST /mcp` | MCP streamable HTTP — the connector transport |
| `GET /.well-known/ai-connector.json` | registration manifest |
| `GET /tools` | JSON tool index with input schemas |
| `POST /tools/{name}` | invoke a tool (for non-MCP clients) |
| `GET /healthz` | liveness probe |

Eight tools: `describe_studio`, `list_episodes`, `get_episode`, `plan_script`,
`produce_episode`, `run_qa`, `list_assets`, `score_info`.

**Full registration walkthrough — Arena, Claude, Cursor, custom GPTs, n8n:
[`CONNECTOR_INSTALL.md`](CONNECTOR_INSTALL.md).**

---

## How an episode is made

| Stage | What happens |
|---|---|
| **Script** | five long sentences, one per scene, 80–110 words, every number spoken as words (`dmf/script.py`) |
| **Voice** | `edge-tts` `en-GB-RyanNeural`, rate −8 %, pitch −7 Hz (`dmf/voice.py`) |
| **Score** | high-pass 65 Hz → low-pass 10.5 kHz → normalise → reverb 0.05 → `tanh(1.25x)·0.82` → 20 ms fade, plus a generated music bed and Foley (`dmf/audio.py`) |
| **Frames** | PIL at 2× supersample, hand-drawn wobble strokes, piped as raw RGB24 into ffmpeg — no per-frame PNGs (`dmf/scenes.py`, `dmf/render.py`) |
| **Timing** | scene windows are fractions of each sentence's *measured* audio, so the film re-times itself when the voice changes |
| **QA gate** | duration ≤ 45 s, 1080×1920, 30 fps, AAC mono, voice RMS > 0.10 at every cue, no digits in the script, safe margins (`dmf/qa_gate.py`) |
| **Publish** | YouTube Shorts (scheduled/private/unlisted/public) and optional Instagram Reels (`dmf/publish.py`) |

A film is never reported as finished until the QA gate passes.

## Repository layout

```
dmf/                 the engine
  config.py          locked brand, audio and technical constants
  slate.py           pre-verified episodes with sourced accuracy tables
  script.py          script generation + the five-sentence contract
  voice.py           TTS with measured durations (edge-tts → gTTS → placeholder)
  audio.py           the DSP chain, music bed, Foley, score assembly
  kit.py             canvas, wobble strokes, type fitting, wordmark, heart
  icons.py           hand-drawn icon set
  scenes.py          the frame painters (hook, ladder, compare, end card)
  render.py          ffmpeg piping, mux, probing, frame extraction
  deliver.py         SRT, youtube_pack.md, contact sheet, IG caption
  qa_gate.py         the QA gate
  publish.py         YouTube / Instagram upload
  pipeline.py        the production run
connector/           the connector surface
  server.py          MCP server (stdio / streamable HTTP / SSE)
  http_server.py     manifest + JSON tools + MCP in one app
  tools.py           the single source of truth for every tool
  manifest.json      the registration manifest
draw_me_a_fact.py    CLI (and the workflow entry point)
tests/test_spec.py   spec tests that lock the rules in place
```

## CLI

```
--publish-mode MODE   dry_run | private | unlisted | public_now | schedule_target
--episode N|SLUG      use a pre-verified slate episode
--topic "..."         draft a new episode (needs GEMINI_API_KEY or GROQ_API_KEY)
--no-render           plan script + voice + timing only
--list-slate          show the slate and what has shipped
--qa FILM.mp4         re-run the QA gate on an existing film
--publish-ig-only     post the last render to Instagram Reels
```

Exit codes: `0` ok · `1` production or QA failure · `2` bad arguments.

## Automation

`.github/workflows/publish_episode.yml` runs daily at 12:45 UTC (6:15 PM IST),
publishes at 19:00 IST, and can be dispatched by hand with a topic or an episode
number. `.github/workflows/connector_ci.yml` runs the spec tests, validates the
manifest, boots the connector and calls a tool over MCP on every push.

## Design rules (locked)

`MASTER_PROMPT.md` is the channel's constitution — five sentences, no title card,
one number that only grows, no harm thresholds, the ask inside the final
sentence, four colours, two typefaces. The tests in `tests/test_spec.py` fail if
an edit breaks one of them.

## Licence

MIT.
