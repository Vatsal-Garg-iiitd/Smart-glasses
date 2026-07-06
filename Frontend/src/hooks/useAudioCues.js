import { useRef, useCallback } from 'react';

export function useAudioCues() {
  const audioCtxRef = useRef(null);

  const initAudio = useCallback(() => {
    if (!audioCtxRef.current) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) {
        audioCtxRef.current = new AudioContext();
      }
    } else if (audioCtxRef.current.state === 'suspended') {
      audioCtxRef.current.resume();
    }
  }, []);

  const playShutter = useCallback(() => {
    if (!audioCtxRef.current) return;
    const ctx = audioCtxRef.current;
    
    // Quick click-click
    const t = ctx.currentTime;
    [0, 0.07].forEach((delay) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      
      osc.type = 'square';
      osc.frequency.setValueAtTime(800, t + delay);
      osc.frequency.exponentialRampToValueAtTime(400, t + delay + 0.05);
      
      gain.gain.setValueAtTime(0, t + delay);
      gain.gain.linearRampToValueAtTime(0.3, t + delay + 0.005);
      gain.gain.exponentialRampToValueAtTime(0.01, t + delay + 0.05);
      
      osc.connect(gain);
      gain.connect(ctx.destination);
      
      osc.start(t + delay);
      osc.stop(t + delay + 0.06);
    });
  }, []);

  const playThinking = useCallback(() => {
    if (!audioCtxRef.current) return;
    const ctx = audioCtxRef.current;
    
    const t = ctx.currentTime;
    const notes = [261.63, 329.63, 392.00]; // C4, E4, G4
    
    notes.forEach((freq, i) => {
      const delay = i * 0.15;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      
      osc.type = 'sine';
      osc.frequency.value = freq;
      
      gain.gain.setValueAtTime(0, t + delay);
      gain.gain.linearRampToValueAtTime(0.2, t + delay + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.01, t + delay + 0.15);
      
      osc.connect(gain);
      gain.connect(ctx.destination);
      
      osc.start(t + delay);
      osc.stop(t + delay + 0.15);
    });
  }, []);

  const playSuccess = useCallback(() => {
    if (!audioCtxRef.current) return;
    const ctx = audioCtxRef.current;
    
    const t = ctx.currentTime;
    const notes = [392.00, 523.25]; // G4, C5
    
    notes.forEach((freq, i) => {
      const delay = i * 0.2;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      
      osc.type = 'sine';
      osc.frequency.value = freq;
      
      gain.gain.setValueAtTime(0, t + delay);
      gain.gain.linearRampToValueAtTime(0.3, t + delay + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.01, t + delay + 0.2);
      
      osc.connect(gain);
      gain.connect(ctx.destination);
      
      osc.start(t + delay);
      osc.stop(t + delay + 0.2);
    });
  }, []);

  return { initAudio, playShutter, playThinking, playSuccess };
}
