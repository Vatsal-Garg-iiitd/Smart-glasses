import { useState, useEffect, useCallback } from 'react';
import { useTTS } from './hooks/useTTS';
import { useAudioCues } from './hooks/useAudioCues';
import { useSpeechInput } from './hooks/useSpeechInput';
import { analyze } from './services/api';
import EnrollmentView from './EnrollmentView';

// Base URL for API requests
const API_BASE_URL = 'http://raspy.local:8000';

function getFullImageUrl(path) {
  if (!path) return '';
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  // Prepend backend base url for local paths (e.g. /images/...)
  return `${API_BASE_URL}${path}`;
}

function App() {
  // Mode configuration
  const [activeMode, setActiveMode] = useState('navigation'); // 'navigation' | 'read' | 'location' | 'custom'
  const [customPromptText, setCustomPromptText] = useState('');
  const [isAutoCaptureActive, setIsAutoCaptureActive] = useState(true);
  
  // Application state
  const [transcript, setTranscript] = useState('');
  const [lastResponse, setLastResponse] = useState('');
  const [lastImageUrl, setLastImageUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showOverlay, setShowOverlay] = useState(true);
  const [showEnrollment, setShowEnrollment] = useState(false);

  // Audio & TTS hooks
  const { initAudio, playShutter, playThinking, playSuccess } = useAudioCues();
  const { speak, cancel, isSpeaking } = useTTS();

  // Firebase captures removed as per instructions

  // Unified capture & analysis trigger
  const triggerCapture = useCallback(async (modeToUse, customText = '') => {
    if (loading) return;
    
    setLoading(true);
    setError(null);
    cancel(); // Stop any current speech
    
    // Play audio cues – skip shutter for Ask AI since camera may not be used
    if (modeToUse !== 'custom') {
      playShutter();
    }
    playThinking();

    try {
      // Send 'ask' mode to backend for custom prompts so triage decides if camera is needed
      const apiMode = modeToUse === 'custom' ? 'ask' : modeToUse;
      const promptToSend = modeToUse === 'custom' ? (customText || customPromptText) : undefined;
      const data = await analyze(apiMode, promptToSend);
      playSuccess();

      setLastResponse(data.analysis);
      // Backend returns .image as null when no photo was needed
      setLastImageUrl(data.image || '');
      
      // Automatic Text-To-Speech readout of result
      speak(data.analysis);
    } catch (err) {
      console.error("Capture trigger failed:", err);
      const errMsg = err.message || "Failed to capture and analyze image.";
      setError(errMsg);
      speak("Error. Failed to process request.");
    } finally {
      setLoading(false);
    }
  }, [loading, customPromptText, playShutter, playThinking, playSuccess, speak, cancel]);

  // Continuous navigation mode
  useEffect(() => {
    let interval;
    if (activeMode === "navigation" && isAutoCaptureActive) {
      interval = setInterval(() => {
        triggerCapture("navigation");
      }, 3000);
    }
    return () => clearInterval(interval);
  }, [activeMode, isAutoCaptureActive, triggerCapture]);

  // Voice commands mapping to the capture function
  const handleVoiceCommand = useCallback((type, text) => {
    setTranscript(text);
    
    let apiMode = 'navigation';
    let customText = '';

    if (type === 'read') {
      apiMode = 'read';
      setActiveMode('read');
    } else if (type === 'location') {
      apiMode = 'location';
      setActiveMode('location');
    } else if (type === 'navigate_on') {
      apiMode = 'navigation';
      setActiveMode('navigation');
    } else if (type === 'navigate_off') {
      cancel();
      return;
    } else {
      // General search/custom prompt
      apiMode = 'custom';
      customText = text;
      setActiveMode('custom');
      setCustomPromptText(text);
    }

    triggerCapture(apiMode, customText);
  }, [triggerCapture, cancel]);

  // Speech input hook
  const { startListening, stopListening, isListening, error: speechError } = useSpeechInput(handleVoiceCommand);

  // Overlay tap handler (unlocks Web Audio & TTS in browsers)
  const handleInitialTap = () => {
    initAudio();
    setShowOverlay(false);
    speak("Smart Glasses activated. Ready to assist. Tap the large button to capture and analyze, or tap the microphone to use voice commands.");
  };

  // Replay last response spoken
  const handleReplaySpeech = () => {
    if (lastResponse) {
      speak(lastResponse);
    }
  };


  // Handle Speech API errors
  useEffect(() => {
    if (speechError) {
      speak(speechError);
      setError(speechError);
    }
  }, [speechError, speak]);

  const toggleListen = () => {
    isListening ? stopListening() : startListening();
  };

  // Wake word SSE listener
  useEffect(() => {
    const eventSource = new EventSource(`${API_BASE_URL}/events`);
    eventSource.onmessage = (e) => {
      if (e.data === "trigger") {
        console.log("Wake word detected! Switching to custom Ask AI mode.");
        setActiveMode('custom');
        // Small delay to ensure state updates before starting recognition
        setTimeout(() => {
          startListening();
        }, 100);
      }
    };
    return () => eventSource.close();
  }, [startListening]);

  return (
    <div className="flex flex-col h-full w-full bg-slate-950 text-slate-100 font-sans overflow-hidden">
      {/* 1. INITIAL GESTURE OVERLAY */}
      {showOverlay && (
        <div 
          onClick={handleInitialTap}
          className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-slate-950 cursor-pointer p-6 transition-all duration-300"
        >
          <div className="relative mb-8 flex items-center justify-center">
            <div className="absolute w-24 h-24 rounded-full bg-emerald-500/20 animate-ping" />
            <div className="w-16 h-16 rounded-full bg-emerald-600 flex items-center justify-center text-white shadow-lg shadow-emerald-500/30">
              <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
          </div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight mb-3 text-center">Tap to Wake Up</h1>
          <p className="text-slate-400 text-sm text-center max-w-sm">
            Enables microphone access, audio cues, and voice assistant features for smart glasses guidance.
          </p>
        </div>
      )}

      {/* 2. HEADER BAR */}
      <header className="flex items-center justify-between px-6 py-4 bg-slate-900/60 backdrop-blur-md border-b border-slate-800 shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-emerald-500 animate-pulse" />
          <span className="font-bold tracking-tight text-white text-base">SAMAKSH AI</span>
        </div>
        <div className="flex items-center gap-3">
          <button 
            onClick={() => setShowEnrollment(true)}
            className="text-xs font-semibold bg-emerald-600/20 text-emerald-400 px-3 py-1.5 rounded-full border border-emerald-500/30 hover:bg-emerald-600/30 transition-colors"
          >
            People
          </button>
          <span className={`px-2.5 py-1 rounded-full text-xs font-semibold tracking-wider uppercase bg-slate-800 text-slate-300 border border-slate-700/50`}>
            API: Online
          </span>
        </div>
      </header>

      {showEnrollment && <EnrollmentView onClose={() => setShowEnrollment(false)} />}

      {/* 3. MAIN WORKSPACE */}
      <main className="flex-1 flex flex-col md:flex-row overflow-hidden min-h-0">
        {/* LEFT PANEL: Live Controls & Capture Button */}
        <section className="flex-1 flex flex-col items-center justify-center p-6 border-b md:border-b-0 md:border-r border-slate-800 bg-slate-900/20 relative">
          
          {/* Mode Selector Tabs */}
          <div className="w-full max-w-md bg-slate-900/80 border border-slate-800 p-1 rounded-xl flex gap-1 mb-8">
            {['navigation', 'read', 'location', 'custom'].map((mode) => (
              <button
                key={mode}
                onClick={() => { setActiveMode(mode); setError(null); }}
                className={`flex-1 py-2 rounded-lg text-xs font-semibold uppercase tracking-wider transition-all duration-200 ${
                  activeMode === mode 
                    ? 'bg-emerald-600 text-white shadow-md' 
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                {mode === 'custom' ? 'Ask AI' : mode}
              </button>
            ))}
          </div>

          {/* Custom Prompt Input (only visible when 'custom' mode is active) */}
          {activeMode === 'custom' && (
            <div className="w-full max-w-md mb-6 animate-fadeIn">
              <input
                type="text"
                value={customPromptText}
                onChange={(e) => setCustomPromptText(e.target.value)}
                placeholder="What should the glasses look for? (e.g. Find empty chairs)"
                className="w-full px-4 py-3 bg-slate-950 border border-slate-800 focus:border-emerald-600 rounded-xl text-sm outline-none text-white placeholder-slate-500 transition-all"
              />
            </div>
          )}

          {/* Auto Capture Toggle for Navigation Mode */}
          {activeMode === 'navigation' && (
            <div className="w-full max-w-md mb-6 flex justify-center animate-fadeIn">
               <button
                 onClick={() => setIsAutoCaptureActive(!isAutoCaptureActive)}
                 className={`px-4 py-2 rounded-full text-xs font-bold uppercase tracking-wider transition-all border ${
                   isAutoCaptureActive 
                     ? 'bg-rose-900/50 text-rose-400 border-rose-800 hover:bg-rose-900/70 shadow-lg shadow-rose-900/20' 
                     : 'bg-emerald-900/50 text-emerald-400 border-emerald-800 hover:bg-emerald-900/70 shadow-lg shadow-emerald-900/20'
                 }`}
               >
                 {isAutoCaptureActive ? '⏹ Stop Continuous Navigation' : '▶ Start Continuous Navigation'}
               </button>
            </div>
          )}

          {/* BIG INTERACTIVE TRIGGER BUTTON */}
          <div className="relative flex items-center justify-center mb-8">
            {/* Thinking / Ripple rings */}
            {loading && (
              <>
                <div className="absolute w-48 h-48 rounded-full border border-emerald-500/20 animate-ping" />
                <div className="absolute w-40 h-40 rounded-full border border-emerald-500/35 animate-ping-slow" />
              </>
            )}
            
            <button
              onClick={() => triggerCapture(activeMode)}
              disabled={loading}
              className={`w-36 h-36 rounded-full flex flex-col items-center justify-center gap-2 transition-all duration-300 relative z-10 shadow-2xl ${
                loading 
                  ? 'bg-slate-900 text-emerald-400 border-2 border-emerald-500/50 cursor-not-allowed' 
                  : 'bg-emerald-600 text-white hover:bg-emerald-500 border-4 border-emerald-700/30 active:scale-95 cursor-pointer hover:shadow-emerald-500/10'
              }`}
            >
              {loading ? (
                <>
                  <svg className="w-8 h-8 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  <span className="text-[10px] font-bold tracking-widest uppercase">Thinking...</span>
                </>
              ) : (
                <>
                  <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <span className="text-[11px] font-bold tracking-widest uppercase">Capture</span>
                </>
              )}
            </button>
          </div>

          {/* Quick Info text / Status */}
          <div className="text-center">
            {error && (
              <p className="text-rose-400 text-xs bg-rose-950/30 border border-rose-900/50 px-4 py-2 rounded-lg max-w-xs break-words mb-2">
                {error}
              </p>
            )}
            <p className="text-slate-400 text-xs">
              {loading ? 'Analyzing scene with Gemini...' : 'Click Shutter or Use voice trigger'}
            </p>
          </div>

          {/* VOICE INPUT TRIGGERS */}
          <div className="absolute bottom-6 flex items-center gap-3">
            <button
              onClick={toggleListen}
              className={`w-12 h-12 rounded-full flex items-center justify-center transition-all ${
                isListening 
                  ? 'bg-rose-600 text-white animate-pulse' 
                  : 'bg-slate-900 border border-slate-800 text-slate-300 hover:bg-slate-800 hover:text-white'
              }`}
              title={isListening ? "Stop voice listening" : "Start voice listening"}
            >
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 14c1.66 0 2.99-1.34 2.99-3L15 5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.3-3c0 3-2.54 5.1-5.3 5.1S6.7 14 6.7 11H5c0 3.41 2.72 6.23 6 6.72V21h2v-3.28c3.28-.48 6-3.3 6-6.72h-1.7z"/>
              </svg>
            </button>
            {isListening && (
              <span className="text-xs font-semibold text-rose-400 tracking-wider animate-pulse uppercase">
                Listening...
              </span>
            )}
            {transcript && !isListening && (
              <span className="text-xs text-slate-400 italic max-w-xs truncate">
                Command: "{transcript}"
              </span>
            )}
          </div>

        </section>

        {/* RIGHT PANEL: Live Display & Analysis Results */}
        <section className="flex-1 flex flex-col p-6 overflow-y-auto bg-slate-950">
          
          {/* Card containing capture results */}
          <div className="bg-slate-900/40 border border-slate-800/80 rounded-2xl p-5 mb-6 shadow-xl relative overflow-hidden flex-1 flex flex-col min-h-[300px]">
            <h2 className="text-slate-400 text-xs font-bold uppercase tracking-widest mb-4 flex items-center gap-2">
              <svg className="w-4 h-4 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 .364l-.707 .707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
              AI Insights
            </h2>

            {/* Content body */}
            {lastResponse && !lastImageUrl ? (
              /* Text-only response (no image was needed) */
              <div className="flex-1 flex flex-col gap-4 min-h-0">
                <div className="flex items-center gap-2 mb-1">
                  <div className="w-6 h-6 rounded-full bg-emerald-600/20 flex items-center justify-center">
                    <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                    </svg>
                  </div>
                  <span className="text-[10px] text-emerald-400 uppercase tracking-widest font-mono">Text response — no image needed</span>
                </div>
                <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800/50 flex-1 overflow-y-auto">
                  <p className="text-white text-lg font-medium leading-relaxed break-words">
                    {lastResponse}
                  </p>
                </div>

                {/* Speech / Audio Controls */}
                <div className="flex items-center justify-between bg-slate-950/30 px-3 py-2 rounded-lg border border-slate-900 shrink-0">
                  <div className="flex items-center gap-2">
                    <button 
                      onClick={handleReplaySpeech}
                      className="p-2 rounded-lg bg-emerald-950 text-emerald-400 hover:bg-emerald-900 transition"
                      title="Replay TTS spoken guidance"
                    >
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                      </svg>
                    </button>
                    <span className="text-xs text-slate-400">Speak response</span>
                  </div>

                  {isSpeaking && (
                    <div className="flex items-end gap-0.5 h-4 px-2">
                      <div className="w-[3px] bg-emerald-500 waveform-bar rounded-t-sm" />
                      <div className="w-[3px] bg-emerald-500 waveform-bar rounded-t-sm" />
                      <div className="w-[3px] bg-emerald-500 waveform-bar rounded-t-sm" />
                    </div>
                  )}
                </div>
              </div>
            ) : lastImageUrl ? (
              <div className="flex-1 flex flex-col lg:flex-row gap-5 items-stretch min-h-0">
                {/* Captured Image Display */}
                <div className="flex-1 rounded-xl overflow-hidden border border-slate-800 shadow-inner bg-slate-950 relative min-h-[160px] max-h-[300px] lg:max-h-none flex items-center justify-center">
                  <img 
                    src={getFullImageUrl(lastImageUrl)} 
                    alt="Latest captured glasses scene" 
                    className="w-full h-full object-contain"
                  />
                  <span className="absolute top-2 left-2 bg-slate-900/80 backdrop-blur-md px-2 py-0.5 rounded text-[10px] text-emerald-400 uppercase tracking-widest font-mono">
                    Captured scene
                  </span>
                </div>

                {/* Analysis readout */}
                <div className="flex-1 flex flex-col justify-between">
                  <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800/50 flex-1 overflow-y-auto mb-4">
                    <p className="text-white text-lg font-medium leading-relaxed break-words">
                      {lastResponse}
                    </p>
                  </div>
                  
                  {/* Speech / Audio Controls */}
                  <div className="flex items-center justify-between bg-slate-950/30 px-3 py-2 rounded-lg border border-slate-900 shrink-0">
                    <div className="flex items-center gap-2">
                      <button 
                        onClick={handleReplaySpeech}
                        className="p-2 rounded-lg bg-emerald-950 text-emerald-400 hover:bg-emerald-900 transition"
                        title="Replay TTS spoken guidance"
                      >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                        </svg>
                      </button>
                      <span className="text-xs text-slate-400">Speak response</span>
                    </div>

                    {isSpeaking && (
                      <div className="flex items-end gap-0.5 h-4 px-2">
                        <div className="w-[3px] bg-emerald-500 waveform-bar rounded-t-sm" />
                        <div className="w-[3px] bg-emerald-500 waveform-bar rounded-t-sm" />
                        <div className="w-[3px] bg-emerald-500 waveform-bar rounded-t-sm" />
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-slate-600 py-12 border-2 border-dashed border-slate-900 rounded-xl">
                <svg className="w-12 h-12 mb-3 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 10.742l-1.922 4.092A1 1 0 007.663 16h8.674a1 1 0 00.901-1.166l-1.922-4.092a1 1 0 00-1.802 0l-1.922 4.092a1 1 0 01-1.802 0l-1.922-4.092z" />
                </svg>
                <p className="text-slate-500 text-sm">No image captured yet</p>
                <p className="text-slate-600 text-xs mt-1">Ready for next request</p>
              </div>
            )}
          </div>

          {/* BOTTOM SUBPANEL: Captures History Feed - Removed as per instructions */}

        </section>
      </main>
    </div>
  );
}

export default App;
