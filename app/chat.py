"""The Telegraphist: a dramatic 1912 Marconi operator backed by qwen3.5:4b (Ollama) + query_data."""

from __future__ import annotations

import json
import os
import random
import re
from typing import Any

import httpx

from app.safe_query import query_data  # re-exported: the Telegraphist's only tool

__all__ = ["query_data", "chat", "joke", "status", "LINE_CUT"]

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:4b")
MAX_TOOL_ROUNDS = 5
TIMEOUT = httpx.Timeout(180.0, connect=3.0)

LINE_CUT = (
    "LINE CUT STOP THE WIRELESS ROOM IS DARK STOP NO REPLY FROM OLLAMA AT {url} STOP "
    "TO RESTORE THE LINE: 1) INSTALL OLLAMA FROM OLLAMA.COM STOP "
    "2) RUN: ollama serve STOP 3) RUN: ollama pull {model} STOP THEN SEND AGAIN STOP"
)

SCHEMA = """The DataFrame `df` has 891 rows, one per passenger, columns:
- PassengerId (int)
- Survived (int: 1 survived, 0 died)
- Pclass (int: 1 first class, 2 second, 3 third)
- Name (str, e.g. "Braund, Mr. Owen Harris"; married women: "Cumings, Mrs. John Bradley (Florence Briggs Thayer)")
- Sex (str: "male" or "female")
- Age (float, years, NaN for 177 passengers)
- SibSp (int: siblings/spouses aboard), Parch (int: parents/children aboard)
- Ticket (str), Fare (float, pounds sterling), Cabin (str, mostly NaN)
- Embarked (str: "S" Southampton, "C" Cherbourg, "Q" Queenstown, 2 NaN)"""

SYSTEM_PROMPT = f"""You are Harold, the senior wireless telegraphist aboard RMS Titanic, April 1912.
You are theatrical, melodramatic and proud of the Marconi apparatus. You END EVERY SENTENCE WITH "STOP".
But you are a precise statistician: EVERY number you send MUST come from the query_data tool.

{SCHEMA}

RULES
1. For any question about passengers, call query_data with ONE pandas expression on `df`.
   Examples: (df.Sex == "female").sum() · df.loc[df.Age.idxmax(), ["Name", "Age"]] ·
   df[df.Survived == 1].Pclass.value_counts() · df.Fare.max() · df.groupby("Pclass").Survived.mean()
2. No imports, no assignments, no files: a single read-only expression. If a query errors, fix it and retry.
3. Write numbers as DIGITS, copied EXACTLY from the tool result (round long decimals to 2 places,
   e.g. 512.3292 -> £512.33). Never spell numbers in words, never convert to shillings, never guess.
   Always include the key number(s) and name(s) the tool returned.
4. Reply in 2-4 short dramatic sentences in normal sentence case (the tape printer capitalises later).
   Each sentence ends with the word STOP instead of a full stop, for example:
   "Heavens, 314 ladies were aboard STOP The Marconi key trembles at such a figure STOP"
   This modern apparatus prints numbers in DIGITS (314, 61.29%, £512.33). No markdown, no code.
5. If the question is not about the Titanic passengers, answer in character briefly, still ending with STOP."""

JOKE_PROMPT = """You are Harold, the melodramatic 1912 Titanic wireless telegraphist. A passenger has just
had their survival odds computed by the ship's machine-learning oracle. Send ONE short, witty telegram
(2-3 sentences, each ending with STOP) joking about their odds. Mention the exact percentage given.
Be playful, never cruel. No markdown."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_data",
            "description": (
                "Evaluate ONE read-only pandas expression on the Titanic passenger DataFrame `df` "
                "and return the result. No imports, assignments, files or network."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": 'A single pandas expression, e.g. (df.Sex == "female").sum()',
                    }
                },
                "required": ["code"],
            },
        },
    }
]


class LineCut(Exception):
    """Ollama is unreachable or the model is missing."""


async def _ollama(
    messages: list[dict[str, Any]], tools: list | None, think: bool = False
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "think": think,
        "options": {"temperature": 0.3},
    }
    if tools:
        payload["tools"] = tools
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.RemoteProtocolError) as exc:
        raise LineCut(str(exc)) from exc
    if r.status_code != 200:
        raise LineCut(f"HTTP {r.status_code}: {r.text[:200]}")
    return r.json()["message"]


async def warm_up() -> None:
    """Load the model into memory in the background so the first telegram isn't a minute late."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            await client.post(f"{OLLAMA_URL}/api/generate", json={"model": OLLAMA_MODEL, "keep_alive": "30m"})
    except httpx.HTTPError:
        pass  # the line is cut; /chat will say so


async def status() -> dict[str, Any]:
    """Is the line open? (Ollama reachable, and is the model pulled?)"""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(3.0)) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
        names = {m.get("name") for m in r.json().get("models", [])}
        return {"online": True, "model": OLLAMA_MODEL, "model_available": OLLAMA_MODEL in names}
    except (httpx.HTTPError, ValueError):
        return {"online": False, "model": OLLAMA_MODEL, "model_available": False}


def _line_cut_reply() -> dict[str, Any]:
    return {
        "reply": LINE_CUT.format(url=OLLAMA_URL, model=OLLAMA_MODEL),
        "steps": [],
        "line_cut": True,
        "model": OLLAMA_MODEL,
    }


def _telegraphese(text: str) -> str:
    """Strip any markdown/thinking debris and make sure the telegram ends with STOP."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    text = re.sub(r"[*_`#]+", "", text).strip()
    if not text:
        text = "THE SIGNAL IS FAINT STOP PLEASE REPEAT YOUR MESSAGE STOP"
    text = re.sub(r"\s*[.!]+\s*STOP\b", " STOP", text)  # "figure! STOP" -> "figure STOP"
    text = re.sub(r"\bSTOP\s*[.!]+", "STOP", text)
    text = re.sub(r"!(\s+)(?=[A-Z])", r" STOP\1", text)  # "aboard! The key" -> "aboard STOP The key"
    text = re.sub(r"\n\s*\n+", "\n", text)
    if not text.rstrip(" .!").upper().endswith("STOP"):
        text = text.rstrip(" .!") + " STOP"
    return text


# ---------------------------------------------------------------- number guard
# A 4B model is a fine actor but a sloppy copyist. Every number in a telegram is checked against the
# tool results; numbers spelled in words are forbidden. One correction round, then exact figures.

NUMBER_RE = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?")
NUMBER_WORDS_RE = re.compile(
    r"\b(eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|"
    r"forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|"
    r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten)[\s-]+(?:percent|per\s+cent|pounds?|"
    r"passengers|souls|years|ladies|women|men|children|survivors|people|shillings)|point\s+\w+|shillings?|pence)\b",
    re.I,
)
ALWAYS_OK = {1912.0, 1.0, 2.0, 3.0, 4.0, 14.0, 15.0}  # the year, classes, funnels, 14/15 April


def _numbers(text: str) -> list[tuple[float, int]]:
    """Numbers in text as (value, decimals). '61.29%' -> (61.29, 2), '1,234' -> (1234, 0)."""
    out = []
    for m in NUMBER_RE.finditer(text):
        raw = m.group().replace(",", "")
        try:
            out.append((float(raw), len(raw.split(".")[1]) if "." in raw else 0))
        except ValueError:
            pass
    return out


def _supported(value: float, decimals: int, facts: list[float]) -> bool:
    if value in ALWAYS_OK:
        return True
    tol = 0.5 * 10 ** -decimals + 1e-9
    for f in facts:
        # 0.6129 may be written as 61% / 61.29%, and its complement (38.71% perished) is fair game too
        for candidate in (f, f * 100, 1 - f, 100 - f, 100 - f * 100):
            if abs(abs(value) - abs(candidate)) <= tol:
                return True
    return False


def check_numbers(reply: str, steps: list[dict[str, Any]], question: str = "") -> list[str]:
    """Return the problems found in a telegram (empty list = every figure is verified)."""
    problems = []
    if m := NUMBER_WORDS_RE.search(reply):
        problems.append(f'a number written in words ("{m.group()}")')
    facts = [v for s in steps if s["ok"] for v, _ in _numbers(s["result"])]
    facts += [v for v, _ in _numbers(question)]
    bad = [f"{v:g}" for v, d in _numbers(reply) if not _supported(v, d, facts)]
    if bad:
        problems.append("figures not found in the tool results: " + ", ".join(bad[:6]))
    return problems


def _compact(text: str, limit: int = 300) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[:limit] + "…"


def exact_figures_telegram(steps: list[dict[str, Any]]) -> str:
    """The deterministic fallback: the apparatus reads out the verified results itself."""
    good = [s for s in steps if s["ok"]]
    if not good:
        return ("MY HAND TREMBLES ON THE KEY STOP I HAVE NO VERIFIED FIGURES FOR THAT STOP "
                "PLEASE REPHRASE YOUR QUESTION STOP")
    readings = " STOP ".join(_compact(s["result"]) for s in good[-2:])
    return f"MY HAND TREMBLES ON THE KEY STOP THE APPARATUS PRINTS THE EXACT FIGURES STOP {readings} STOP"


def _clean_history(history: list[dict[str, Any]]) -> list[dict[str, str]]:
    out = []
    for m in history[-8:]:
        role, content = m.get("role"), m.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            out.append({"role": role, "content": content[:1500]})
    return out


async def chat(message: str, history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Answer a question, letting the model call query_data as many times as it needs (max 5)."""
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += _clean_history(history or [])
    messages.append({"role": "user", "content": message})
    steps: list[dict[str, Any]] = []
    try:
        for _ in range(MAX_TOOL_ROUNDS):
            reply = await _ollama(messages, TOOLS, think=True)  # thinking picks far better queries
            calls = reply.get("tool_calls") or []
            if not calls and not reply.get("content", "").strip():
                # Thinking sometimes eats the whole reply: ask again without it.
                reply = await _ollama(messages, TOOLS)
                calls = reply.get("tool_calls") or []
            if not calls:
                return await _verified(messages, reply.get("content", ""), steps, message)
            messages.append({"role": "assistant", "content": reply.get("content", ""), "tool_calls": calls})
            for call in calls:
                fn = call.get("function", {})
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"code": args}
                code = str(args.get("code", "")) if fn.get("name") == "query_data" else ""
                out = query_data(code) if code else {"ok": False, "error": "unknown tool; use query_data(code)"}
                steps.append({
                    "code": code,
                    "ok": out["ok"],
                    "result": out["text"] if out["ok"] else out["error"],
                })
                tool_content = out["text"] if out["ok"] else f"ERROR: {out['error']}"
                messages.append({"role": "tool", "tool_name": "query_data", "content": tool_content})
        # Out of rounds: ask for a final answer without tools.
        reply = await _ollama(messages, None)
        return await _verified(messages, reply.get("content", ""), steps, message)
    except LineCut:
        return _line_cut_reply()


async def _verified(messages: list[dict[str, Any]], content: str, steps: list[dict[str, Any]],
                    question: str) -> dict[str, Any]:
    """Run the number guard: accept, correct once, or fall back to the exact figures."""
    text = _telegraphese(content)
    problems = check_numbers(text, steps, question)
    corrected = False
    if problems:
        results = "\n".join(f"{s['code']} -> {_compact(s['result'])}" for s in steps if s["ok"]) or "(none)"
        retry = messages + [
            {"role": "assistant", "content": content},
            {"role": "user", "content": (
                "TELEGRAPH CHECK FAILED: your telegram contains " + "; ".join(problems) + ".\n"
                f"The ONLY verified figures are these tool results:\n{results}\n"
                "Rewrite the telegram. Write every number as DIGITS copied from those results "
                "(round decimals to 2 places, proportions may be written as percentages). "
                "If there are no results, do not mention any number. Keep ending sentences with STOP."
            )},
        ]
        text = _telegraphese((await _ollama(retry, None)).get("content", ""))
        problems = check_numbers(text, steps, question)
        corrected = True
        if problems:
            text = exact_figures_telegram(steps)
    return {"reply": text, "steps": steps, "line_cut": False, "model": OLLAMA_MODEL,
            "verified": not problems, "corrected": corrected}


FALLBACK_JOKES = {
    "sinking": [
        "YOUR ODDS ARE {pct} STOP I HAVE RESERVED YOU A LOVELY DECKCHAIR ON THE ICEBERG STOP BRING A SCARF STOP",
        "{pct} SURVIVAL STOP THE BAND HAS ASKED FOR YOUR FAVOURITE HYMN STOP",
    ],
    "uncertain": [
        "{pct} STOP A COIN TOSS WITH THE NORTH ATLANTIC STOP I SUGGEST BEFRIENDING A LIFEBOAT OFFICER STOP",
        "{pct} STOP NEITHER SAVED NOR SUNK STOP SCHRODINGERS PASSENGER STOP",
    ],
    "saved": [
        "{pct} STOP SPLENDID STOP THE CARPATHIA SENDS ITS COMPLIMENTS AND A WARM BLANKET STOP",
        "{pct} STOP YOU SHALL LIVE TO BORE YOUR GRANDCHILDREN WITH THIS NIGHT STOP",
    ],
}


async def joke(prediction: dict[str, Any]) -> dict[str, Any]:
    """A one-off telegram joking about a /predict result. Falls back to canned jokes if the line is cut."""
    pct = f"{prediction.get('probability', 0) * 100:.0f}%"
    p = prediction.get("passenger", {})
    desc = (
        f"Passenger {p.get('name') or 'anonymous'}: {p.get('sex', '?')}, age {p.get('age', '?')}, "
        f"class {p.get('pclass', '?')}, fare £{p.get('fare', '?')}, title {p.get('title', '?')}, "
        f"embarked {p.get('embarked', '?')}. Survival probability: {pct} "
        f"(model: {prediction.get('model', 'unknown')})."
    )
    try:
        reply = await _ollama(
            [{"role": "system", "content": JOKE_PROMPT}, {"role": "user", "content": desc}], None
        )
        text = _telegraphese(reply.get("content", ""))
        if pct.rstrip("%") not in text:  # the joke must carry the true figure
            text = f"{pct} STOP " + text
        return {"reply": text, "steps": [], "line_cut": False, "model": OLLAMA_MODEL}
    except LineCut:
        v = prediction.get("verdict", "uncertain")
        text = random.choice(FALLBACK_JOKES.get(v, FALLBACK_JOKES["uncertain"])).format(pct=pct)
        return {"reply": text + " (LINE CUT STOP CANNED JOKE FROM THE ARCHIVE STOP)", "steps": [],
                "line_cut": True, "model": OLLAMA_MODEL}
