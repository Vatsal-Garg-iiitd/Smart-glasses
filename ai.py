#!/usr/bin/env python3
"""
Smart Glasses AI Backend Module (ai.py)
=======================================
Helper functions for capturing images, processing them with Gemini,
and saving metadata to Firebase Realtime Database.
"""

import os
import sys
import time
import logging
import asyncio
from dotenv import load_dotenv
import cv2
import firebase_admin
from firebase_admin import credentials, db
from google import genai
from PIL import Image
from langsmith import traceable

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# ─── Configuration ───────────────────────────────────────────────
FIREBASE_CRED_PATH = os.environ.get("FIREBASE_CRED_PATH", "serviceAccountKey.json")
FIREBASE_DB_URL = os.environ.get("FIREBASE_DB_URL", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
CAMERA_INDEX = int(os.environ.get("CAMERA_INDEX", "0"))

# ─── Prompts ─────────────────────────────────────────────────────
PROMPT_NAVIGATION = """You are an AI assistant helping a blind person navigate safely.
Analyze this image and provide clear, concise navigation guidance in 2-3 sentences:
- Is the path ahead clear? Any turns needed?
- Are there obstacles, stairs, people, vehicles, or hazards?
- Give specific directions: go straight, turn left/right, stop, slow down.
- PRIORITY: If there is readable text present, read it to the user and do NOT describe the environment. If the text is in another language, translate it and ONLY output the English translation.
Be direct and actionable. Do not describe the image aesthetically."""

PROMPT_READ = """You are an AI assistant helping a blind person read text.
Look at this image and read ALL visible text clearly and accurately.
If there are multiple text areas, read them in logical order (top to bottom, left to right).
If no text is visible, say 'I don't see any readable text in the current view.'
Just provide the text content, no extra commentary."""

PROMPT_LOCATION = """You are an AI assistant helping a blind person understand their surroundings.
Describe this scene in 2-3 sentences:
- What type of location is this? (indoor/outdoor, room type, street, etc.)
- What are the notable features or landmarks?
- Any useful details for orientation?
Be practical and helpful, not poetic."""

PROMPT_GENERAL = """You are an AI assistant helping a blind person.
Look at this image and describe what is in front of them.
Be clear, concise, and helpful in 2-3 sentences."""

# ─── Globals ─────────────────────────────────────────────────────
camera = None
gemini_client = None

# ─── Camera ──────────────────────────────────────────────────────
def init_camera():
    """Initialize the webcam, cross-platform compatible."""
    global camera
    if camera is not None and camera.isOpened():
        return True

    # Use V4L2 for Linux/Raspberry Pi as GStreamer can crash, otherwise CAP_ANY
    backend = cv2.CAP_V4L2 if sys.platform.startswith("linux") else cv2.CAP_ANY
    logging.info(f"Initializing camera with backend: {backend}")

    for idx in [CAMERA_INDEX, 0, 1, 2]:
        cap = cv2.VideoCapture(idx, backend)
        if cap.isOpened():
            # Set to standard, compatible resolution
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            camera = cap
            logging.info(f"[CAMERA] Camera initialized successfully on index {idx}")
            return True
        cap.release()

    logging.error("[CAMERA] No camera found. Please ensure a webcam is connected.")
    return False

def capture_image(target_path, return_frame=False):
    """Capture a single frame and save it directly to target_path."""
    global camera
    if camera is None or not camera.isOpened():
        logging.error("[CAMERA] Camera is not open or initialized.")
        if return_frame:
            return False, None
        return False

    logging.info("Image capture started...")
    # Flush camera buffer (read a few old frames)
    for _ in range(5):
        camera.read()

    ret, frame = camera.read()
    if not ret:
        logging.error("[CAMERA] Failed to capture image from camera.")
        return False

    # Save frame to path
    success = cv2.imwrite(target_path, frame)
    if success:
        logging.info(f"[CAMERA] Image successfully captured and saved to: {target_path}")
        if return_frame:
            return True, frame
        return True
    else:
        logging.error(f"[CAMERA] Failed to save captured frame to: {target_path}")
        if return_frame:
            return False, None
        return False

def release_camera():
    """Release the camera resources."""
    global camera
    if camera is not None:
        camera.release()
        camera = None
        logging.info("Camera released.")

# ─── Gemini ──────────────────────────────────────────────────────
def init_gemini():
    """Initialize the Gemini GenAI client."""
    global gemini_client
    if gemini_client is not None:
        return True

    if not GEMINI_API_KEY:
        logging.error("[GEMINI] GEMINI_API_KEY environment variable is missing.")
        raise ValueError("Missing GEMINI_API_KEY")

    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    logging.info("[GEMINI] Gemini client initialized.")
    return True

@traceable(name="process_image")
def process_image(image_path, prompt):
    """Analyze image with Gemini using the given prompt."""
    init_gemini()
    try:
        logging.info(f"Sending image to Gemini for analysis...")
        img = Image.open(image_path)
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt, img],
        )
        analysis_text = response.text.strip()
        logging.info(f"[GEMINI] Gemini analysis result: {analysis_text}")
        return analysis_text
    except Exception as e:
        logging.error(f"[GEMINI] Gemini analysis failed: {e}", exc_info=True)
        raise e

# ─── Triage (does the query need an image?) ──────────────────────
TRIAGE_PROMPT = """You are a router for a smart-glasses AI assistant that helps blind users.
Your ONLY job is to decide whether the user's question requires looking through the camera.

Rules:
- If the question asks about something physically in front of the user, nearby objects, text to read, navigation, surroundings, colors, people, or anything that requires SEEING the physical world → reply exactly: YES
- If the question is general knowledge, math, conversation, jokes, definitions, advice, or anything that does NOT require seeing the physical world → reply exactly: NO
- CRITICAL: If there is a "Recent conversation" provided, and the user's question uses pronouns (he/she/it) or asks a follow-up question about the topic being discussed in that conversation, it is general knowledge. Reply exactly: NO

Reply with ONLY the single word YES or NO. Nothing else."""


@traceable(name="triage_query")
def triage_query(user_query, context_prompt=""):
    """Decide whether the user's question requires a camera capture.
    Returns True if an image is needed, False otherwise."""
    init_gemini()
    try:
        full_prompt = f"{TRIAGE_PROMPT}\n\n"
        if context_prompt:
            full_prompt += f"{context_prompt}\n\n"
        full_prompt += f"User question: {user_query}"

        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[full_prompt],
        )
        answer = response.text.strip().upper()
        needs_image = answer.startswith("YES")
        logging.info(f"[TRIAGE] Query: '{user_query}' → needs_image={needs_image} (raw: '{answer}')")
        return needs_image
    except Exception as e:
        logging.error(f"[TRIAGE] Triage call failed, defaulting to image capture: {e}")
        # Safe fallback: capture an image if triage fails
        return True


@traceable(name="answer_text_only")
def answer_text_only(prompt, history=None):
    """Answer a user query with text only (no image), using the Gemini API."""
    init_gemini()
    try:
        logging.info(f"[GEMINI] Sending text-only query to Gemini...")
        
        contents = []
        if history:
            last_role = None
            for msg in history:
                role = "user" if msg.get("role") == "user" else "model"
                if role == last_role:
                    # Combine with previous to ensure strict alternation
                    contents[-1]["parts"][0]["text"] += "\n" + msg.get("text", "")
                else:
                    contents.append({"role": role, "parts": [{"text": msg.get("text", "")}]})
                    last_role = role
                
        # Must alternate: if last was user, append prompt to it
        if contents and contents[-1]["role"] == "user":
            contents[-1]["parts"][0]["text"] += "\n\n" + prompt
        else:
            contents.append({"role": "user", "parts": [{"text": prompt}]})

        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
        )
        result = response.text.strip()
        logging.info(f"[GEMINI] Text-only result: {result}")
        return result
    except Exception as e:
        logging.error(f"[GEMINI] Text-only query failed: {e}", exc_info=True)
        raise e

# ─── Firebase ────────────────────────────────────────────────────
def init_firebase():
    """Initialize Firebase Admin SDK with only DB configuration (no Storage)."""
    try:
        # Check if already initialized to avoid duplicate app errors
        firebase_admin.get_app()
        logging.info("Firebase app already initialized.")
        return True
    except ValueError:
        pass

    if not FIREBASE_DB_URL:
        logging.error("[FIREBASE] FIREBASE_DB_URL environment variable is missing.")
        raise ValueError("Missing FIREBASE_DB_URL")
    if not os.path.exists(FIREBASE_CRED_PATH):
        logging.error(f"[FIREBASE] Firebase service account credentials file not found at: {FIREBASE_CRED_PATH}")
        raise FileNotFoundError(f"Credentials not found: {FIREBASE_CRED_PATH}")

    logging.info(f"Initializing Firebase with DB URL: {FIREBASE_DB_URL}")
    cred = credentials.Certificate(FIREBASE_CRED_PATH)
    firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})
    logging.info("[FIREBASE] Firebase Admin SDK initialized.")
    return True

def save_capture_metadata(filename, image_url, timestamp, analysis):
    """Store capture metadata in Firebase Realtime Database."""
    init_firebase()
    try:
        ref = db.reference("captures")
        payload = {
            "filename": filename,
            "image_url": image_url,
            "timestamp": timestamp,
            "analysis": analysis
        }
        new_ref = ref.push(payload)
        logging.info(f"[FIREBASE] Firebase write status: Success. Created entry {new_ref.key} under /captures")
        return new_ref.key
    except Exception as e:
        logging.error(f"[FIREBASE] Firebase write failed: {e}", exc_info=True)
        raise e

def save_chat_message(role, text, timestamp_ms):
    """Store a single chat message (user or assistant) into Firebase /chat_history."""
    init_firebase()
    try:
        ref = db.reference("chat_history")
        payload = {
            "role": role,
            "text": text,
            "timestamp": timestamp_ms
        }
        ref.push(payload)
        logging.info(f"[FIREBASE] Saved {role} message to /chat_history")
    except Exception as e:
        logging.error(f"[FIREBASE] Failed to save chat message: {e}")

def fetch_recent_chat_history(cutoff_ms, limit):
    """Retrieve recent chat history from Firebase, sorted by timestamp."""
    init_firebase()
    try:
        ref = db.reference("chat_history")
        # Firebase push IDs are chronologically sorted. We can just grab the last N records
        # and filter by timestamp in Python, avoiding the need for strict Firebase indices.
        query = ref.order_by_key().limit_to_last(limit)
        results = query.get()
        
        if not results:
            return []
            
        messages = list(results.values())
        # Filter by cutoff_ms and sort just in case
        valid_messages = [m for m in messages if m.get("timestamp", 0) >= cutoff_ms]
        valid_messages.sort(key=lambda m: m.get("timestamp", 0))
        return valid_messages
    except Exception as e:
        logging.error(f"[FIREBASE] Failed to fetch chat history: {e}")
        return []

# ─── Standalone Test Runner ──────────────────────────────────────
from datetime import datetime

async def run_analysis(mode, user_prompt=None):
    prompts = {
        "navigation": PROMPT_NAVIGATION,
        "read": PROMPT_READ,
        "location": PROMPT_LOCATION,
        "ask": user_prompt or PROMPT_GENERAL
    }

    prompt = prompts.get(mode, PROMPT_GENERAL)

    os.makedirs("images", exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    filename = f"capture_{timestamp}.jpg"
    image_path = os.path.join("images", filename)

    if not init_camera():
        raise Exception("Camera initialization failed")

    if mode != "read":
        success, frame = capture_image(image_path, return_frame=True)
    else:
        success = capture_image(image_path, return_frame=False)
        frame = None

    if not success:
        raise Exception("Image capture failed")

    # Run Gemini and Face Recognition concurrently
    scene_task = asyncio.to_thread(process_image, image_path, prompt)
    
    faces_detected = []
    if mode != "read" and frame is not None:
        from face_recognition import recognize_faces
        face_task = asyncio.to_thread(recognize_faces, frame)
        analysis, faces = await asyncio.gather(scene_task, face_task)
        faces_detected = faces
        if faces:
            names = [f["name"] for f in faces if f["name"] != "Unknown"]
            if names:
                unique_names = list(set(names))
                analysis = f"You're facing {', '.join(unique_names)}. " + analysis
    else:
        analysis = await scene_task

    save_capture_metadata(
        filename=filename,
        image_url=f"/images/{filename}",
        timestamp=timestamp,
        analysis=analysis
    )

    return {
        "image": f"/images/{filename}",
        "analysis": analysis,
        "timestamp": timestamp
    }