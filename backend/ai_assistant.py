"""KI-Briefing und Fragen an das Cockpit über die Claude API.

Data minimisation: Claude only receives schedule and planning data — lesson
titles (subject + class), dates, deadlines, class tests of the teacher's own
classes, school dates. Never grades, notes, or the content of Nextcloud /
itslearning messages (which carry colleagues' names); only their count.
Teachers opt in individually (signal preferences: "ai_enabled").

Configuration: ANTHROPIC_API_KEY (required), AI_MODEL (optional).
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
from datetime import date, datetime, timedelta
from typing import Any

from .ical_utils import BERLIN
from .signals import KIND_LABELS

logger = logging.getLogger(__name__)

MODEL = os.environ.get("AI_MODEL", "").strip() or "claude-opus-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_BRIEFINGS_PER_DAY = 8
MAX_QUESTIONS_PER_DAY = 30
MAX_HISTORY_MESSAGES = 8
MAX_QUESTION_CHARS = 600
MAX_CONTEXT_ENTRIES = 120
WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

SYSTEM_PROMPT = """Du bist der Assistent im Lehrercockpit, dem persönlichen Dashboard einer Lehrkraft an einer Berliner Schule.
Du bekommst eine Übersicht aus ihrem Stundenplan, dem Orgaplan, dem Klassenarbeitsplan, ihren itslearning-Terminen und dem Schulkalender.

- Antworte auf Deutsch, knapp und konkret, in der Du-Form.
- Nutze nur die Daten aus der Übersicht. Wenn etwas dort nicht steht, sag das offen, statt zu raten.
- Nenne Daten mit Wochentag (z. B. „Do 25.09.“).
- Keine Einleitung, keine Grußformel, kein Markdown außer einfachen Aufzählungspunkten."""

BRIEFING_INSTRUCTION = (
    "Fasse zusammen, was heute und in den nächsten Tagen für mich wichtig ist. "
    "Antworte mit 3 bis 5 kurzen Zeilen, jede beginnt mit „• “. Das Wichtigste zuerst: "
    "Entfall und Änderungen heute, Klassenarbeiten und Fristen der nächsten Tage, danach Termine. "
    "Wenn es nichts Besonderes gibt, schreib genau eine Zeile, die das sagt."
)


class AIError(Exception):
    """User-facing error with an HTTP status for the API layer."""

    def __init__(self, message: str, status: int = 503):
        super().__init__(message)
        self.status = status


def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


_client_lock = threading.Lock()
_client = None


def _get_client():
    global _client
    with _client_lock:
        if _client is None:
            import anthropic

            _client = anthropic.Anthropic(timeout=45.0, max_retries=2)
        return _client


# ── Context ──────────────────────────────────────────────────────────────────

def _day(value: str | None) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _day_label(day: date) -> str:
    return f"{WEEKDAYS[day.weekday()][:2]} {day:%d.%m.}"


def _lessons(modules: dict, days: set[date]) -> list[str]:
    result = modules.get("webuntis") or {}
    events = ((result.get("data") or {}).get("events") or []) if result.get("ok") else []
    lines = []
    for event in events:
        try:
            start = datetime.fromisoformat(str(event.get("startsAt")).replace("Z", "+00:00"))
        except ValueError:
            continue
        start = start.replace(tzinfo=BERLIN) if start.tzinfo is None else start.astimezone(BERLIN)
        if start.date() not in days:
            continue
        line = f"- {_day_label(start.date())} {start:%H:%M} {event.get('title') or 'Stunde'}"
        if event.get("location"):
            line += f" ({event['location']})"
        if event.get("cancelled"):
            line += " – entfällt"
        lines.append((start, line))
    return [line for _start, line in sorted(lines)]


def build_context(modules: dict, signals: list[dict], classes: set[str], now: datetime) -> str:
    """Compact, data-minimised overview for Claude (German)."""
    local = now.astimezone(BERLIN)
    today = local.date()
    lines = [f"Jetzt: {WEEKDAYS[today.weekday()]}, {today:%d.%m.%Y}, {local:%H:%M} Uhr (Berlin)."]
    if classes:
        lines.append("Klassen der Lehrkraft: " + ", ".join(sorted(classes)) + ".")

    lessons = _lessons(modules, {today, today + timedelta(days=1)})
    lines.append("")
    lines.append("Stundenplan heute und morgen:")
    lines.extend(lessons or ["- keine Stunden im Stundenplan-Abo"])

    entries = [s for s in signals if s.get("source") != "nextcloud"]
    entries.sort(key=lambda s: (s.get("date") or "9999", s.get("time") or ""))
    lines.append("")
    lines.append("Einträge der nächsten Wochen:")
    if not entries:
        lines.append("- keine")
    for signal in entries[:MAX_CONTEXT_ENTRIES]:
        day = _day(signal.get("date"))
        when = _day_label(day) if day else "ohne Datum"
        if signal.get("time"):
            when += f" {signal['time']}"
        line = f"- {when} [{KIND_LABELS.get(signal['kind'], signal['kind'])}] {signal['title']}"
        if signal.get("detail"):
            line += f" – {signal['detail']}"
        lines.append(line)

    nextcloud = [s for s in signals if s.get("source") == "nextcloud"]
    if nextcloud:
        lines.append("")
        lines.append(f"Nextcloud: {len(nextcloud)} neue Hinweise oder Dateiänderungen (Inhalte werden nicht übermittelt).")
    return "\n".join(lines)


def context_hash(context: str) -> str:
    # The first line carries the current minute; it must not change the hash.
    stable = context.split("\n", 1)[1] if "\n" in context else context
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()[:24]


# ── Claude calls ─────────────────────────────────────────────────────────────

def _call(messages: list[dict], context: str, *, max_tokens: int) -> tuple[str, dict[str, int]]:
    """One Claude request. Returns (text, usage). Raises AIError with a German message."""
    if not available():
        raise AIError("Der KI-Assistent ist auf diesem Server nicht eingerichtet.", 503)
    import anthropic

    try:
        response = _get_client().beta.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": SYSTEM_PROMPT}, {"type": "text", "text": context}],
            messages=messages,
            output_config={"effort": "low"},   # short summaries and answers
            cache_control={"type": "ephemeral"},  # reuses the prefix across follow-up questions
            betas=[FALLBACK_BETA],
            fallbacks="default",                # re-run declined requests on the recommended model
        )
    except anthropic.RateLimitError as exc:
        raise AIError("Die KI ist gerade ausgelastet. Bitte gleich noch einmal versuchen.", 429) from exc
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
        logger.error("[ai] credentials rejected: %s", exc)
        raise AIError("Der KI-Assistent ist falsch eingerichtet (API-Schlüssel).", 503) from exc
    except anthropic.BadRequestError as exc:
        logger.error("[ai] bad request: %s", exc)
        raise AIError("Die Anfrage an die KI war ungültig.", 502) from exc
    except anthropic.APIStatusError as exc:
        if exc.status_code >= 500:
            raise AIError("Die KI ist gerade nicht erreichbar. Bitte später noch einmal versuchen.", 503) from exc
        logger.error("[ai] API error %s: %s", exc.status_code, exc)
        raise AIError("Die KI hat die Anfrage abgelehnt.", 502) from exc
    except anthropic.APIConnectionError as exc:
        raise AIError("Die KI ist gerade nicht erreichbar. Bitte später noch einmal versuchen.", 503) from exc

    if response.stop_reason == "refusal":
        raise AIError("Dazu kann der Assistent nichts sagen.", 422)
    text = "\n".join(block.text for block in response.content if block.type == "text").strip()
    if not text:
        raise AIError("Die KI hat keine Antwort geliefert.", 502)
    usage = {"input": response.usage.input_tokens or 0, "output": response.usage.output_tokens or 0}
    return text, usage


def generate_briefing(context: str) -> tuple[list[str], dict[str, int]]:
    text, usage = _call([{"role": "user", "content": BRIEFING_INSTRUCTION}], context, max_tokens=2000)
    lines = [line.strip().lstrip("•-* ").strip() for line in text.splitlines() if line.strip()]
    return lines[:6], usage


def clean_history(history: Any) -> list[dict]:
    """Previous turns from the browser: alternating user/assistant text, newest last."""
    if not isinstance(history, list):
        return []
    cleaned = []
    for turn in history[-MAX_HISTORY_MESSAGES:]:
        if not isinstance(turn, dict) or turn.get("role") not in ("user", "assistant"):
            continue
        content = str(turn.get("content") or "").strip()[:2000]
        if not content:
            continue
        if cleaned and cleaned[-1]["role"] == turn["role"]:
            cleaned[-1]["content"] += "\n" + content
        else:
            cleaned.append({"role": turn["role"], "content": content})
    while cleaned and cleaned[0]["role"] != "user":
        cleaned.pop(0)
    if cleaned and cleaned[-1]["role"] == "user":
        cleaned.pop()  # the new question follows
    return cleaned


def answer_question(context: str, history: list[dict], question: str) -> tuple[str, dict[str, int]]:
    question = question.strip()[:MAX_QUESTION_CHARS]
    if not question:
        raise AIError("Bitte eine Frage eingeben.", 422)
    messages = clean_history(history) + [{"role": "user", "content": question}]
    return _call(messages, context, max_tokens=3000)


# ── Usage, cache, opt-in (DB) ────────────────────────────────────────────────

def usage_today(conn, user_id: int, today: date) -> dict[str, int]:
    row = conn.execute("SELECT briefings, questions FROM ai_usage WHERE user_id = %s AND day = %s",
                       (user_id, today)).fetchone()
    return {"briefings": row[0] if row else 0, "questions": row[1] if row else 0}


def record_usage(conn, user_id: int, today: date, kind: str, tokens: dict[str, int]) -> None:
    column = {"briefing": "briefings", "question": "questions"}[kind]
    conn.execute(
        f"""
        INSERT INTO ai_usage (user_id, day, {column}, input_tokens, output_tokens)
        VALUES (%s, %s, 1, %s, %s)
        ON CONFLICT (user_id, day) DO UPDATE SET
            {column} = ai_usage.{column} + 1,
            input_tokens = ai_usage.input_tokens + EXCLUDED.input_tokens,
            output_tokens = ai_usage.output_tokens + EXCLUDED.output_tokens
        """,
        (user_id, today, tokens.get("input", 0), tokens.get("output", 0)),
    )


def cached_briefing(conn, user_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT day, context_hash, lines, created_at FROM ai_briefings WHERE user_id = %s",
                       (user_id,)).fetchone()
    if not row:
        return None
    return {"day": row[0], "context_hash": row[1], "lines": row[2] or [], "created_at": row[3]}


def store_briefing(conn, user_id: int, today: date, digest: str, lines: list[str], now: datetime) -> None:
    import psycopg.types.json as _pjson

    conn.execute(
        """
        INSERT INTO ai_briefings (user_id, day, context_hash, lines, created_at)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET day = EXCLUDED.day, context_hash = EXCLUDED.context_hash,
            lines = EXCLUDED.lines, created_at = EXCLUDED.created_at
        """,
        (user_id, today, digest, _pjson.Jsonb(lines), now),
    )


def briefing_is_fresh(cached: dict[str, Any] | None, today: date, digest: str, now: datetime) -> bool:
    """Reuse today's briefing unless the data changed and it is older than two hours."""
    if not cached or cached["day"] != today:
        return False
    if cached["context_hash"] == digest:
        return True
    created = cached["created_at"]
    return created is not None and now - created < timedelta(hours=2)
