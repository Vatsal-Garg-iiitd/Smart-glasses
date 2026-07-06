import { renderHook, act } from '@testing-library/react';
import { expect, test, vi, beforeEach } from 'vitest';
import { useFirebase } from '../hooks/useFirebase';
import * as firebaseDatabase from 'firebase/database';

vi.mock('firebase/database', () => {
  return {
    ref: vi.fn(),
    onValue: vi.fn(),
    set: vi.fn(),
    update: vi.fn(),
  };
});
vi.mock('../firebase', () => ({
  db: {}
}));

beforeEach(() => {
  vi.clearAllMocks();
  firebaseDatabase.onValue.mockImplementation(() => vi.fn());
});

test('listens to status and messages correctly', () => {
  const onProcessing = vi.fn();
  const onError = vi.fn();
  const onNewMessage = vi.fn();
  
  renderHook(() => useFirebase(onProcessing, onError, onNewMessage));
  
  // onValue should have been called 3 times (connected, status, messages)
  expect(firebaseDatabase.onValue).toHaveBeenCalledTimes(3);
  
  const statusCallback = firebaseDatabase.onValue.mock.calls[1][1];
  
  act(() => {
    statusCallback({ val: () => 'processing' });
  });
  
  expect(onProcessing).toHaveBeenCalled();
  
  const messagesCallback = firebaseDatabase.onValue.mock.calls[2][1];
  
  act(() => {
    messagesCallback({
      val: () => ({
        msg1: { text: "hello", spoken: false, timestamp: 1 }
      })
    });
  });
  
  expect(onNewMessage).toHaveBeenCalledWith([{ id: 'msg1', text: "hello", spoken: false, timestamp: 1 }]);
});

test('sends navigation commands using update', async () => {
  const { result } = renderHook(() => useFirebase());
  
  await act(async () => {
    await result.current.sendCommand('navigate_on', '');
  });
  
  expect(firebaseDatabase.update).toHaveBeenCalled();
});
