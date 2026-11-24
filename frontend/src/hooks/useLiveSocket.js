/**
 * useLiveSocket — manages a single authenticated WebSocket connection.
 *
 * Features:
 * - Exponential back-off reconnect (1s → 2s → 4s … max 15s)
 * - Ping every 25 s; ignores "pong"
 * - Close code 4401 → forces logout (bad/expired JWT)
 * - Safe in React StrictMode (uses a guard ref to prevent double-mount)
 * - After reconnect, calls onReconnect so callers can refresh stale data
 */
import { useEffect, useRef, useState, useCallback } from 'react';
import { wsUrl } from '../config.js';

const MIN_BACKOFF = 1000;   // 1 second
const MAX_BACKOFF = 15000;  // 15 seconds
const PING_INTERVAL = 25000; // 25 seconds

export function useLiveSocket({ token, onEvent, onForceLogout, onReconnect }) {
  const [status, setStatus] = useState('connecting');

  // Use refs so changes don't trigger re-connection
  const onEventRef = useRef(onEvent);
  const onForceLogoutRef = useRef(onForceLogout);
  const onReconnectRef = useRef(onReconnect);
  useEffect(() => { onEventRef.current = onEvent; }, [onEvent]);
  useEffect(() => { onForceLogoutRef.current = onForceLogout; }, [onForceLogout]);
  useEffect(() => { onReconnectRef.current = onReconnect; }, [onReconnect]);

  const wsRef = useRef(null);
  const backoffRef = useRef(MIN_BACKOFF);
  const retryTimerRef = useRef(null);
  const pingTimerRef = useRef(null);
  const mountedRef = useRef(false); // StrictMode guard
  const attemptRef = useRef(0);     // increments each connect attempt

  const cleanup = useCallback(() => {
    clearInterval(pingTimerRef.current);
    clearTimeout(retryTimerRef.current);
    if (wsRef.current) {
      // Remove listeners before closing to prevent reconnect loops
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      wsRef.current.onmessage = null;
      wsRef.current.onopen = null;
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const connect = useCallback((isReconnect = false) => {
    if (!token || !mountedRef.current) return;

    const thisAttempt = ++attemptRef.current;
    cleanup();

    setStatus(isReconnect ? 'reconnecting' : 'connecting');

    let ws;
    try {
      ws = new WebSocket(wsUrl(token));
    } catch (err) {
      console.warn('[WS] Failed to construct WebSocket:', err);
      setStatus('offline');
      return;
    }
    wsRef.current = ws;

    ws.onopen = () => {
      if (thisAttempt !== attemptRef.current) return; // stale attempt
      setStatus('live');
      backoffRef.current = MIN_BACKOFF; // reset back-off on success

      if (isReconnect && onReconnectRef.current) {
        onReconnectRef.current();
      }

      // Start ping loop
      pingTimerRef.current = setInterval(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send('ping');
        }
      }, PING_INTERVAL);
    };

    ws.onmessage = (evt) => {
      if (thisAttempt !== attemptRef.current) return;
      if (evt.data === 'pong') return; // ignore pong
      try {
        const event = JSON.parse(evt.data);
        onEventRef.current?.(event);
      } catch {
        // non-JSON frame — ignore
      }
    };

    ws.onerror = () => {
      // onerror is always followed by onclose; handle retry there
    };

    ws.onclose = (evt) => {
      if (thisAttempt !== attemptRef.current) return;
      clearInterval(pingTimerRef.current);

      // 4401 = invalid/expired token — force logout
      if (evt.code === 4401) {
        setStatus('offline');
        onForceLogoutRef.current?.();
        return;
      }

      if (!mountedRef.current) return;

      setStatus('reconnecting');
      const delay = backoffRef.current;
      backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF);
      retryTimerRef.current = setTimeout(() => connect(true), delay);
    };
  }, [token, cleanup]); // eslint-disable-line react-hooks/exhaustive-deps

  // Open connection when token is available; close when unmounted or token gone
  useEffect(() => {
    if (!token) {
      setStatus('offline');
      return;
    }
    mountedRef.current = true;
    connect(false);

    return () => {
      mountedRef.current = false;
      cleanup();
    };
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  /** Manually trigger a reconnect (e.g. after long tab sleep) */
  const reconnect = useCallback(() => {
    backoffRef.current = MIN_BACKOFF;
    connect(true);
  }, [connect]);

  return { status, reconnect };
}
