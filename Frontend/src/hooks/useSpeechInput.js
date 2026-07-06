import { useState, useCallback, useRef } from 'react';

export function useSpeechInput(onCommand) {
  const [isListening, setIsListening] = useState(false);
  const [error, setError] = useState(null);
  const recognitionRef = useRef(null);

  const parseAndSendCommand = useCallback((text) => {
    let type = "general";
    
    // Keyword matching based on explanation.md rules
    if (text.includes("read sign") || text.includes("what does that say") || text.includes("read")) {
      type = "read";
    } else if (text.includes("describe") || text.includes("what is in front of me") || text.includes("where am i") || text.includes("location")) {
      type = "location";
    } else if (text.includes("navigate") || text.includes("help me walk") || text.includes("start navigation")) {
      type = "navigate_on";
    } else if (text.includes("stop navigation") || text.includes("stop walking")) {
      type = "navigate_off";
    }

    onCommand(type, text);
  }, [onCommand]);

  const startListening = useCallback(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setError("Speech recognition is not supported in this browser.");
      return;
    }

    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // ignore
      }
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
      setIsListening(true);
      setError(null);
    };

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript.toLowerCase();
      parseAndSendCommand(transcript);
    };

    recognition.onerror = (event) => {
      console.error("Speech recognition error", event.error);
      setIsListening(false);
      
      if (event.error === 'not-allowed') {
        setError("Microphone access denied.");
      } else if (event.error === 'no-speech') {
        setError("I didn't hear anything.");
      } else if (event.error === 'aborted') {
        // Ignore aborted errors, often happens when stopping manually
      } else {
        setError(`Microphone error: ${event.error}`);
      }
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognitionRef.current = recognition;
    
    try {
      recognition.start();
    } catch (e) {
      console.error("Could not start recognition", e);
    }
  }, [parseAndSendCommand]);

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
  }, []);

  return { startListening, stopListening, isListening, error };
}
