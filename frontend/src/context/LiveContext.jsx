/**
 * LiveContext — single WebSocket connection per browser tab.
 * Wraps useLiveSocket and exposes the status + event subscription API
 * so BOTH the dashboard and the alert toasts share one connection.
 */
import { createContext, useContext, useRef, useCallback } from 'react';
import { useLiveSocket } from '../hooks/useLiveSocket.js';
import { useAuth } from './AuthContext.jsx';

const LiveContext = createContext(null);

export function LiveProvider({ children }) {
  const { token, logout } = useAuth();

  // All subscriber callbacks registered via subscribe()
  const listenersRef = useRef(new Set());

  // Fire all subscribers when any event arrives
  const handleEvent = useCallback((event) => {
    for (const cb of listenersRef.current) {
      try { cb(event); } catch { /* ignore bad subscriber */ }
    }
  }, []);

  const { status, reconnect } = useLiveSocket({
    token,
    onEvent: handleEvent,
    onForceLogout: logout,
  });

  /**
   * Subscribe to live events.
   * @param {(event: object) => void} cb - called with every parsed event
   * @returns {() => void} unsubscribe function
   */
  const subscribe = useCallback((cb) => {
    listenersRef.current.add(cb);
    return () => listenersRef.current.delete(cb);
  }, []);

  return (
    <LiveContext.Provider value={{ status, reconnect, subscribe }}>
      {children}
    </LiveContext.Provider>
  );
}

/** Hook to access live context anywhere in the tree. */
export function useLive() {
  const ctx = useContext(LiveContext);
  if (!ctx) throw new Error('useLive must be used inside LiveProvider');
  return ctx;
}
