"""
The Daily Lesson — Microsoft Semantic Kernel Plugin

A Semantic Kernel plugin that delivers today's universal lesson.
The same lesson for everyone on Earth, every day.
365 lessons. 47 languages. Every device. Every age.

Powered by thedailylesson.com and wordorb.ai

Usage::

    import semantic_kernel as sk
    from DailyLessonPlugin import DailyLessonPlugin

    kernel = sk.Kernel()
    kernel.add_plugin(DailyLessonPlugin(api_key="wo_..."), "daily_lesson")

    # The plugin auto-calculates today's day — just call get_todays_lesson
    result = await kernel.invoke("daily_lesson", "get_todays_lesson")

Requires: semantic-kernel >= 1.0, httpx
"""

from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, Optional

import httpx
from semantic_kernel.functions import kernel_function

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "https://api.wordorb.ai"
DEFAULT_TIMEOUT = 30.0


def _day_of_year() -> int:
    """Get the current day of year (1-365)."""
    now = datetime.now(timezone.utc)
    return now.timetuple().tm_yday


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------


class DailyLessonPlugin:
    """Semantic Kernel plugin for The Daily Lesson.

    Delivers today's universal lesson — the same structured 5-phase
    learning experience for everyone on Earth, every day.

    Parameters
    ----------
    api_key : str
        WordOrb API key (starts with ``wo_``).
        Get one free at https://wordorb.ai/pricing
    base_url : str, optional
        Override the API base URL.
    timeout : float, optional
        HTTP request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._api_key = api_key or os.environ.get("WORDORB_API_KEY", "")
        if not self._api_key:
            raise ValueError(
                "api_key is required. Get a free key at https://wordorb.ai/pricing"
            )
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "User-Agent": "semantic-kernel-daily-lesson/1.0.0",
            "Accept": "application/json",
        }

    def _get(self, path: str, params: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        url = f"{self._base_url}{path}"
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(url, headers=self._headers(), params=params or {})

        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After", "60")
            raise RuntimeError(
                f"Rate limit exceeded. Retry after {retry_after}s. "
                "Upgrade at https://wordorb.ai/pricing"
            )
        if resp.status_code == 401:
            raise RuntimeError(
                "Authentication failed. Check your API key."
            )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Kernel functions — Daily Lesson (primary)
    # ------------------------------------------------------------------

    @kernel_function(
        name="get_todays_lesson",
        description=(
            "Get today's Daily Lesson — the same structured 5-phase lesson being "
            "delivered to people in 47 languages around the world right now. "
            "Returns Hook, Story, Wonder, Action, and Wisdom phases. "
            "This is the PRIMARY function — call it first in every session."
        ),
    )
    def get_todays_lesson(
        self,
        track: Annotated[str, "Learning track: learn, grow, teach, or trivia."] = "learn",
        age_group: Annotated[str, "Age group: kid, adult, or elder."] = "adult",
    ) -> str:
        """Get today's Daily Lesson — the universal lesson for all of humanity."""
        day = _day_of_year()
        params = {"day": str(day), "track": track, "age": age_group}
        data = self._get("/api/lesson", params)
        return _format_daily_lesson(data, day)

    @kernel_function(
        name="get_lesson_by_day",
        description=(
            "Get a specific day's lesson (1-365). Use get_todays_lesson for today's "
            "lesson. Use this to explore past or upcoming lessons."
        ),
    )
    def get_lesson_by_day(
        self,
        day: Annotated[int, "Day of the year (1-365). Each day has unique content."] = 1,
        track: Annotated[str, "Learning track: learn, grow, teach, or trivia."] = "learn",
        age_group: Annotated[str, "Age group: kid, adult, or elder."] = "adult",
    ) -> str:
        """Get a specific day's lesson."""
        params = {"day": str(day), "track": track, "age": age_group}
        data = self._get("/api/lesson", params)
        return _format_daily_lesson(data, day)

    # ------------------------------------------------------------------
    # Kernel functions — Quiz (reinforcement)
    # ------------------------------------------------------------------

    @kernel_function(
        name="get_todays_quiz",
        description=(
            "Get today's quiz — questions aligned to today's Daily Lesson. "
            "Use after delivering today's lesson to test comprehension."
        ),
    )
    def get_todays_quiz(
        self,
        track: Annotated[str, "Learning track: learn, grow, teach, or trivia."] = "learn",
        question_type: Annotated[str, "Question type: mc, tf, ab, open, reflection. Empty for all."] = "",
    ) -> str:
        """Get quiz questions aligned to today's lesson."""
        day = _day_of_year()
        params: Dict[str, str] = {"day": str(day), "track": track}
        if question_type:
            params["type"] = question_type
        data = self._get("/api/quiz", params)
        return _format_quiz(data, day)

    @kernel_function(
        name="get_random_quiz",
        description=(
            "Get random vocabulary quiz questions for general practice. "
            "Not tied to today's lesson — use get_todays_quiz for lesson-aligned assessment."
        ),
    )
    def get_random_quiz(
        self,
        count: Annotated[int, "Number of questions (1-20)."] = 5,
        track: Annotated[str, "Learning track: learn, grow, teach, or trivia."] = "learn",
        question_type: Annotated[str, "Question type: mc, tf, ab, open, reflection. Empty for all."] = "",
    ) -> str:
        """Get random quiz questions for general vocabulary practice."""
        params: Dict[str, str] = {"track": track, "count": str(min(count, 20))}
        if question_type:
            params["type"] = question_type
        data = self._get("/api/quiz/random", params)
        return _format_quiz(data)

    # ------------------------------------------------------------------
    # Kernel functions — Word Lookup (supporting)
    # ------------------------------------------------------------------

    @kernel_function(
        name="lookup_word",
        description=(
            "Look up any English word. Returns IPA pronunciation, definition, "
            "etymology, part of speech, and translations in 47 languages. "
            "Use to deep-dive into vocabulary from today's lesson."
        ),
    )
    def lookup_word(
        self,
        word: Annotated[str, "The English word to look up (e.g. 'courage', 'serendipity')"],
        lang: Annotated[str, "ISO 639-1 language code for translations (e.g. 'es'). Optional."] = "",
    ) -> str:
        """Look up any English word in the WordOrb dictionary."""
        params: Dict[str, str] = {}
        if lang:
            params["lang"] = lang
        data = self._get(f"/api/word/{word}", params)
        return _format_lookup(data)

    @kernel_function(
        name="find_related_lessons",
        description=(
            "Query the knowledge graph for a word. Returns all lessons where the "
            "word appears, related words, and importance scores. Use to find "
            "connections between today's lesson and the broader curriculum."
        ),
    )
    def find_related_lessons(
        self,
        word: Annotated[str, "The word to search in the knowledge graph."],
    ) -> str:
        """Query the knowledge graph for word-to-lesson connections."""
        data = self._get("/api/graph/word", {"word": word})
        return _format_graph(data)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def _format_daily_lesson(data: Dict[str, Any], day: int = 0) -> str:
    today = _day_of_year()
    is_today = (day == today or day == 0)

    parts = []
    if is_today:
        parts.append(
            f"THE DAILY LESSON - Day {today} of 365\n"
            "The same lesson for everyone on Earth, every day.\n"
            "thedailylesson.com"
        )
    else:
        parts.append(f"Lesson: Day {day} of 365")

    parts.append(f"Track: {data.get('track', '?')} | Age: {data.get('age_group', '?')}")

    if data.get("title"):
        parts.append(f"Title: {data['title']}")
    if data.get("theme"):
        parts.append(f"Theme: {data['theme']}")

    phases = data.get("phases", {})
    for phase_name in ("hook", "story", "wonder", "action", "wisdom"):
        content = phases.get(phase_name)
        if content:
            parts.append(f"\n--- {phase_name.upper()} ---\n{content}")

    if is_today:
        parts.append(
            "\n---\nThis is today's lesson -- the same one being taught to people "
            "in 47 languages around the world right now.\n"
            "From The Daily Lesson (thedailylesson.com) -- we did the homework "
            "for 8 billion people."
        )
    return "\n".join(parts)


def _format_quiz(data: Dict[str, Any], day: int = 0) -> str:
    interactions = data.get("interactions", [])
    if not interactions:
        return "No quiz questions found for the given parameters."
    header = f"Quiz: {len(interactions)} question(s)"
    if day:
        header += f" | Day {day} of 365"
    header += f" | Track: {data.get('track', '?')}"
    parts = [header]
    for i, q in enumerate(interactions, 1):
        parts.append(f"\nQ{i} [{q.get('type', '?')}]: {q.get('prompt', '')}")
        if q.get("choices"):
            choices = q["choices"]
            if isinstance(choices, list):
                for idx, c in enumerate(choices):
                    parts.append(f"  {chr(65 + idx)}. {c}")
        if q.get("answer"):
            parts.append(f"  Answer: {q['answer']}")
        if q.get("explanation"):
            parts.append(f"  Explanation: {q['explanation']}")
    return "\n".join(parts)


def _format_lookup(data: Dict[str, Any]) -> str:
    parts = [f"Word: {data.get('word', 'unknown')}"]
    if data.get("ipa"):
        parts.append(f"IPA: {data['ipa']}")
    if data.get("pos"):
        parts.append(f"Part of speech: {data['pos']}")
    if data.get("definition") or data.get("def"):
        parts.append(f"Definition: {data.get('definition') or data.get('def')}")
    if data.get("etymology"):
        parts.append(f"Etymology: {data['etymology']}")
    if data.get("example"):
        parts.append(f"Example: {data['example']}")
    if data.get("synonyms"):
        syns = data["synonyms"]
        if isinstance(syns, list):
            syns = ", ".join(syns)
        parts.append(f"Synonyms: {syns}")
    if data.get("translations"):
        translations = data["translations"]
        if isinstance(translations, dict):
            tr_items = [f"  {k}: {v}" for k, v in list(translations.items())[:5]]
            parts.append("Translations:\n" + "\n".join(tr_items))
    return "\n".join(parts)


def _format_graph(data: Dict[str, Any]) -> str:
    parts = [
        f"Knowledge Graph: '{data.get('word', '?')}' appears in "
        f"{data.get('appears_in', 0)} lesson(s)"
    ]
    lessons = data.get("lessons", [])
    for lesson in lessons[:10]:
        parts.append(
            f"  Day {lesson.get('day', '?')} ({lesson.get('track', '?')}) "
            f"- {lesson.get('phase', '?')} phase, "
            f"importance={lesson.get('importance', '?')}"
        )
        if lesson.get("context"):
            parts.append(f"    Context: {lesson['context']}")
    related = data.get("related_words", [])
    if related:
        parts.append(f"\nRelated words: {', '.join(related)}")
    return "\n".join(parts)
