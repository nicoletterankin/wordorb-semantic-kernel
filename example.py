"""
Complete example: Semantic Kernel agent with WordOrb plugin and automatic planner.

The planner automatically decides which WordOrb functions to call based on the
user's natural language request.

Run::

    export OPENAI_API_KEY="sk-..."
    export WORDORB_API_KEY="wo_..."
    python example.py

Requires: semantic-kernel >= 1.0, httpx
"""

from __future__ import annotations

import asyncio
import os
import sys

import semantic_kernel as sk
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings import (
    OpenAIChatPromptExecutionSettings,
)
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.functions import KernelArguments

from WordOrbPlugin import WordOrbPlugin

# ---------------------------------------------------------------------------
# Validate environment
# ---------------------------------------------------------------------------

WORDORB_API_KEY = os.environ.get("WORDORB_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

if not WORDORB_API_KEY:
    print("Error: Set the WORDORB_API_KEY environment variable.")
    print("  Get a free key at https://wordorb.ai/pricing")
    sys.exit(1)

if not OPENAI_API_KEY:
    print("Error: Set the OPENAI_API_KEY environment variable.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Build the kernel
# ---------------------------------------------------------------------------

SYSTEM_MESSAGE = """\
You are an expert vocabulary tutor powered by the WordOrb platform.

Your capabilities:
- Look up any English word for its definition, pronunciation, etymology, and translations.
- Retrieve structured 5-phase lessons (hook, story, wonder, action, wisdom).
- Generate quiz questions (multiple choice, true/false, open-ended, etc.).
- Explore the knowledge graph to find thematic connections between words and lessons.

Teaching style:
- Always include pronunciation (IPA) and at least one example sentence.
- Connect new words to related words using the knowledge graph.
- After teaching, offer a quiz to reinforce learning.
- Be encouraging and adapt to the student's level.
"""


async def build_kernel() -> sk.Kernel:
    """Build a Semantic Kernel with the WordOrb plugin and OpenAI chat."""
    kernel = sk.Kernel()

    # Add AI service
    kernel.add_service(
        OpenAIChatCompletion(
            service_id="chat",
            ai_model_id="gpt-4o",
            api_key=OPENAI_API_KEY,
        )
    )

    # Add WordOrb plugin
    wordorb = WordOrbPlugin(api_key=WORDORB_API_KEY)
    kernel.add_plugin(wordorb, plugin_name="wordorb")

    return kernel


# ---------------------------------------------------------------------------
# Interactive loop
# ---------------------------------------------------------------------------


async def main() -> None:
    """Run an interactive vocabulary tutor session."""
    kernel = await build_kernel()
    chat_history = ChatHistory(system_message=SYSTEM_MESSAGE)

    # Configure auto function-calling
    settings = OpenAIChatPromptExecutionSettings(
        service_id="chat",
        max_tokens=2000,
        temperature=0.3,
    )
    settings.function_choice_behavior = (
        sk.contents.FunctionChoiceBehavior.Auto()
    )

    print("=" * 60)
    print("  WordOrb Vocabulary Tutor (Semantic Kernel)")
    print("  Type 'quit' to exit.")
    print("=" * 60)
    print()
    print("Try asking:")
    print('  - "What does serendipity mean?"')
    print('  - "Give me a lesson for day 42 on the learn track"')
    print('  - "Quiz me with 3 multiple choice questions"')
    print('  - "What words are related to courage?"')
    print()

    chat_service = kernel.get_service("chat")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        chat_history.add_user_message(user_input)

        result = await chat_service.get_chat_message_content(
            chat_history=chat_history,
            settings=settings,
            kernel=kernel,
        )

        response = str(result)
        chat_history.add_assistant_message(response)
        print(f"\nTutor: {response}\n")


if __name__ == "__main__":
    asyncio.run(main())
