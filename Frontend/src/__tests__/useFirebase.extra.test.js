import { renderHook, act } from '@testing-library/react';
import { expect, test, vi, beforeEach } from 'vitest';
import { useFirebase } from '../hooks/useFirebase';
import * as firebaseDatabase from 'firebase/database';

vi.mock('firebase/database', () => {
  return {
    ref: vi.fn((db, path) => ({ db, path })),
    onValue: vi.fn(),
    set: vi.fn(),
    update: vi.fn(),
  };
});

vi.mock('../firebase', () => ({
  db: { mockDb: true }
}));

beforeEach(() => {
  vi.clearAllMocks();
  firebaseDatabase.onValue.mockImplementation(() => vi.fn());
  firebaseDatabase.set.mockResolvedValue(true);
  firebaseDatabase.update.mockResolvedValue(true);
});

test('handles connection status listener changes correctly', () => {
  const { result } = renderHook(() => useFirebase());
  
  // onValue is called 3 times: connection, command status, messages
  expect(firebaseDatabase.onValue).toHaveBeenCalledTimes(3);
  
  // The first call to onValue is connection listener
  const connectionCall = firebaseDatabase.onValue.mock.calls[0];
  expect(connectionCall[0].path).toBe('.info/connected');
  
  const connectionCallback = connectionCall[1];
  
  // Simulate connected = true
  act(() => {
    connectionCallback({ val: () => true });
  });
  expect(result.current.isConnected).toBe(true);
  
  // Simulate connected = false
  act(() => {
    connectionCallback({ val: () => false });
  });
  expect(result.current.isConnected).toBe(false);
});

test('handles error and idle command statuses correctly', () => {
  const onProcessing = vi.fn();
  const onError = vi.fn();
  
  const { result } = renderHook(() => useFirebase(onProcessing, onError));
  
  // The second call is status listener
  const statusCallback = firebaseDatabase.onValue.mock.calls[1][1];
  
  // Simulate error status
  act(() => {
    statusCallback({ val: () => 'error' });
  });
  expect(result.current.status).toBe('error');
  expect(onError).toHaveBeenCalledTimes(1);
  expect(onProcessing).not.toHaveBeenCalled();
  
  // Simulate idle status
  act(() => {
    statusCallback({ val: () => 'idle' });
  });
  expect(result.current.status).toBe('idle');
  // Callbacks shouldn't be called again
  expect(onError).toHaveBeenCalledTimes(1);
  expect(onProcessing).not.toHaveBeenCalled();
});

test('sends standard commands using set', async () => {
  const { result } = renderHook(() => useFirebase());
  
  let success;
  await act(async () => {
    success = await result.current.sendCommand('describe', 'describe this scene');
  });
  
  expect(success).toBe(true);
  expect(firebaseDatabase.set).toHaveBeenCalledTimes(1);
  
  const setCall = firebaseDatabase.set.mock.calls[0];
  expect(setCall[0].path).toBe('/session/command');
  expect(setCall[1]).toEqual({
    type: 'describe',
    status: 'pending',
    text: 'describe this scene'
  });
});

test('sends navigate_off command using update', async () => {
  const { result } = renderHook(() => useFirebase());
  
  let success;
  await act(async () => {
    success = await result.current.sendCommand('navigate_off', '');
  });
  
  expect(success).toBe(true);
  expect(firebaseDatabase.update).toHaveBeenCalledTimes(1);
  
  const updateCall = firebaseDatabase.update.mock.calls[0];
  expect(updateCall[0].path).toBe('/session');
  expect(updateCall[1]).toEqual({
    mode: 'normal',
    navigation_active: false
  });
});

test('handles write errors gracefully in sendCommand', async () => {
  // Mock console.error to avoid cluttering test outputs
  const consoleMock = vi.spyOn(console, 'error').mockImplementation(() => {});
  firebaseDatabase.set.mockRejectedValueOnce(new Error('Firebase network failure'));
  
  const { result } = renderHook(() => useFirebase());
  
  let success;
  await act(async () => {
    success = await result.current.sendCommand('speak', 'hello');
  });
  
  expect(success).toBe(false);
  expect(consoleMock).toHaveBeenCalled();
  consoleMock.mockRestore();
});

test('marks message as spoken in Firebase and filters it from further notifications', async () => {
  const onNewMessage = vi.fn();
  const { result } = renderHook(() => useFirebase(null, null, onNewMessage));
  
  const messagesCallback = firebaseDatabase.onValue.mock.calls[2][1];
  
  // Emit 2 new messages
  act(() => {
    messagesCallback({
      val: () => ({
        msgA: { text: 'Alert 1', spoken: false, timestamp: 100 },
        msgB: { text: 'Alert 2', spoken: false, timestamp: 200 },
      })
    });
  });
  
  expect(onNewMessage).toHaveBeenLastCalledWith([
    { id: 'msgA', text: 'Alert 1', spoken: false, timestamp: 100 },
    { id: 'msgB', text: 'Alert 2', spoken: false, timestamp: 200 }
  ]);
  
  // Mark msgA as spoken
  await act(async () => {
    await result.current.markMessageSpoken('msgA');
  });
  
  // Verify firebase update was called
  expect(firebaseDatabase.update).toHaveBeenCalledTimes(1);
  const updateCall = firebaseDatabase.update.mock.calls[0];
  expect(updateCall[0].path).toBe('/messages/msgA');
  expect(updateCall[1]).toEqual({ spoken: true });
  
  // Emit the messages again. msgA should be filtered out because it is marked processed in the hook's ref.
  onNewMessage.mockClear();
  act(() => {
    messagesCallback({
      val: () => ({
        msgA: { text: 'Alert 1', spoken: false, timestamp: 100 },
        msgB: { text: 'Alert 2', spoken: false, timestamp: 200 },
      })
    });
  });
  
  expect(onNewMessage).toHaveBeenLastCalledWith([
    { id: 'msgB', text: 'Alert 2', spoken: false, timestamp: 200 }
  ]);
});

test('filters out messages that have spoken=true or are already processed', () => {
  const onNewMessage = vi.fn();
  renderHook(() => useFirebase(null, null, onNewMessage));
  
  const messagesCallback = firebaseDatabase.onValue.mock.calls[2][1];
  
  act(() => {
    messagesCallback({
      val: () => ({
        msg1: { text: 'Already spoken', spoken: true, timestamp: 10 },
        msg2: { text: 'Unspoken', spoken: false, timestamp: 20 },
      })
    });
  });
  
  expect(onNewMessage).toHaveBeenCalledWith([
    { id: 'msg2', text: 'Unspoken', spoken: false, timestamp: 20 }
  ]);
});

test('sorts incoming messages by timestamp', () => {
  const onNewMessage = vi.fn();
  renderHook(() => useFirebase(null, null, onNewMessage));
  
  const messagesCallback = firebaseDatabase.onValue.mock.calls[2][1];
  
  act(() => {
    messagesCallback({
      val: () => ({
        msgLater: { text: 'Later', spoken: false, timestamp: 500 },
        msgEarlier: { text: 'Earlier', spoken: false, timestamp: 100 },
        msgMiddle: { text: 'Middle', spoken: false, timestamp: 300 },
      })
    });
  });
  
  expect(onNewMessage).toHaveBeenCalledWith([
    { id: 'msgEarlier', text: 'Earlier', spoken: false, timestamp: 100 },
    { id: 'msgMiddle', text: 'Middle', spoken: false, timestamp: 300 },
    { id: 'msgLater', text: 'Later', spoken: false, timestamp: 500 }
  ]);
});
