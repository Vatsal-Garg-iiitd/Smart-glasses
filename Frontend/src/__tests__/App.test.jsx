import { render, screen, fireEvent } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import App from '../App';

vi.mock('../hooks/useFirebase', () => ({
  useFirebase: () => ({
    status: 'idle',
    isConnected: true,
    sendCommand: vi.fn().mockResolvedValue(true),
    markMessageSpoken: vi.fn()
  })
}));

vi.mock('../hooks/useTTS', () => ({
  useTTS: () => ({
    speak: vi.fn(),
    cancel: vi.fn(),
    isSpeaking: false
  })
}));

vi.mock('../hooks/useAudioCues', () => ({
  useAudioCues: () => ({
    initAudio: vi.fn(),
    playShutter: vi.fn(),
    playThinking: vi.fn(),
    playSuccess: vi.fn()
  })
}));

function renderApp() {
  const { container } = render(<App />);
  return container;
}

test('renders audio init overlay on first load', () => {
  renderApp();
  
  const overlays = screen.getAllByText('Tap anywhere to start');
  expect(overlays.length).toBeGreaterThan(0);
  expect(screen.getAllByText('This enables your microphone and speaker').length).toBeGreaterThan(0);
});

test('dismisses overlay on tap and shows main UI', () => {
  renderApp();
  
  const overlays = screen.getAllByText('Tap anywhere to start');
  fireEvent.click(overlays[0]);
  
  // After clicking, check for main UI elements
  expect(screen.getAllByText('Ready').length).toBeGreaterThan(0);
  expect(screen.getAllByText('Read Sign').length).toBeGreaterThan(0);
  expect(screen.getAllByText('Describe').length).toBeGreaterThan(0);
  expect(screen.getAllByText('Navigate').length).toBeGreaterThan(0);
  expect(screen.getAllByText('Tap to speak').length).toBeGreaterThan(0);
});

test('shows em dash when no response yet', () => {
  renderApp();
  
  const overlays = screen.getAllByText('Tap anywhere to start');
  fireEvent.click(overlays[0]);
  
  expect(screen.getAllByText('—').length).toBeGreaterThan(0);
});
