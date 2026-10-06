"""The owner's guardrails on the subscription (decided 2026-10-05): what the artists may use, and when.

- a daily budget across all artists, a ceiling per work, and a painting window (local time);
- measured in API-equivalent dollars from the token usage in the transcripts, priced as Claude Code prices it
  (verified: the spike painting's tokens give Claude Code's own $3.1858 exactly);
- the "day" runs noon to noon, so one night's window (23:00-07:00) is one day.

Nothing here reaches an artist: a budget or window stop ends a sitting like the end of a working day.
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from config import DATA

DAILY_USD = float(os.environ.get("ATELIER_DAILY_USD", "40"))
WORK_USD = float(os.environ.get("ATELIER_WORK_USD", "60"))
# "23-7": from 23:00 to 07:00; "always": no window (tests)
WINDOW = os.environ.get("ATELIER_WINDOW", "23-7")
LEDGER = DATA / "run" / "ledger.json"

# $ per million tokens: input, output, cache read, cache write (5 min), cache write (1 h)
PRICES = {
    "claude-opus-5-5": (4.0, 20.0, 0.20, 5.0, 8.0),
    "claude-sonnet-5-5": (2.0, 10.0, 0.20, 2.5, 4.0),
    "claude-fable-5-1": (10.0, 50.0, 0.25, 12.5, 20.0),
}
UNKNOWN = PRICES["claude-fable-5-1"]  # an unknown model is priced high, never low


def cost(usage: dict, model: str | None) -> float:
    p = PRICES.get(model or "", UNKNOWN)
    cc = usage.get("cache_creation") or {}
    w5 = cc.get("ephemeral_5m_input_tokens") or 0
    w1 = cc.get("ephemeral_1h_input_tokens") or 0
    if not cc:
        w1 = usage.get("cache_creation_input_tokens") or 0  # unknown split: the dearer rate
    return ((usage.get("input_tokens") or 0) * p[0] + (usage.get("output_tokens") or 0) * p[1]
            + (usage.get("cache_read_input_tokens") or 0) * p[2] + w5 * p[3] + w1 * p[4]) / 1e6


class Meter:
    """A sitting's spend so far, from its transcript's assistant messages (each API message counted once)."""

    def __init__(self):
        self.by_message: dict[str, float] = {}

    def add(self, d: dict):
        m = d.get("message") or {}
        if d.get("type") == "assistant" and m.get("id") and m.get("usage"):
            self.by_message[m["id"]] = cost(m["usage"], m.get("model"))

    @property
    def usd(self) -> float:
        return sum(self.by_message.values())


def day(t: datetime | None = None) -> str:
    """The atelier's day: noon to noon, so a night is one day."""
    return ((t or datetime.now()) - timedelta(hours=12)).strftime("%Y-%m-%d")


def ledger() -> dict:
    return json.loads(LEDGER.read_text()) if LEDGER.exists() else {}


def spend(usd: float, work: str):
    """Book a finished sitting's spend on today and on the work."""
    led = ledger()
    d = led.setdefault("days", {})
    d[day()] = round(d.get(day(), 0) + usd, 4)
    w = led.setdefault("works", {})
    w[work] = round(w.get(work, 0) + usd, 4)
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    tmp = LEDGER.with_suffix(".tmp")
    tmp.write_text(json.dumps(led, indent=1))
    tmp.replace(LEDGER)


def spent_today() -> float:
    return ledger().get("days", {}).get(day(), 0.0)


def spent_on(work: str) -> float:
    return ledger().get("works", {}).get(work, 0.0)


def in_window(t: datetime | None = None) -> bool:
    if WINDOW == "always":
        return True
    start, end = (int(x) for x in WINDOW.split("-"))
    h = (t or datetime.now()).hour
    return (start <= h or h < end) if start > end else (start <= h < end)


def next_open(t: datetime | None = None) -> datetime:
    """When painting may next start: the window's next opening, and a new day's budget if today's is spent."""
    t = t or datetime.now()
    if WINDOW == "always":
        nxt = t if spent_today() < DAILY_USD else (t - timedelta(hours=12)).replace(hour=12, minute=0, second=0, microsecond=0) + timedelta(days=1)
        return nxt
    start = int(WINDOW.split("-")[0])
    opening = t.replace(hour=start, minute=0, second=0, microsecond=0)
    if in_window(t) and spent_today() < DAILY_USD:
        return t
    if opening <= t:
        opening += timedelta(days=1)
    # an opening whose day's budget is already spent (the same night): the next night
    while ledger().get("days", {}).get(day(opening), 0.0) >= DAILY_USD:
        opening += timedelta(days=1)
    return opening


def may_paint(work: str, sitting_usd: float = 0.0) -> str | None:
    """None if painting may go on; else why not: "window", "daily" or "work"."""
    if spent_on(work) + sitting_usd >= WORK_USD:
        return "work"
    if spent_today() + sitting_usd >= DAILY_USD:
        return "daily"
    if not in_window():
        return "window"
    return None
