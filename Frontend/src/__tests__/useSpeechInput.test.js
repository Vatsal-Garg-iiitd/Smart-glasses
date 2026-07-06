import { renderHook, act } from '@testing-library/react';
import { expect, test, vi, beforeEach } from 'vitest';
import { useSpeechInput } from '../hooks/useSpeechInput';

const mockStart = vi.fn();
const mockStop = vi.fn();
let currentInstance = null;

class MockSpeechRecognition {
  constructor() {
    this.start = mockStart;
    this.stop = mockStop;
    currentInstance = this;
  }
}

window.SpeechRecognition = MockSpeechRecognition;

beforeEach(() => {
  vi.clearAllMocks();
  currentInstance = null;
});

test('parses commands correctly', () => {
  const onCommand = vi.fn();
  const { result } = renderHook(() => useSpeechInput(onCommand));
  
  act(() => {
    result.current.startListening();
  });
  
  // Simulate result
  act(() => {
    currentInstance.onresult({
      results: [[{ transcript: 'read this sign' }]]
    });
  });
  
  expect(onCommand).toHaveBeenCalledWith('read', 'read this sign');
  
  act(() => {
    currentInstance.onresult({
      results: [[{ transcript: 'where am i' }]]
    });
  });
  
  expect(onCommand).toHaveBeenCalledWith('location', 'where am i');
  
  act(() => {
    currentInstance.onresult({
      results: [[{ transcript: 'start navigation' }]]
    });
  });
  
  expect(onCommand).toHaveBeenCalledWith('navigate_on', 'start navigation');
});
