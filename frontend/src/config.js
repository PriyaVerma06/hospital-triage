/**
 * Global configuration.
 * API_BASE is set via VITE_API_BASE env variable (default: "/api").
 * The Vite dev proxy maps /api → http://127.0.0.1:8000.
 */
export const API_BASE = import.meta.env.VITE_API_BASE ?? '/api';

/**
 * Build the WebSocket URL for the authenticated live-update connection.
 * Uses wss:// on HTTPS pages, ws:// on HTTP (dev).
 * The Vite proxy maps /ws → ws://127.0.0.1:8000.
 * @param {string} token - JWT access token
 * @returns {string} Full WebSocket URL
 */
export function wsUrl(token) {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  return `${proto}//${host}/ws?token=${encodeURIComponent(token)}`;
}
