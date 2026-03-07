"""
Microsoft Semantic Kernel plugin for WordOrb.ai (Python version).

Provides four kernel functions:
  - lookup_word          -- dictionary lookup (162K words, 47 languages)
  - get_lesson           -- structured 5-phase lesson
  - get_quiz             -- quiz / assessment questions
  - find_related_lessons -- knowledge graph connections

Usage::

    import semantic_kernel as sk
    from WordOrbPlugin import WordOrbPlugin

    kernel = sk.Kernel()
    kernel.add_plugin(WordOrbPlugin(api_key="wo_..."), "wordorb")

Requires: semantic-kernel >= 1.0, httpx
"""

from __future__ import annotations

import os
from typing import Annotated, Any, Dict, List, Optional

import httpx
from semantic_kernel.functions import kernel_function

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "https://api.wordorb.ai"
DEFAULT_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------


class WordOrbPlugin:
    """Semantic Kernel plugin for the WordOrb.ai vocabulary API.

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
            "User-Agent": "semantic-kernel-wordorb/1.0.0",
            "Accept": "application/json",
        }

    def _get(self, path: str, params: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        url = f"{self._base_url}{path}"
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(url, headers=self._headers(), params=params or {})

        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After", "60")
            raise RuntimeError(
                f"WordOrb rate limit exceeded. Retry after {retry_after}s. "
                "Upgrade at https://wordorb.ai/pricing"
            )
        if resp.status_code == 401:
            raise RuntimeError(
                "WordOrb authentication failed. Check your API key."
            )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Kernel functions
    # ------------------------------------------------------------------

    @kernel_function(
        name="lookup_word",
        description=(
            "Look up any English word. Returns IPA pronunciation, definition, "
            "etymology, part of speech, and translations in 47 languages. "
            "Use when the user asks about a word's meaning, pronunciation, or origin."
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
        name="get_lesson",
        description=(
            "Get a structured vocabulary lesson with 5 phases (hook, story, wonder, "
            "action, wisdom). Specify day (1-365), track (learn/grow/teach/trivia), "
            "and age group (kid/adult/elder). Use when building lesson plans or teaching."
        ),
    )
    def get_lesson(
        self,
        day: Annotated[int, "Day of the year (1-365). Each day has unique content."] = 1,
        track: Annotated[str, "Learning track: learn, grow, teach, or trivia."] = "learn",
        age_group: Annotated[str, "Age group: kid, adult, or elder."] = "adult",
    ) -> str:
        """Get a structured 5-phase vocabulary lesson."""
        params = {"day": str(day), "track": track, "age": age_group}
        data = self._get("/api/lesson", params)
        return _format_lesson(data)

    @kernel_function(
        name="get_quiz",
        description=(
            "Get vocabulary quiz questions. Specify a day (1-365) for lesson-aligned "
            "questions, or set day to 0 for random questions. Filter by type: mc, tf, "
            "ab, open, reflection. Use when assessing vocabulary knowledge."
        ),
    )
    def get_quiz(
        self,
        day: Annotated[int, "Day (1-365), or 0 for random questions."] = 0,
        track: Annotated[str, "Learning track: learn, grow, teach, or trivia."] = "learn",
        question_type: Annotated[str, "Question type: mc, tf, ab, open, reflection. Empty for all."] = "",
        count: Annotated[int, "Number of random questions (1-20). Only for day=0."] = 5,
    ) -> str:
        """Get quiz questions aligned to a lesson or random."""
        if day > 0:
            params: Dict[str, str] = {"day": str(day), "track": track}
            if question_type:
                params["type"] = question_type
            path = "/api/quiz"
        else:
            params = {"track": track, "count": str(min(count, 20))}
            if question_type:
                params["type"] = question_type
            path = "/api/quiz/random"

        data = self._get(path, params)
        return _format_quiz(data)

    @kernel_function(
        name="find_related_lessons",
        description=(
            "Query the knowledge graph for a word. Returns all lessons where the "
            "word appears, related words, and importance scores. Use to find "
            "thematic connections or build learning paths."
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


def _format_lesson(data: Dict[str, Any]) -> str:
    parts = [
        f"Lesson: Day {data.get('day', '?')} | Track: {data.get('track', '?')} "
        f"| Age: {data.get('age_group', '?')}",
    ]
    if data.get("title"):
        parts.append(f"Title: {data['title']}")
    if data.get("theme"):
        parts.append(f"Theme: {data['theme']}")
    phases = data.get("phases", {})
    for phase_name in ("hook", "story", "wonder", "action", "wisdom"):
        content = phases.get(phase_name)
        if content:
            parts.append(f"\n--- {phase_name.upper()} ---\n{content}")
    return "\n".join(parts)


def _format_quiz(data: Dict[str, Any]) -> str:
    interactions = data.get("interactions", [])
    if not interactions:
        return "No quiz questions found for the given parameters."
    parts = [
        f"Quiz: {len(interactions)} question(s) | Track: {data.get('track', '?')}"
    ]
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
