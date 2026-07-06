#!/usr/bin/env python3
"""
Smart Glasses AI API (api.py)
============================
FastAPI backend for triggering captures, serving images, and analyzing
them using the Gemini API.
"""

import os
import sys
import logging
import datetime
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Import core helpers from ai.py
from ai import (
    init_camera,
    capture_image,
    process_image,
    save_capture_metadata,
    init_firebase,
    init_gemini,
    release_camera,
    PROMPT_NAVIGATION,
    PROMPT_READ,
    PROMPT_LOCATION,
    PROMPT_GENERAL,
)
from conversation_context import select_recent_context, build_prompt_with_context

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

IMAGES_DIR = "images"

# Ensure images directory exists before mounting StaticFiles
if not os.path.exists(IMAGES_DIR):
    try:
        os.makedirs(IMAGES_DIR)
        logging.info(f"Created static images directory: {IMAGES_DIR}")
    except Exception as e:
        logging.error(f"[API] Failed to create directory '{IMAGES_DIR}': {e}")
        sys.exit(1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle event handler for FastAPI."""
    logging.info("Starting up Smart Glasses AI API backend...")

    # Initialize components
    try:
        init_firebase()
    except Exception as e:
        logging.error(f"[API] Firebase initialization failed: {e}")
        
    try:
        init_gemini()
    except Exception as e:
        logging.error(f"[API] Gemini initialization failed: {e}")
        
    try:
        init_camera()
    except Exception as e:
        logging.error(f"[API] Camera initialization failed: {e}")
        
    yield
    
    # Shutdown
    logging.info("Shutting down Smart Glasses AI API backend...")
    release_camera()


app = FastAPI(
    title="Smart Glasses AI API",
    description="Backend API for Smart Glasses blind assistance project",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration to allow all origins for easy development and access across same Wi-Fi
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the images directory as static files under /images
# Example: http://<backend-ip>:8000/images/capture_20260616_183000.jpg
app.mount(f"/{IMAGES_DIR}", StaticFiles(directory=IMAGES_DIR), name=IMAGES_DIR)

# Global conversation history to maintain context
conversation_history = []

class CaptureRequest(BaseModel):
    mode: Optional[str] = "navigation"  # Supports: navigation, read, location, general
    custom_prompt: Optional[str] = None

class CaptureResponse(BaseModel):
    image_url: str
    analysis: str
    timestamp: str

@app.post("/capture", response_model=CaptureResponse)
async def capture_and_analyze(request: CaptureRequest):
    logging.info(f"[API] Frontend request received: mode={request.mode}")
    
    # 1. Ensure camera is initialized
    if not init_camera():
        logging.error("[API] Camera is unavailable.")
        raise HTTPException(status_code=503, detail="Camera is currently unavailable.")

    # 2. Setup timestamps and filenames
    now = datetime.datetime.now(datetime.timezone.utc)
    timestamp_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    file_timestamp = now.strftime("%Y%m%d_%H%M%S")
    filename = f"capture_{file_timestamp}.jpg"
    target_path = os.path.join(IMAGES_DIR, filename)

    # 3. Capture image
    try:
        success = capture_image(target_path)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to capture image from camera.")
    except Exception as e:
        logging.error(f"[API] Failed to capture image: {e}")
        raise HTTPException(status_code=500, detail=f"Image capture failed: {str(e)}")

    # 4. Map mode to prompt
    if request.custom_prompt:
        prompt = request.custom_prompt
        user_text = request.custom_prompt
    elif request.mode == "read":
        prompt = PROMPT_READ
        user_text = "[Read Text Mode]"
    elif request.mode == "location":
        prompt = PROMPT_LOCATION
        user_text = "[Location Mode]"
    elif request.mode == "general":
        prompt = PROMPT_GENERAL
        user_text = "[General Mode]"
    else:
        prompt = PROMPT_NAVIGATION
        user_text = "[Navigation Mode]"

    # 4.5 Build context-aware prompt
    now_ms = int(now.timestamp() * 1000)
    recent_context = select_recent_context(conversation_history, now_ms)
    context_aware_prompt = build_prompt_with_context(prompt, recent_context)

    # 5. Process with Gemini
    try:
        analysis_result = process_image(target_path, context_aware_prompt)
        
        # Update conversation history
        conversation_history.append({"role": "user", "text": user_text, "timestamp": now_ms})
        conversation_history.append({"role": "assistant", "text": analysis_result, "timestamp": now_ms})
    except Exception as e:
        logging.error(f"[API] Gemini analysis failed: {e}")
        # Clean up captured image since analysis failed
        if os.path.exists(target_path):
            os.remove(target_path)
        raise HTTPException(status_code=502, detail=f"Gemini API failure: {str(e)}")

    # 6. Store metadata in Firebase
    image_url_path = f"/{IMAGES_DIR}/{filename}"
    try:
        save_capture_metadata(
            filename=filename,
            image_url=image_url_path,
            timestamp=timestamp_str,
            analysis=analysis_result
        )
    except Exception as e:
        logging.error(f"[API] Firebase metadata write failed: {e}")
        # We don't fail the request completely since image and analysis succeeded,
        # but we warn the client or include a note.

    # 7. Return response
    return CaptureResponse(
        image_url=image_url_path,
        analysis=analysis_result,
        timestamp=timestamp_str
    )

@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "camera_connected": init_camera()
    }
