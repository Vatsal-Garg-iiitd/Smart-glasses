## Project: Smart Glasses Companion App (React PWA)

# ─────────────────────────────────────────────────────────────
# CONTEXT & GOAL
# ─────────────────────────────────────────────────────────────

Build a React PWA (single HTML page, no backend) that acts as the
voice-controlled interface for a smart glasses system. A Raspberry Pi
runs Gemini AI and pushes results to Firebase Realtime Database. This
app is the phone-based front-end: it listens to the user's voice,
writes commands to Firebase, and reads AI responses back aloud.

The user is visually impaired or hands-free. Every interaction must be
accessible by voice and audio feedback alone. Do NOT rely on the user
reading text on screen — audio is the primary output channel.

# ─────────────────────────────────────────────────────────────
# TECH STACK
# ─────────────────────────────────────────────────────────────

- Framework: React (functional components + hooks)
- Styling: Tailwind CSS (dark theme, large touch targets ≥ 48px)
- Database: Firebase Realtime Database (the ONLY backend)
- Voice Input: Web Speech API (SpeechRecognition)
- Audio Output: Web Speech API (SpeechSynthesis) for TTS
- Audio Cues: Web Audio API (AudioContext) for earcons
- Build: Vite

# ─────────────────────────────────────────────────────────────
# FIREBASE SETUP
# ─────────────────────────────────────────────────────────────

Install Firebase SDK: npm install firebase

Create src/firebase.js with a config object using these placeholder
keys — the user will replace them with their real values:

  const firebaseConfig = {
    apiKey: "YOUR_API_KEY",
    authDomain: "YOUR_AUTH_DOMAIN",
    databaseURL: "YOUR_DATABASE_URL",
    projectId: "YOUR_PROJECT_ID",
    storageBucket: "YOUR_STORAGE_BUCKET",
    messagingSenderId: "YOUR_MESSAGING_SENDER_ID",
    appId: "YOUR_APP_ID"
  };

Export app and db (the Realtime Database instance) from this file.
Leave a // TODO: Replace with your Firebase config comment above it.

# ─────────────────────────────────────────────────────────────
# FIREBASE DATABASE SCHEMA (do NOT change these paths)
# ─────────────────────────────────────────────────────────────

/session/command  →  Object the app WRITES to trigger Raspberry Pi
                      Example: { type: "read", status: "pending" }
                      Example: { type: "general", text: "Describe what is in front of me", status: "pending" }

/session/command/status  →  String the Pi WRITES back. Listen for:
                      "pending" | "processing" | "done" | "error"

/session  →  Object the app WRITES to toggle Navigation Mode
                      Example: { mode: "navigation", navigation_active: true }
                      Example: { mode: "normal", navigation_active: false }

/messages/{id}   →  Object the Pi WRITES with AI response:
                      { text: "The sign says EXIT.", spoken: false, timestamp: 1234567890 }
                      App must SET spoken: true after reading the message aloud.

# ─────────────────────────────────────────────────────────────
# COMMAND TYPES & MODES (what the Pi understands)
# ─────────────────────────────────────────────────────────────

| Command type    | When to send                                        |
|-----------------|-----------------------------------------------------|
| "read"          | User says "read sign" / "what does that say"        |
| "location"      | User says "describe" / "what is in front of me"    |
| "general"       | Any other spoken query (pass full text)       |

*Note: For navigation (e.g. "navigate" / "help me walk"), do NOT send a command. Instead, update the session mode as described in the schema.*

Map voice input to these types using keyword matching. Unmatched
queries always fall back to type "general" with the full transcript
included as the `text` field.

# ─────────────────────────────────────────────────────────────
# FEATURE 1: VOICE INPUT (Speech-to-Text)
# ─────────────────────────────────────────────────────────────

Use the browser's SpeechRecognition API (webkit prefix fallback included).

- Show a large microphone button as the primary UI element (≥ 80px diameter)
- On tap/click: start recognition, show animated "listening" state
- On result: display the transcript text on screen (for sighted companions)
  then immediately parse and send the command to Firebase
- On error: announce via TTS: "Sorry, I didn't catch that. Please try again."
- Set continuous: false, interimResults: false
- Announce via TTS when mic is ready: "Ready. Tap to speak."

# ─────────────────────────────────────────────────────────────
# FEATURE 2: FIREBASE WRITE (Sending Commands & Navigation)
# ─────────────────────────────────────────────────────────────

When a voice command is parsed, call a sendCommand(type, text?) function:

1. If navigating: update(ref(db, '/session'), { mode: "navigation", navigation_active: true })
2. If normal command: set(ref(db, '/session/command'), { type, status: "pending", text })
2. Immediately play the SHUTTER earcon (see Audio Cues section)
3. Update local UI state to "command sent"
4. If Firebase write fails → announce via TTS: "Connection error. Please check your network."

# ─────────────────────────────────────────────────────────────
# FEATURE 3: FIREBASE LISTENERS (Real-time)
# ─────────────────────────────────────────────────────────────

Set up TWO real-time listeners in a useEffect on app mount. Clean them
up in the useEffect return function.

Listener A — /session/command/status
  onValue(ref(db, '/session/command/status'), (snapshot) => { ... })
  - If value is "processing" → play THINKING earcon
  - If value is "error" → announce via TTS: "Something went wrong. Please try again."
  - If value is "done" → do nothing here (messages listener handles output)

Listener B — /messages
  onValue(ref(db, '/messages'), (snapshot) => { ... })
  - Loop through all messages where spoken === false
  - Sort by timestamp ascending (speak oldest first)
  - For each unspoken message:
    1. Play SUCCESS earcon
    2. Speak the message text via TTS (do NOT start next message until this one finishes)
    3. After TTS ends (use the onend event), call:
       update(ref(db, `/messages/${id}`), { spoken: true })
  - CRITICAL: Use a queue or sequential promise chain — never speak two
    messages simultaneously. Only mark spoken:true AFTER the utterance ends.

# ─────────────────────────────────────────────────────────────
# FEATURE 4: TEXT-TO-SPEECH ENGINE
# ─────────────────────────────────────────────────────────────

Create a useTTS() custom hook that wraps SpeechSynthesis:

  speak(text, onEnd?)
    - Cancel any current utterance first
    - Create a new SpeechSynthesisUtterance
    - Set rate: 1.1, pitch: 1.0, volume: 1.0
    - Prefer a local language voice (en-US or en-GB)
    - Call onEnd callback when utterance finishes
    - Expose isSpeaking state

  cancel()
    - window.speechSynthesis.cancel()

Handle the Chrome mobile bug: call window.speechSynthesis.resume()
every 10 seconds while a long utterance is playing (use setInterval inside
the utterance, cleared on onend).

# ─────────────────────────────────────────────────────────────
# FEATURE 5: AUDIO CUES (Earcons via Web Audio API)
# ─────────────────────────────────────────────────────────────

Create a useAudioCues() custom hook using AudioContext. Generate all
sounds programmatically — no external audio files needed.

SHUTTER earcon (plays when command is sent):
  Two short oscillator bursts — a quick "click-click" effect.
  OscillatorNode, type: "square", freq 800Hz → 400Hz, duration 60ms each,
  with 10ms gap. Gain envelope: fast attack (5ms), fast decay.

THINKING earcon (plays when status = "processing"):
  A gentle ascending three-note chime (C4 → E4 → G4), each note 150ms,
  OscillatorNode type "sine". Signals "please wait."

SUCCESS earcon (plays just before reading AI response):
  A bright two-note chime (G4 → C5), each 200ms, sine wave.
  Signals "here comes the answer."

IMPORTANT: Create AudioContext lazily on first user gesture (tap) to
comply with browser autoplay policy. Store it in a ref. Resume it if
suspended: if (ctx.state === 'suspended') await ctx.resume()

# ─────────────────────────────────────────────────────────────
# UI DESIGN REQUIREMENTS
# ─────────────────────────────────────────────────────────────

Dark theme, high contrast. The user might be handing the phone to
someone else to read, but audio is primary.

Layout (single screen, no navigation):

  ┌─────────────────────────────────────┐
  │  SMART GLASSES          [status dot] │  ← header, shows Firebase connection
  │                                      │
  │        [BIG MIC BUTTON]              │  ← 96px circle, pulse animation when listening
  │     "Tap to speak"                   │
  │                                      │
  │  Last command: "read sign"           │  ← shows transcript
  │  Status: Processing...               │  ← shows /session/command/status
  │                                      │
  │  ──── Last Response ────             │
  │  "The sign says Emergency Exit."     │  ← shows most recent message text
  │                                      │
  │  [STOP] [READ AGAIN]                 │  ← stop TTS / replay last message
  └─────────────────────────────────────┘

Tailwind classes guidance:
- Background: bg-gray-950
- Mic button idle: bg-indigo-600 hover:bg-indigo-500
- Mic button listening: bg-red-500 with animate-pulse
- Status dot: green=connected, yellow=processing, red=error
- All text: text-white or text-gray-300
- Touch targets: min-h-[48px] min-w-[48px] on all interactive elements

# ─────────────────────────────────────────────────────────────
# APP STATE SHAPE (use useState or useReducer)
# ─────────────────────────────────────────────────────────────

  {
    isListening: boolean,       // mic is recording
    isSpeaking: boolean,        // TTS is playing
    transcript: string,         // last voice input
    status: string,             // Firebase /session/command/status value
    lastResponse: string,       // most recent message text shown on screen
    isConnected: boolean,       // Firebase connection state
    error: string | null        // any error message
  }

# ─────────────────────────────────────────────────────────────
# FILE STRUCTURE
# ─────────────────────────────────────────────────────────────

src/
  firebase.js          ← Firebase init + exports db
  hooks/
    useTTS.js          ← SpeechSynthesis wrapper
    useAudioCues.js    ← Web Audio earcons
    useSpeechInput.js  ← SpeechRecognition wrapper
    useFirebase.js     ← all Firebase read/write + listeners
  App.jsx              ← top-level component, composes hooks
  main.jsx
  index.css            ← Tailwind directives
index.html
vite.config.js
tailwind.config.js
package.json
README.md             ← setup instructions + Firebase config steps

# ─────────────────────────────────────────────────────────────
# EDGE CASES TO HANDLE
# ─────────────────────────────────────────────────────────────

1. Browser support: Check for SpeechRecognition and SpeechSynthesis on
   mount. If not supported, show a message: "Please use Chrome on Android
   for the best experience."

2. Mic permission denied: Catch the NotAllowedError, announce via TTS
   (if TTS works): "Microphone access was denied. Please enable it in
   browser settings." Show the same message on screen.

3. Firebase offline: Listen to .info/connected in Firebase to track
   connection state. Update the status dot accordingly. Announce once
   when connection drops: "Lost connection to glasses."

4. Duplicate messages: The /messages listener fires on every db change.
   Keep a Set of already-spoken message IDs in a ref to avoid replaying.

5. AudioContext autoplay: Initialize only after a user tap. Show "Tap
   anywhere to enable audio" overlay on first load that dismisses on
   any tap and initializes AudioContext.

6. Speaking queue race condition: If a new message arrives while TTS
   is still speaking, add it to a queue array. Process queue items
   sequentially — never call speak() while isSpeaking is true.

# ─────────────────────────────────────────────────────────────
# README REQUIREMENTS
# ─────────────────────────────────────────────────────────────

Write a README.md with:
1. Prerequisites (Node 18+, npm, Firebase project)
2. Step-by-step: how to create a Firebase Realtime Database
3. Where to paste the Firebase config (src/firebase.js)
4. How to run: npm install && npm run dev
5. How to build for production: npm run build
6. Browser compatibility note (Chrome on Android recommended)
7. A description of the 3 earcon sounds and what they mean
