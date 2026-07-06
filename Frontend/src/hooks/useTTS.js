import { useState, useCallback, useRef } from 'react';

export function useTTS() {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const intervalRef = useRef(null);

  const cancel = useCallback(() => {
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }
  }, []);

  const speak = useCallback((text, onEnd) => {
    if (!window.speechSynthesis) {
      if (onEnd) onEnd();
      return;
    }

    cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.1;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;
    
    // Prefer English voices
    const voices = window.speechSynthesis.getVoices();
    const enVoice = voices.find(v => v.lang.startsWith('en'));
    if (enVoice) utterance.voice = enVoice;

    utterance.onstart = () => {
      setIsSpeaking(true);
      // Chrome mobile bug workaround: ping speech synthesis to keep it alive
      intervalRef.current = setInterval(() => {
        if (!window.speechSynthesis.speaking) {
          clearInterval(intervalRef.current);
        } else {
          window.speechSynthesis.resume();
        }
      }, 10000);
    };

    utterance.onend = () => {
      setIsSpeaking(false);
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      if (onEnd) onEnd();
    };

    utterance.onerror = (e) => {
      console.error("TTS Error", e);
      setIsSpeaking(false);
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      if (onEnd) onEnd();
    };

    window.speechSynthesis.speak(utterance);
  }, [cancel]);

  return { speak, cancel, isSpeaking };
}
