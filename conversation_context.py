"""Conversation context helpers for the live AI chatbot."""

CONTEXT_WINDOW_MS = 5 * 60 * 1000  # 5 minutes
CONTEXT_MESSAGE_LIMIT = 20


def select_recent_context(messages, now_ms, window_ms=CONTEXT_WINDOW_MS, limit=CONTEXT_MESSAGE_LIMIT):
    """Return the last `limit` messages within the time window."""
    if not messages:
        return []

    cutoff = now_ms - window_ms
    recent = [
        msg for msg in messages
        if msg.get("text") and msg.get("timestamp", 0) >= cutoff
    ]
    recent.sort(key=lambda msg: msg["timestamp"])
    return recent[-limit:]


def format_context_for_prompt(messages):
    """Format prior messages as readable conversation history."""
    if not messages:
        return ""

    lines = []
    for msg in messages:
        role = msg.get("role", "user")
        label = "User" if role == "user" else "Assistant"
        lines.append(f"{label}: {msg['text']}")

    return "\n".join(lines)


def build_prompt_with_context(base_prompt, context_messages):
    """Append recent conversation history to the base prompt."""
    context_text = format_context_for_prompt(context_messages)
    if not context_text:
        return base_prompt

    return (
        f"{base_prompt}\n\n"
        "Recent conversation (use this for continuity, do not repeat it verbatim):\n"
        f"{context_text}"
    )
