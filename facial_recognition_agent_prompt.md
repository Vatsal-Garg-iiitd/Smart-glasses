# Agent Prompt: Add Face Recognition to Smart Glasses Backend

Copy everything below the line into your agentic coding tool (Claude Code, etc.), pointed at the `Smart-glasses` repo.

---

## Project Context

This is my smart glasses backend for a blind-assistance device (repo: `Smart-glasses`). Current structure:

- **`main.py`** — FastAPI app, the current active entrypoint. Single unified `POST /analyze` endpoint that handles four modes:
  - `navigation`, `read`, `location` → always capture + analyze a frame
  - `ask` → triages the user's text query first (via `triage_query` in `ai.py`) and only captures a frame if the LLM decides the question needs visual context
  - Also exposes `POST /trigger-wake-word` and a `GET /events` SSE stream that the React frontend listens to for wake-word triggers.
- **`ai.py`** — core helpers: OpenCV camera init/capture (`init_camera`, `capture_image`, `release_camera`), Gemini client (`google-genai`, model `gemini-2.5-flash`) via `process_image(image_path, prompt)`, the triage function, `answer_text_only` for text-only queries, and Firebase Realtime Database helpers (`save_chat_message`, `fetch_recent_chat_history`, `save_capture_metadata`). Gemini-calling functions are wrapped in `@traceable` (LangSmith) for observability. Prompt templates: `PROMPT_NAVIGATION`, `PROMPT_READ`, `PROMPT_LOCATION`, `PROMPT_GENERAL`.
- **`conversation_context.py`** — pure helper functions that build a short conversation-context window from recent Firebase chat history, appended to prompts for continuity.
- **`wake_word.py`** — standalone script using `SpeechRecognition`, listens for "hey lens" and POSTs to the backend's `/trigger-wake-word` on `raspy.local` — i.e., the backend runs directly on the capture device itself and calls Gemini's cloud API over the network. There is no separate "companion device" tier — just device → Gemini cloud.
- **`Frontend/`** — React PWA, calls `/analyze` and listens to `/events` for wake-word triggers.
- **`requirements.txt`**: firebase-admin, google-genai, Pillow, python-dotenv, fastapi, uvicorn, opencv-python, langsmith, SpeechRecognition, PyAudio.
- **`api .py`** (note the space in the filename) — this looks like an earlier draft of `main.py` (older `/capture` endpoint, in-memory `conversation_history` list instead of Firebase, no triage/wake-word/SSE). Treat `main.py` + `ai.py` as the source of truth. Don't build face recognition into `api .py` — check with me before touching it at all; it may just be dead code to delete.

Read all of these files before writing anything, and match their existing conventions: bracket-tagged logging (`logging.info(f"[TAG] message")`), `@traceable` on functions that do model inference, lazy global-singleton init pattern (like `init_camera`/`init_gemini`), and config via `python-dotenv` / `os.environ.get(...)`.

## Goal

Add embedding + similarity-based face recognition, integrated into the existing `/analyze` flow, with **face recognition and the existing Gemini scene analysis running in parallel on the same captured frame**, not sequentially.

## Why parallel matters here specifically

`process_image()` is mostly a network round-trip to Gemini's cloud API — the device's CPU is idle while waiting on that response. Face detection + embedding is local CPU-bound work. These two workloads don't compete for the same resource (network wait vs. local compute), so running them concurrently is a genuine efficiency win, not just cosmetic parallelism. Use `asyncio.gather` with each blocking call wrapped in `asyncio.to_thread(...)` (both the existing Gemini call and the new face-recognition call are synchronous/blocking, matching the current codebase's style — don't rewrite them as native async, just offload them to threads and run concurrently).

Concretely:
- `main.py`'s `analyze()` endpoint is currently a plain `def` (FastAPI runs it in its own threadpool implicitly). Convert it to `async def` and explicitly parallelize the two sub-tasks inside it — don't rely on FastAPI's implicit threading for this, since we need both results before responding.
- Face detection/embedding is CPU-bound; OpenCV and ONNX Runtime both release the GIL during their C-level compute, so a true thread-level concurrent execution alongside the network-bound Gemini call is realistic here, not just interleaving.

## Required Changes

### 1. New module: `face_recognition.py`
Mirror `ai.py`'s style. Should contain:
- **Face detector**: something lightweight enough for the device this runs on (I'm using this on hardware with real memory/CPU constraints — ask me to confirm current specs before locking in a model choice; don't assume workstation-class hardware). Candidates: MediaPipe Face Detection (BlazeFace) or OpenCV's YuNet. Pick one, justify it, keep it swappable.
- **Alignment**: use landmarks to crop/align faces to the embedding model's expected input size.
- **Embedding model**: run via **ONNX Runtime**. Candidates: ArcFace (InsightFace `buffalo_s`/`buffalo_sc` for a lighter footprint) or MobileFaceNet. Present the accuracy/speed/size tradeoff and let me pick before committing.
- **Similarity matching**: cosine similarity against stored embeddings, configurable threshold (tunable parameter, not hardcoded), support multiple stored embeddings per person (average or max similarity across them).
- A single entry point: `recognize_faces(frame) -> list[{bbox, name_or_unknown, confidence}]` that takes a raw frame (numpy array from OpenCV — see point 2), not a file path, to avoid an extra disk read.
- Wrap the inference-calling function in `@traceable`, same as `process_image` and `triage_query`, so it shows up in the same LangSmith traces.

### 2. Modify the capture path to expose the raw frame
`capture_image(target_path)` in `ai.py` currently only writes to disk and returns a bool. Face recognition needs the in-memory frame too, so it shouldn't have to re-read the JPEG back off disk. Propose a change (e.g., have it optionally also return the captured frame array, or add a small wrapper) — but this function is used elsewhere in the codebase, so show me the diff and confirm before changing its signature.

### 3. Wire parallel execution into `main.py`
In the `/analyze` endpoint, wherever a frame is captured for `navigation`/`read`/`location`/triaged-`ask`:
```python
scene_task = asyncio.to_thread(process_image, image_path, prompt)
face_task = asyncio.to_thread(recognize_faces, frame)
analysis, faces = await asyncio.gather(scene_task, face_task)
```
(adapt to however `run_analysis`/the mode dispatch is actually structured — read the current control flow closely rather than assuming this drops in verbatim).

### 4. Merge results before responding
Combine the Gemini scene description with any recognized name(s) into one coherent response before it's saved via `save_chat_message`/`save_capture_metadata` and returned to the frontend for TTS. Keep this merge deterministic/rule-based (e.g., prepend "You're facing `<name>`." when a confident match exists) rather than routing the face-match result back through Gemini — we already decided identity matching shouldn't go through the LLM.
- Open question for the `read` mode: face recognition is probably irrelevant when the user is asking to read text. Decide whether to skip the face-recognition pass for that mode to save compute, and tell me your reasoning rather than silently doing one or the other.

### 5. Enrollment
- Add a new endpoint (e.g. `POST /enroll`) to `main.py` for capturing N frames of a person, embedding them, and storing them tagged with a name.
- Given Firebase is already this project's database, store enrolled embeddings there under a new node (e.g. `/enrolled_faces`) for consistency with `save_chat_message`/`save_capture_metadata` — unless you think local storage is clearly better here, in which case say why before switching.
- Support listing and deleting enrolled people (this is other people's biometric data — enrollment must be an explicit action, not silent background collection, and deletion must be straightforward).
- Add a corresponding UI flow in `Frontend/` consistent with its existing structure — look at what's there before adding new components.

### 6. Testing
Follow the existing `test_*.py` convention in the repo (e.g. `test_comprehensive.py`, `test_conversation_context.py`). Add a `test_face_recognition.py` with:
- Unit tests for the similarity math (identical image → similarity ≈ 1.0; different people → below threshold)
- A small labeled-image accuracy eval to help me calibrate the threshold (report true accept / false accept / false reject rates)

### 7. Dependencies
Add whatever's needed (likely `onnxruntime`, `insightface` or equivalent, `numpy` if not already pulled in transitively) to `requirements.txt`, matching the plain flat-list style already there.

## Constraints
- Python, matching the rest of the codebase.
- Use established pretrained models (InsightFace/ONNX Runtime/OpenCV) — no training or fine-tuning.
- Don't touch `api .py` beyond flagging it as likely dead code.
- Ask before changing the signature of any function used elsewhere in the codebase (like `capture_image`).
- Ask me to confirm actual hardware specs before locking in a specific detector/embedder — don't assume.
