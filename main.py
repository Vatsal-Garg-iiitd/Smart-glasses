import os
import datetime
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import asyncio

from ai import (
    run_analysis,
    release_camera,
    init_camera,
    init_gemini,
    init_firebase,
    capture_image,
    process_image,
    triage_query,
    answer_text_only,
    PROMPT_GENERAL,
    save_chat_message,
    fetch_recent_chat_history,
)
from conversation_context import build_prompt_with_context, CONTEXT_WINDOW_MS, CONTEXT_MESSAGE_LIMIT

IMAGES_DIR = "images"
os.makedirs(IMAGES_DIR, exist_ok=True)



@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_firebase()
    except Exception:
        pass
    try:
        init_gemini()
    except Exception:
        pass
    try:
        init_camera()
    except Exception:
        pass
    yield
    release_camera()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")


class AnalyzeRequest(BaseModel):
    mode: str
    prompt: str | None = None


@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    """
    Unified analysis endpoint.
    - navigation / read / location  → always capture + analyze image
    - ask (custom prompt)           → triage first; only capture if the LLM says the query needs visual context
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    now_ms = int(now.timestamp() * 1000)

    # Build conversation context for continuity from Firebase
    cutoff_ms = now_ms - CONTEXT_WINDOW_MS
    recent_context = fetch_recent_chat_history(cutoff_ms, CONTEXT_MESSAGE_LIMIT)

    # ── Modes that ALWAYS need the camera ──
    if request.mode in ("navigation", "read", "location"):
        result = run_analysis(request.mode, request.prompt)

        # Store in Firebase conversation history
        user_text = f"[{request.mode.title()} Mode]"
        save_chat_message("user", user_text, now_ms)
        save_chat_message("assistant", result["analysis"], now_ms + 1) # slightly offset timestamp to maintain order

        return result

    # ── "ask" / custom mode: let the LLM decide if it needs the camera ──
    user_query = request.prompt or "Describe what you see"

    # Build context string for triage and answering
    context_prompt = build_prompt_with_context("", recent_context).strip()

    needs_image = triage_query(user_query, context_prompt)
    logging.info(f"[ANALYZE] Triage result for '{user_query}': needs_image={needs_image}")

    if needs_image:
        # Capture image and analyze with the user's question
        visual_prompt = (
            f"{PROMPT_GENERAL}\n\n"
            f"The user specifically asked: {user_query}"
        )
        context_aware_prompt = build_prompt_with_context(visual_prompt, recent_context)
        result = run_analysis("ask", context_aware_prompt)

        # Store in conversation history
        conversation_history.append({"role": "user", "text": user_query, "timestamp": now_ms})
        conversation_history.append({"role": "assistant", "text": result["analysis"], "timestamp": now_ms})

        return result
    else:
        # Text-only answer — no camera needed
        text_prompt = (
            "You are an AI assistant helping a blind person. "
            "Answer the following question clearly and concisely.\n\n"
            f"Question: {user_query}"
        )
        try:
            answer = answer_text_only(text_prompt, history=recent_context)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Gemini API failure: {str(e)}")

        # Store in Firebase conversation history
        save_chat_message("user", user_query, now_ms)
        save_chat_message("assistant", answer, now_ms + 1)

        return {
            "image": None,
            "analysis": answer,
            "timestamp": now.strftime("%Y%m%d_%H%M%S"),
        }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


# ─── Wake Word Trigger Events ───
wake_word_event = asyncio.Event()

@app.post("/trigger-wake-word")
async def trigger_wake_word():
    """Endpoint called by the background Python script when 'hey lens' is detected."""
    wake_word_event.set()
    return {"status": "triggered"}

async def sse_event_generator():
    while True:
        await wake_word_event.wait()
        wake_word_event.clear()
        yield "data: trigger\n\n"

@app.get("/events")
async def sse_events():
    """SSE endpoint for the React frontend to listen for wake word triggers."""
    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")