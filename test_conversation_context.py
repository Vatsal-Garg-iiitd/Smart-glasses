#!/usr/bin/env python3
"""Tests for conversation context selection and prompt building."""

import unittest

from conversation_context import (
    CONTEXT_MESSAGE_LIMIT,
    CONTEXT_WINDOW_MS,
    build_prompt_with_context,
    format_context_for_prompt,
    select_recent_context,
)


class TestSelectRecentContext(unittest.TestCase):
    def test_empty_messages(self):
        self.assertEqual(select_recent_context([], now_ms=1_000_000), [])

    def test_filters_messages_outside_window(self):
        now = 1_000_000
        messages = [
            {"role": "user", "text": "old", "timestamp": now - CONTEXT_WINDOW_MS - 1},
            {"role": "assistant", "text": "recent", "timestamp": now - 1000},
        ]
        result = select_recent_context(messages, now_ms=now)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "recent")

    def test_returns_last_two_messages_in_window(self):
        now = 2_000_000
        messages = [
            {"role": "user", "text": "first", "timestamp": now - 4000},
            {"role": "assistant", "text": "second", "timestamp": now - 3000},
            {"role": "user", "text": "third", "timestamp": now - 2000},
            {"role": "assistant", "text": "fourth", "timestamp": now - 1000},
        ]
        result = select_recent_context(messages, now_ms=now)
        self.assertEqual(len(result), CONTEXT_MESSAGE_LIMIT)
        self.assertEqual([msg["text"] for msg in result], ["third", "fourth"])

    def test_skips_messages_without_text(self):
        now = 1_000_000
        messages = [
            {"role": "user", "text": "", "timestamp": now - 1000},
            {"role": "assistant", "text": "valid", "timestamp": now - 500},
        ]
        result = select_recent_context(messages, now_ms=now)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "valid")

    def test_sorts_unordered_messages(self):
        now = 1_000_000
        messages = [
            {"role": "assistant", "text": "later", "timestamp": now - 1000},
            {"role": "user", "text": "earlier", "timestamp": now - 2000},
        ]
        result = select_recent_context(messages, now_ms=now)
        self.assertEqual([msg["text"] for msg in result], ["earlier", "later"])


class TestFormatContextForPrompt(unittest.TestCase):
    def test_empty_context(self):
        self.assertEqual(format_context_for_prompt([]), "")

    def test_formats_roles(self):
        messages = [
            {"role": "user", "text": "What is ahead?"},
            {"role": "assistant", "text": "A hallway."},
        ]
        formatted = format_context_for_prompt(messages)
        self.assertIn("User: What is ahead?", formatted)
        self.assertIn("Assistant: A hallway.", formatted)


class TestBuildPromptWithContext(unittest.TestCase):
    def test_no_context_returns_base_prompt(self):
        base = "Describe the scene."
        self.assertEqual(build_prompt_with_context(base, []), base)

    def test_with_context_appends_history(self):
        base = "Respond to the user."
        messages = [{"role": "user", "text": "What did you say?", "timestamp": 1}]
        prompt = build_prompt_with_context(base, messages)
        self.assertTrue(prompt.startswith(base))
        self.assertIn("User: What did you say?", prompt)


if __name__ == "__main__":
    unittest.main()
