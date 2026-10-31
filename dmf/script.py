"""Script generation (§3).

Order of preference:

1. the pre-verified slate (deterministic, fact-checked, §11)
2. Gemini (if GEMINI_API_KEY) to write a new five-sentence episode to spec
3. Groq   (if GROQ_API_KEY)
4. the topic bank, used only to suggest a topic for the operator

The §3 shape is enforced, not hoped for: five sentences, one per scene, no
full stop inside a sentence, 80-110 words, and every number written as words.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .config import GEMINI_API_KEY, GROQ_API_KEY

NUMBER_WORDS = {
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six",
    "7": "seven", "8": "eight", "9": "nine", "10": "ten", "11": "eleven", "12": "twelve",
    "13": "thirteen", "14": "fourteen", "15": "fifteen", "20": "twenty", "30": "thirty",
    "40": "forty", "50": "fifty", "100": "one hundred", "1000": "one thousand",
}

SYSTEM_PROMPT = """You are the sole producer of a YouTube Shorts channel called Draw Me a Fact.
Write ONE episode as strict JSON. Rules that are never traded away:

- Exactly five sentences, one per scene. Sentences are long and flowing, built
  from commas, em dashes and relative clauses, with NO full stop inside.
- Sentence 1 = claim + number. 2 = mechanism. 3 = scale ladder, climbing.
  4 = the turn nobody expects. 5 = reframe + "so subscribe, and tap like".
- 80-110 words total. Deadpan, curious, never excited.
- Every number is written as words ("eight point eight five", "twenty four thousand").
- One number that only grows. Never imply a harm threshold. No politics, gore,
  medical advice, real named people.

Return only JSON:
{"slug","series","title","alt_titles":[3],"hook_130","numbers_summary","pinned_comment",
 "tags","sentences":[5],"scenes":[5],"accuracy_table":[{"claim","value","source"}],
 "voice_script":[5]}
Scene objects use keys: icon (mountain|weight_crush|cloud|cube_grid|paper|fold_layers|tshirt|water|atom),
headline, display_number, target_num, unit, caption; the third may add "ladder":[{"label","val","text"}];
the fourth may add "compare":{"left_name","left_val","left_txt","right_name","right_val","right_txt"};
the fifth uses reframe, emphasis_word, ruler_label.
Series must be one of: Fold It, Scale Check, Wrong By Default, Tiny Machines, Cost Of One.
"""


def _call_gemini(topic: str) -> dict | None:
    import requests

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    )
    body = {
        "contents": [{"parts": [{"text": f"{SYSTEM_PROMPT}\n\nTopic: {topic}"}]}],
        "generationConfig": {"temperature": 0.7, "responseMimeType": "application/json"},
    }
    try:
        r = requests.post(url, json=body, timeout=90)
        r.raise_for_status()
        txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(txt)
    except Exception:
        return None


def _call_groq(topic: str) -> dict | None:
    import requests

    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "temperature": 0.7,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Topic: {topic}"},
                ],
            },
            timeout=90,
        )
        r.raise_for_status()
        return json.loads(r.json()["choices"][0]["message"]["content"])
    except Exception:
        return None


_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
         "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_SCALES = [(1_000_000_000, "billion"), (1_000_000, "million"), (1_000, "thousand")]


def int_to_words(n: int) -> str:
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens, rest = divmod(n, 10)
        return _TENS[tens] + (f"-{_ONES[rest]}" if rest else "")
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        head = f"{_ONES[hundreds]} hundred"
        return head + (f" {int_to_words(rest)}" if rest else "")
    for value, name in _SCALES:
        if n >= value:
            head, rest = divmod(n, value)
            return f"{int_to_words(head)} {name}" + (f" {int_to_words(rest)}" if rest else "")
    return str(n)


def number_to_words(raw: str) -> str:
    raw = raw.replace(",", "")
    if "." in raw:
        whole, frac = raw.split(".", 1)
        return f"{int_to_words(int(whole))} point {' '.join(_ONES[int(d)] for d in frac)}"
    return int_to_words(int(raw))


def digits_to_words(text: str) -> str:
    """§2.8: every number is spoken as words, never read as digits."""
    return re.sub(r"\d[\d,]*(?:\.\d+)?", lambda m: number_to_words(m.group(0)), text)


def validate_script(ep: dict[str, Any]) -> list[str]:
    """Return a list of §3 problems. Empty list = passes."""
    problems: list[str] = []
    sentences = ep.get("sentences") or []
    scenes = ep.get("scenes") or []
    if len(sentences) != 5:
        problems.append(f"expected 5 sentences, got {len(sentences)}")
    if len(scenes) != 5:
        problems.append(f"expected 5 scenes, got {len(scenes)}")
    words = sum(len(s.split()) for s in sentences)
    if not 70 <= words <= 125:
        problems.append(f"word budget {words} outside 70-125")
    for i, s in enumerate(sentences, 1):
        if not s.strip():
            problems.append(f"sentence {i} is empty")
        if "." in s.strip().rstrip("."):
            problems.append(f"sentence {i} contains an internal full stop")
        if re.search(r"\d", s):
            problems.append(f"sentence {i} contains digits (must be spoken as words)")
    last = (sentences[-1] if sentences else "").lower()
    if "subscribe" not in last:
        problems.append("sentence 5 must carry the ask")
    acc = ep.get("accuracy_table") or []
    if len(acc) < 2:
        problems.append("accuracy table needs at least 2 sourced claims")
    for row in acc:
        if not str(row.get("source", "")).strip():
            problems.append(f"unsourced claim: {row.get('claim')}")
    return problems


def normalise(ep: dict[str, Any]) -> dict[str, Any]:
    ep = dict(ep)
    ep["sentences"] = [digits_to_words(" ".join(s.split())) for s in ep.get("sentences", [])]
    ep.setdefault("alt_titles", [])
    ep.setdefault("tags", "")
    ep.setdefault("pinned_comment", "")
    ep.setdefault("accuracy_table", [])
    for sc in ep.get("scenes", []):
        sc.setdefault("icon", "atom")
        sc.setdefault("target_num", 0.0)
        sc.setdefault("unit", "")
    return ep


def generate(topic: str | None, preverified: dict | None = None) -> tuple[dict, str]:
    """Return (episode, provenance). Provenance is 'slate', 'gemini' or 'groq'."""
    if preverified is not None:
        return normalise(preverified), "slate"
    if topic and GEMINI_API_KEY:
        ep = _call_gemini(topic)
        if ep:
            ep = normalise(ep)
            if not validate_script(ep):
                return ep, "gemini"
    if topic and GROQ_API_KEY:
        ep = _call_groq(topic)
        if ep:
            ep = normalise(ep)
            if not validate_script(ep):
                return ep, "groq"
    raise RuntimeError(
        "No pre-verified episode left in the slate and no usable LLM key "
        "(GEMINI_API_KEY / GROQ_API_KEY). Pass an episode from dmf.slate or set a key."
    )
