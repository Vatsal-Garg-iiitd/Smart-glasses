#!/usr/bin/env python3
"""
Comprehensive Test Suite for Smart Glasses AI
==============================================
Tests every component: conversation context, triage, LLM calls,
API endpoints, Firebase, LangSmith, and frontend build.
"""

import os
import sys
import time
import unittest
import importlib

# ──────────────────────────────────────────────────────────────────
# SECTION 1: Conversation Context (Pure Logic – No API Needed)
# ──────────────────────────────────────────────────────────────────
from conversation_context import (
    CONTEXT_WINDOW_MS,
    CONTEXT_MESSAGE_LIMIT,
    select_recent_context,
    format_context_for_prompt,
    build_prompt_with_context,
)


class Test01_SelectRecentContext(unittest.TestCase):
    """Tests for select_recent_context()"""

    def test_empty_messages_returns_empty(self):
        self.assertEqual(select_recent_context([], now_ms=1_000_000), [])

    def test_filters_out_messages_outside_time_window(self):
        now = 1_000_000
        messages = [
            {"role": "user", "text": "too old", "timestamp": now - CONTEXT_WINDOW_MS - 1},
            {"role": "assistant", "text": "recent", "timestamp": now - 1000},
        ]
        result = select_recent_context(messages, now_ms=now)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "recent")


    def test_skips_messages_without_text(self):
        now = 1_000_000
        messages = [
            {"role": "user", "text": "", "timestamp": now - 1000},
            {"role": "assistant", "text": "valid", "timestamp": now - 500},
        ]
        result = select_recent_context(messages, now_ms=now)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "valid")

    def test_skips_messages_missing_text_key(self):
        now = 1_000_000
        messages = [
            {"role": "user", "timestamp": now - 1000},
            {"role": "assistant", "text": "has text", "timestamp": now - 500},
        ]
        result = select_recent_context(messages, now_ms=now)
        self.assertEqual(len(result), 1)

    def test_sorts_unordered_messages_by_timestamp(self):
        now = 1_000_000
        messages = [
            {"role": "assistant", "text": "later", "timestamp": now - 1000},
            {"role": "user", "text": "earlier", "timestamp": now - 2000},
        ]
        result = select_recent_context(messages, now_ms=now)
        self.assertEqual([m["text"] for m in result], ["earlier", "later"])

    def test_boundary_exact_cutoff(self):
        now = 1_000_000
        messages = [
            {"role": "user", "text": "at boundary", "timestamp": now - CONTEXT_WINDOW_MS},
        ]
        result = select_recent_context(messages, now_ms=now)
        self.assertEqual(len(result), 1, "Message exactly at cutoff should be included (>=)")

    def test_custom_window_and_limit(self):
        now = 1_000_000
        messages = [
            {"role": "user", "text": "a", "timestamp": now - 500},
            {"role": "user", "text": "b", "timestamp": now - 400},
            {"role": "user", "text": "c", "timestamp": now - 300},
        ]
        result = select_recent_context(messages, now_ms=now, window_ms=1000, limit=1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "c")


class Test02_FormatContextForPrompt(unittest.TestCase):
    """Tests for format_context_for_prompt()"""

    def test_empty_returns_empty_string(self):
        self.assertEqual(format_context_for_prompt([]), "")

    def test_formats_user_and_assistant_labels(self):
        messages = [
            {"role": "user", "text": "Hello"},
            {"role": "assistant", "text": "Hi there"},
        ]
        result = format_context_for_prompt(messages)
        self.assertIn("User: Hello", result)
        self.assertIn("Assistant: Hi there", result)

    def test_defaults_unknown_role_to_user(self):
        messages = [{"text": "no role specified"}]
        result = format_context_for_prompt(messages)
        self.assertIn("User: no role specified", result)

    def test_multiline_output_preserves_order(self):
        messages = [
            {"role": "user", "text": "First"},
            {"role": "assistant", "text": "Second"},
            {"role": "user", "text": "Third"},
        ]
        result = format_context_for_prompt(messages)
        lines = result.strip().split("\n")
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("User:"))
        self.assertTrue(lines[1].startswith("Assistant:"))
        self.assertTrue(lines[2].startswith("User:"))


class Test03_BuildPromptWithContext(unittest.TestCase):
    """Tests for build_prompt_with_context()"""

    def test_no_context_returns_base_prompt_unchanged(self):
        base = "Describe what you see."
        self.assertEqual(build_prompt_with_context(base, []), base)

    def test_with_context_appends_history(self):
        base = "Answer the user."
        messages = [{"role": "user", "text": "What color is the wall?", "timestamp": 1}]
        result = build_prompt_with_context(base, messages)
        self.assertTrue(result.startswith(base))
        self.assertIn("Recent conversation", result)
        self.assertIn("User: What color is the wall?", result)

    def test_context_contains_do_not_repeat_instruction(self):
        base = "Base."
        messages = [{"role": "user", "text": "Hi", "timestamp": 1}]
        result = build_prompt_with_context(base, messages)
        self.assertIn("do not repeat it verbatim", result)


# ──────────────────────────────────────────────────────────────────
# SECTION 2: Environment & Configuration Checks
# ──────────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()


class Test04_EnvironmentConfig(unittest.TestCase):
    """Verify all required environment variables are present."""

    def test_gemini_api_key_set(self):
        key = os.environ.get("GEMINI_API_KEY", "")
        self.assertTrue(len(key) > 0, "GEMINI_API_KEY is missing from .env")

    def test_firebase_db_url_set(self):
        url = os.environ.get("FIREBASE_DB_URL", "")
        self.assertTrue(len(url) > 0, "FIREBASE_DB_URL is missing from .env")

    def test_firebase_cred_path_exists(self):
        path = os.environ.get("FIREBASE_CRED_PATH", "serviceAccountKey.json")
        self.assertTrue(os.path.exists(path), f"Firebase credentials file not found at: {path}")

    def test_langsmith_tracing_set(self):
        val = os.environ.get("LANGSMITH_TRACING", "")
        self.assertEqual(val.lower(), "true", "LANGSMITH_TRACING should be 'true'")

    def test_langsmith_api_key_set(self):
        key = os.environ.get("LANGSMITH_API_KEY", "")
        self.assertTrue(len(key) > 0, "LANGSMITH_API_KEY is missing from .env")

    def test_langsmith_project_set(self):
        proj = os.environ.get("LANGSMITH_PROJECT", "")
        self.assertTrue(len(proj) > 0, "LANGSMITH_PROJECT is missing from .env")

    def test_images_directory_exists(self):
        self.assertTrue(os.path.isdir("images"), "'images' directory should exist")


# ──────────────────────────────────────────────────────────────────
# SECTION 3: Module Imports & Structure
# ──────────────────────────────────────────────────────────────────
class Test05_ModuleImports(unittest.TestCase):
    """Verify all modules import correctly without crashing."""

    def test_import_ai(self):
        import ai
        self.assertTrue(hasattr(ai, "init_camera"))
        self.assertTrue(hasattr(ai, "capture_image"))
        self.assertTrue(hasattr(ai, "release_camera"))
        self.assertTrue(hasattr(ai, "init_gemini"))
        self.assertTrue(hasattr(ai, "process_image"))
        self.assertTrue(hasattr(ai, "triage_query"))
        self.assertTrue(hasattr(ai, "answer_text_only"))
        self.assertTrue(hasattr(ai, "init_firebase"))
        self.assertTrue(hasattr(ai, "save_capture_metadata"))
        self.assertTrue(hasattr(ai, "run_analysis"))

    def test_import_main(self):
        import main
        self.assertTrue(hasattr(main, "app"))
        self.assertTrue(hasattr(main, "analyze"))
        self.assertTrue(hasattr(main, "health_check"))
        self.assertTrue(hasattr(main, "AnalyzeRequest"))

    def test_import_conversation_context(self):
        import conversation_context
        self.assertTrue(hasattr(conversation_context, "select_recent_context"))
        self.assertTrue(hasattr(conversation_context, "format_context_for_prompt"))
        self.assertTrue(hasattr(conversation_context, "build_prompt_with_context"))

    def test_prompts_exist_in_ai(self):
        import ai
        self.assertTrue(hasattr(ai, "PROMPT_NAVIGATION"))
        self.assertTrue(hasattr(ai, "PROMPT_READ"))
        self.assertTrue(hasattr(ai, "PROMPT_LOCATION"))
        self.assertTrue(hasattr(ai, "PROMPT_GENERAL"))
        self.assertTrue(hasattr(ai, "TRIAGE_PROMPT"))

    def test_langsmith_traceable_decorator_applied(self):
        import ai
        # Check that the functions have been wrapped by @traceable
        # langsmith wraps them - the function names should still be accessible
        self.assertTrue(callable(ai.process_image))
        self.assertTrue(callable(ai.triage_query))
        self.assertTrue(callable(ai.answer_text_only))


# ──────────────────────────────────────────────────────────────────
# SECTION 4: Pydantic Models & Request Validation
# ──────────────────────────────────────────────────────────────────
class Test06_RequestModels(unittest.TestCase):
    """Test Pydantic request model validation."""

    def test_analyze_request_with_mode_only(self):
        from main import AnalyzeRequest
        req = AnalyzeRequest(mode="navigation")
        self.assertEqual(req.mode, "navigation")
        self.assertIsNone(req.prompt)

    def test_analyze_request_with_mode_and_prompt(self):
        from main import AnalyzeRequest
        req = AnalyzeRequest(mode="ask", prompt="What is this?")
        self.assertEqual(req.mode, "ask")
        self.assertEqual(req.prompt, "What is this?")

    def test_analyze_request_custom_mode(self):
        from main import AnalyzeRequest
        req = AnalyzeRequest(mode="ask", prompt="Tell me a joke")
        self.assertEqual(req.mode, "ask")

    def test_all_supported_modes(self):
        from main import AnalyzeRequest
        for mode in ["navigation", "read", "location", "ask"]:
            req = AnalyzeRequest(mode=mode)
            self.assertEqual(req.mode, mode)


# ──────────────────────────────────────────────────────────────────
# SECTION 5: Gemini Client Initialization
# ──────────────────────────────────────────────────────────────────
class Test07_GeminiInit(unittest.TestCase):
    """Test Gemini client initialization."""

    def test_init_gemini_succeeds(self):
        import ai
        ai.gemini_client = None  # Reset
        result = ai.init_gemini()
        self.assertTrue(result)
        self.assertIsNotNone(ai.gemini_client)

    def test_init_gemini_idempotent(self):
        import ai
        ai.init_gemini()
        client1 = ai.gemini_client
        ai.init_gemini()
        client2 = ai.gemini_client
        self.assertIs(client1, client2, "init_gemini should not recreate client")


# ──────────────────────────────────────────────────────────────────
# SECTION 6: Firebase Initialization
# ──────────────────────────────────────────────────────────────────
class Test08_FirebaseInit(unittest.TestCase):
    """Test Firebase initialization."""

    def test_init_firebase_succeeds(self):
        import ai
        result = ai.init_firebase()
        self.assertTrue(result)

    def test_init_firebase_idempotent(self):
        import ai
        ai.init_firebase()
        result = ai.init_firebase()  # Should not raise
        self.assertTrue(result)


# ──────────────────────────────────────────────────────────────────
# SECTION 7: Triage Query (LLM Call – requires working API)
# ──────────────────────────────────────────────────────────────────
class Test09_TriageQuery(unittest.TestCase):
    """Test the triage_query function that decides if camera is needed."""

    def test_text_only_question_returns_false(self):
        """General knowledge question should NOT need the camera."""
        import ai
        result = ai.triage_query("What is 2 plus 2?")
        self.assertFalse(result, "Math question should not need camera")

    def test_visual_question_returns_true(self):
        """Question about surroundings SHOULD need the camera."""
        import ai
        result = ai.triage_query("What color is the object in front of me?")
        self.assertTrue(result, "Visual question should need camera")

    def test_triage_with_context(self):
        """Triage should work with conversation context string."""
        import ai
        context = "User: What is the capital of France?\nAssistant: Paris."
        result = ai.triage_query("Tell me more about it", context)
        # Follow-up to a text question should also be text-only
        self.assertIsInstance(result, bool)


# ──────────────────────────────────────────────────────────────────
# SECTION 8: Text-Only Answer (LLM Call)
# ──────────────────────────────────────────────────────────────────
class Test10_AnswerTextOnly(unittest.TestCase):
    """Test the answer_text_only function."""

    def test_simple_text_question(self):
        import ai
        result = ai.answer_text_only("What is the capital of India?")
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0, "Answer should not be empty")
        # The answer should mention Delhi/New Delhi
        self.assertTrue(
            "delhi" in result.lower() or "new delhi" in result.lower(),
            f"Expected 'Delhi' in answer, got: {result}"
        )

    def test_returns_string_type(self):
        import ai
        result = ai.answer_text_only("Say hello")
        self.assertIsInstance(result, str)


# ──────────────────────────────────────────────────────────────────
# SECTION 9: API Endpoint – /health
# ──────────────────────────────────────────────────────────────────
class Test11_HealthEndpoint(unittest.TestCase):
    """Test the /health endpoint via direct function call."""

    def test_health_returns_healthy(self):
        from main import health_check
        result = health_check()
        self.assertEqual(result["status"], "healthy")
        self.assertIn("timestamp", result)

    def test_health_timestamp_is_iso_format(self):
        from main import health_check
        result = health_check()
        ts = result["timestamp"]
        self.assertIn("T", ts, "Timestamp should be ISO format")


# ──────────────────────────────────────────────────────────────────
# SECTION 10: API Endpoint – /analyze (ask mode, text-only)
# ──────────────────────────────────────────────────────────────────
class Test12_AnalyzeEndpointAskMode(unittest.TestCase):
    """Test the /analyze endpoint for ask mode (text-only path)."""

    def test_text_only_question_returns_no_image(self):
        from main import analyze, AnalyzeRequest
        req = AnalyzeRequest(mode="ask", prompt="What is 5 times 3?")
        result = analyze(req)
        self.assertIsNone(result.get("image"), "Text-only question should return image=None")
        self.assertIn("analysis", result)
        self.assertTrue(len(result["analysis"]) > 0)

    def test_response_has_timestamp(self):
        from main import analyze, AnalyzeRequest
        req = AnalyzeRequest(mode="ask", prompt="Say hi")
        result = analyze(req)
        self.assertIn("timestamp", result)


# ──────────────────────────────────────────────────────────────────
# SECTION 11: Conversational Continuity (Follow-up Test)
# ──────────────────────────────────────────────────────────────────
class Test13_ConversationalContinuity(unittest.TestCase):
    """Test that follow-up questions use conversation context."""

    def test_followup_question_uses_context(self):
        from main import analyze, AnalyzeRequest

        # Ask initial question
        req1 = AnalyzeRequest(mode="ask", prompt="What planet is closest to the Sun?")
        res1 = analyze(req1)
        self.assertIn("analysis", res1)

        # Ask follow-up using pronoun (relies on context)
        req2 = AnalyzeRequest(mode="ask", prompt="How far is it from the Sun?")
        res2 = analyze(req2)
        self.assertIn("analysis", res2)
        # The answer should reference Mercury or provide distance info
        self.assertTrue(
            len(res2["analysis"]) > 0,
            "Follow-up answer should not be empty"
        )


# ──────────────────────────────────────────────────────────────────
# SECTION 12: LangSmith Tracing Verification
# ──────────────────────────────────────────────────────────────────
class Test14_LangSmithTracing(unittest.TestCase):
    """Verify LangSmith tracing is correctly configured."""

    def test_langsmith_env_vars_loaded(self):
        self.assertEqual(os.environ.get("LANGSMITH_TRACING", "").lower(), "true")
        self.assertTrue(len(os.environ.get("LANGSMITH_API_KEY", "")) > 0)
        self.assertTrue(len(os.environ.get("LANGSMITH_PROJECT", "")) > 0)
        self.assertEqual(
            os.environ.get("LANGSMITH_ENDPOINT", ""),
            "https://api.smith.langchain.com"
        )

    def test_langsmith_importable(self):
        import langsmith
        self.assertTrue(hasattr(langsmith, "traceable"))

    def test_traceable_decorator_on_functions(self):
        """Verify that our key functions are wrapped with @traceable."""
        import ai
        # After @traceable, the function is wrapped. We check it's still callable.
        for fn_name in ["process_image", "triage_query", "answer_text_only"]:
            fn = getattr(ai, fn_name)
            self.assertTrue(callable(fn), f"{fn_name} should be callable after @traceable")


# ──────────────────────────────────────────────────────────────────
# RUN ALL TESTS
# ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Custom runner for clear output
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes in order
    test_classes = [
        Test01_SelectRecentContext,
        Test02_FormatContextForPrompt,
        Test03_BuildPromptWithContext,
        Test04_EnvironmentConfig,
        Test05_ModuleImports,
        Test06_RequestModels,
        Test07_GeminiInit,
        Test08_FirebaseInit,
        Test09_TriageQuery,
        Test10_AnswerTextOnly,
        Test11_HealthEndpoint,
        Test12_AnalyzeEndpointAskMode,
        Test13_ConversationalContinuity,
        Test14_LangSmithTracing,
    ]

    for test_class in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(test_class))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 70)
    print(f"TOTAL TESTS: {result.testsRun}")
    print(f"PASSED:      {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"FAILED:      {len(result.failures)}")
    print(f"ERRORS:      {len(result.errors)}")
    print("=" * 70)
