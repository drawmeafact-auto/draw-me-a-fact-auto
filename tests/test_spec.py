"""Spec tests: these encode MASTER_PROMPT.md rules so a future edit cannot quietly break them."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from dmf import audio, deliver, script, voice
from dmf.config import FPS, H, REVERB_MIX, SR, W
from dmf.kit import Canvas, fit_font, heart_points, marker_stack
from dmf.qa_gate import run_checks
from dmf.pipeline import plan_scene_windows
from dmf.scenes import format_number, scene_kind
from dmf.slate import VERIFIED_SLATE, find_episode, next_from_slate

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# script contract (§3)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("ep", VERIFIED_SLATE, ids=lambda e: f"ep{e['ep']}")
def test_every_slate_episode_meets_script_contract(ep):
    assert script.validate_script(ep) == []


@pytest.mark.parametrize("ep", VERIFIED_SLATE, ids=lambda e: f"ep{e['ep']}")
def test_every_slate_episode_has_five_scenes_and_sources(ep):
    assert len(ep["sentences"]) == 5
    assert len(ep["scenes"]) == 5
    assert all(row["source"].strip() for row in ep["accuracy_table"])


def test_slate_episode_numbers_are_unique():
    numbers = [e["ep"] for e in VERIFIED_SLATE]
    assert len(numbers) == len(set(numbers))


def test_validate_script_catches_digits_and_missing_ask():
    bad = {
        "sentences": ["A 42 km mountain."] * 5,
        "scenes": [{}] * 5,
        "accuracy_table": [{"claim": "x", "value": "1", "source": ""}],
    }
    problems = script.validate_script(bad)
    assert any("digits" in p for p in problems)
    assert any("carry the ask" in p for p in problems)
    assert any("sourced" in p or "unsourced" in p for p in problems)


def test_digits_to_words_does_not_leave_digits():
    assert script.digits_to_words("42 folds") == "forty-two folds"
    assert script.digits_to_words("2,700 litres") == "two thousand seven hundred litres"
    assert script.digits_to_words("8.85 km") == "eight point eight five km"
    assert not any(ch.isdigit() for ch in script.digits_to_words("20 km and 1,200 tonnes"))


def test_episode_zero_is_not_treated_as_missing():
    """Regression: episode 0 exists (the sample) and must not fall back to 'next'."""
    assert find_episode("0")["ep"] == 0
    assert int(find_episode("0").get("ep")) == 0


def test_connector_queue_skips_samples():
    from connector import tools

    pending = tools.list_episodes()["next_in_queue"]
    assert pending["episode"] == 11, pending
    assert pending["sample"] is False


def test_sample_episodes_never_auto_queue():
    assert next_from_slate(set())["ep"] == 11
    for ep in VERIFIED_SLATE:
        if ep["ep"] == 0:
            assert ep.get("sample") is True


def test_slate_lookup_and_queue():
    assert find_episode("11")["slug"] == "mountains-10km-limit"
    assert find_episode("fold-paper-42-times-moon")["ep"] == 12
    assert find_episode("does-not-exist") is None
    queued = next_from_slate({"million-vs-billion-seconds"})
    assert queued is not None


# ---------------------------------------------------------------------------
# drawing rules (§5)
# ---------------------------------------------------------------------------
def test_heart_is_parametric_not_a_blob():
    pts = heart_points(0, 0, 10.0)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    # a real heart is wider than tall and has two lobes up top
    assert max(xs) - min(xs) > max(ys) - min(ys) * 0.5
    assert len(pts) >= 100


def test_marker_stack_returns_its_own_size():
    layer, w, h = marker_stack(size=80)
    assert w > 0 and h > 0
    assert layer.size == (w * 2, h * 2)  # drawn at S=2
    assert layer.mode == "RGBA"


def test_fit_font_fits_the_box_not_just_the_width():
    c = Canvas()
    small = fit_font(c.draw, "10 km", 800, 100, lo=40, hi=200, max_lines=1)
    huge = fit_font(c.draw, "10 km", 800, 600, lo=40, hi=200, max_lines=1)
    assert huge.size >= small.size
    assert small.size <= 200


def test_reverb_mix_is_locked_low():
    assert REVERB_MIX <= 0.08


def test_canvas_finishes_at_broadcast_size():
    c = Canvas()
    assert c.img.size == (W * 2, H * 2)
    out = c.finish()
    assert out.size == (W, H)
    assert out.mode == "RGB"


def test_scene_kinds_follow_script_structure():
    ep = find_episode("11")
    kinds = [scene_kind(s, i, 5) for i, s in enumerate(ep["scenes"])]
    assert kinds == ["hook", "hook", "ladder", "compare", "end"]


def test_windows_are_derived_from_measured_audio():
    onsets = [0.28, 5.0, 10.0, 15.0, 20.0]
    durations = [4.5, 4.8, 4.8, 4.8, 5.0]
    windows = plan_scene_windows([{}] * 5, onsets, durations)
    assert windows[0]["start"] == 0.0
    assert windows[-1]["end"] > 25.0
    for a, b in zip(windows, windows[1:]):
        assert a["end"] == pytest.approx(b["start"], abs=0.01)


def test_number_formatting_keeps_units():
    assert "km" in format_number(8.85, "km")
    assert "," in format_number(439800, "km")


# ---------------------------------------------------------------------------
# audio chain (§4)
# ---------------------------------------------------------------------------
def test_chain_order_matches_the_spec_table():
    src = inspect.getsource(audio.voice_chain)
    order = ["highpass", "fft_filter", "normalise", "reverb", "compress", "fade"]
    positions = [src.index(fn) for fn in order]
    assert positions == sorted(positions)


def test_compression_is_the_locked_formula():
    x = np.linspace(-1, 1, 1000).astype(np.float32)
    np.testing.assert_allclose(audio.compress(x), np.tanh(x * 1.25) * 0.82, rtol=1e-6)


def test_voice_chain_output_is_sane():
    t = np.linspace(0, 1.0, SR, endpoint=False)
    tone = (0.4 * np.sin(2 * np.pi * 180 * t)).astype(np.float32)
    out = audio.voice_chain(tone)
    assert out.dtype == np.float32
    assert 0 < audio.rms(out) < 0.9
    assert np.max(np.abs(out)) <= 1.0


def test_build_score_respects_the_45_second_ceiling():
    clip = np.zeros(int(9.0 * SR), dtype=np.float32)
    clip[::200] = 0.5
    mix, onsets, durations = audio.build_score([clip] * 5, 0.28)
    assert mix.size / SR <= 45.0
    assert onsets[0] == pytest.approx(0.28)
    assert len(onsets) == 5 == len(durations)


def test_audio_module_refuses_to_run_bare():
    with pytest.raises(SystemExit):
        import runpy

        runpy.run_module("dmf.audio", run_name="__main__")


def test_sfx_generators_are_bounded():
    for name, fn in audio.SFX.items():
        sig = fn()
        assert sig.size > 0, name
        assert np.max(np.abs(sig)) <= 1.0 + 1e-6, name


# ---------------------------------------------------------------------------
# deliverables (§7)
# ---------------------------------------------------------------------------
def test_srt_has_five_cues_spanning_their_sentences(tmp_path):
    ep = find_episode("11")
    onsets = [0.28, 8.0, 16.0, 24.0, 32.0]
    durations = [7.5, 7.8, 7.8, 7.8, 8.0]
    out = deliver.write_srt(ep["sentences"], onsets, durations, tmp_path / "a.srt")
    text = out.read_text(encoding="utf-8")
    assert text.count("-->") == 5
    assert "00:00:00,280" in text
    for block in text.strip().split("\n\n"):
        body = block.split("\n")[2:]
        assert all(len(line) <= 42 for line in body if line)


def test_youtube_pack_contains_every_required_block(tmp_path):
    ep = find_episode("11")
    out = deliver.write_youtube_pack(
        ep, [0.28, 8, 16, 24, 32], [7.5] * 5, 40.0, tmp_path / "pack.md"
    )
    text = out.read_text(encoding="utf-8")
    for needle in ["## 1. Title", "## 2. Alternative titles", "## 3. Description",
                   "## 4. Tags", "## 5. Pinned comment", "## 6. Accuracy table"]:
        assert needle in text
    assert "/500 characters" in text


def test_tags_stay_under_500_characters(tmp_path):
    ep = dict(find_episode("11"))
    ep["tags"] = ", ".join(f"tag{i}" for i in range(200))
    out = deliver.write_youtube_pack(ep, [0.28, 8, 16, 24, 32], [7.5] * 5, 40.0, tmp_path / "p.md")
    line = [l for l in out.read_text().splitlines() if l.startswith("tag0")][0]
    assert len(line) <= 500


# ---------------------------------------------------------------------------
# QA gate (§9)
# ---------------------------------------------------------------------------
def test_qa_gate_reports_missing_file_as_failure(tmp_path):
    result = run_checks(tmp_path / "nope.mp4", [], [], [])
    assert result["passed"] is False


def test_qa_gate_accepts_the_shipped_film():
    video = ROOT / "output" / "latest_episode.mp4"
    timings = sorted((ROOT / "build").glob("*/timing.json")) if (ROOT / "build").exists() else []
    if not video.exists() or not timings:
        pytest.skip("no rendered film in this checkout")
    data = json.loads(timings[-1].read_text())
    result = run_checks(video, data["onsets"], data["durations"], data.get("sentences", []))
    assert result["passed"] is True, result["rows"]


# ---------------------------------------------------------------------------
# connector surface
# ---------------------------------------------------------------------------
def test_manifest_matches_registered_tools():
    from connector import tools

    manifest = json.loads((ROOT / "connector" / "manifest.json").read_text())
    names = {t["name"] for t in manifest["tools"]}
    assert names <= set(tools.TOOLS)
    assert manifest["transport"]["endpoint"] == "/mcp"


def test_connector_tools_are_read_only_safe():
    from connector import tools

    info = tools.describe_studio()
    assert info["channel"]["runtime_ceiling_seconds"] == 45
    assert tools.get_episode("11")["contract_passed"] is True
    assert "episodes" in tools.list_episodes()
    with pytest.raises(ValueError):
        tools.get_episode("nope")


def test_voice_synth_falls_back_to_placeholder_when_offline(tmp_path, monkeypatch):
    monkeypatch.setattr(voice, "edge_tts", None)
    monkeypatch.setattr(voice, "gTTS", None)
    lines = voice.synth_lines(["One short sentence about paper."], tmp_path)
    assert len(lines) == 1
    assert lines[0].source == "placeholder"
    assert lines[0].duration > 0.5
