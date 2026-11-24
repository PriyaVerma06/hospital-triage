/**
 * AlertToasts — global toast stack for live clinical alerts.
 *
 * Mounted ONCE in the layout so alerts appear on every page.
 * Subscribes to LiveContext; also fetches unacknowledged alerts on mount.
 *
 * Features:
 * - Red toast for level 1-2 (critical), amber for others
 * - Critical toasts stay until dismissed; others auto-dismiss after 10 s
 * - Cap at 5 visible toasts
 * - Web Audio API beep for critical alerts (mute toggle saved in localStorage)
 * - Bell icon in navbar shows unacknowledged count (passed up via onCountChange)
 */
import { useEffect, useRef, useCallback, useReducer } from 'react';
import { X, Bell, AlertCircle, CheckCircle, ExternalLink } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useLive } from '../context/LiveContext.jsx';
import { getAlerts, acknowledgeAlert } from '../lib/api.js';

const MAX_TOASTS = 5;
const AUTO_DISMISS_MS = 10000;

// ---------------------------------------------------------------------------
// Web Audio beep (no audio files)
// ---------------------------------------------------------------------------
function playBeep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = 'sine';
    osc.frequency.value = 880;
    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.6);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.6);
  } catch {
    // Audio blocked or unavailable — ignore silently
  }
}

// ---------------------------------------------------------------------------
// Reducer for toast list
// ---------------------------------------------------------------------------
function toastReducer(state, action) {
  switch (action.type) {
    case 'ADD': {
      // Avoid duplicate alert ids
      if (action.toast.alertId && state.some((t) => t.alertId === action.toast.alertId)) {
        return state;
      }
      const next = [action.toast, ...state].slice(0, MAX_TOASTS);
      return next;
    }
    case 'REMOVE':
      return state.filter((t) => t.id !== action.id);
    default:
      return state;
  }
}

let _toastIdCounter = 0;

export default function AlertToasts({ onCountChange }) {
  const { subscribe } = useLive();
  const [toasts, dispatch] = useReducer(toastReducer, []);
  const muteRef = useRef(localStorage.getItem('alert_muted') === 'true');
  // Store auto-dismiss timer ids keyed by toast id
  const timersRef = useRef({});

  const addToast = useCallback((alertEvent) => {
    const isCritical = alertEvent.level != null && alertEvent.level <= 2;
    const id = ++_toastIdCounter;

    dispatch({
      type: 'ADD',
      toast: {
        id,
        alertId: alertEvent.alert_id ?? alertEvent.id ?? null,
        patientId: alertEvent.patient_id ?? null,
        message: alertEvent.message ?? 'New alert',
        level: alertEvent.level ?? 3,
        isCritical,
        time: new Date(),
      },
    });

    // Beep for critical
    if (isCritical && !muteRef.current) {
      playBeep();
    }

    // Auto-dismiss non-critical after 10 s
    if (!isCritical) {
      timersRef.current[id] = setTimeout(() => {
        dispatch({ type: 'REMOVE', id });
      }, AUTO_DISMISS_MS);
    }
  }, []);

  const removeToast = useCallback((id) => {
    clearTimeout(timersRef.current[id]);
    dispatch({ type: 'REMOVE', id });
  }, []);

  const handleAcknowledge = useCallback(async (toast) => {
    if (toast.alertId) {
      try { await acknowledgeAlert(toast.alertId); } catch { /* ignore */ }
    }
    removeToast(toast.id);
    onCountChange?.(-1);
  }, [removeToast, onCountChange]);

  // Subscribe to live alert events
  useEffect(() => {
    const unsub = subscribe((event) => {
      if (event.type === 'alert') {
        addToast(event);
        onCountChange?.(1); // increment bell count
      }
    });
    return unsub;
  }, [subscribe, addToast, onCountChange]);

  // On mount: fetch unacknowledged count for the bell
  useEffect(() => {
    getAlerts({ unacknowledged_only: true })
      .then((alerts) => onCountChange?.(alerts?.length ?? 0, true))
      .catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Cleanup timers on unmount
  useEffect(() => {
    return () => { Object.values(timersRef.current).forEach(clearTimeout); };
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-16 right-4 z-50 flex flex-col gap-2 w-80 max-w-[calc(100vw-2rem)]">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          role="alert"
          className={`rounded-xl shadow-lg border p-3 flex flex-col gap-2 animate-slide-in ${
            toast.isCritical
              ? 'bg-red-50 border-red-300'
              : 'bg-amber-50 border-amber-300'
          }`}
        >
          {/* Top row */}
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <AlertCircle className={`w-4 h-4 shrink-0 ${toast.isCritical ? 'text-red-600' : 'text-amber-600'}`} />
              <p className={`text-sm font-semibold truncate ${toast.isCritical ? 'text-red-800' : 'text-amber-800'}`}>
                {toast.message}
              </p>
            </div>
            <button onClick={() => removeToast(toast.id)} className="shrink-0 p-0.5 rounded hover:bg-black/10">
              <X className="w-3.5 h-3.5 text-gray-500" />
            </button>
          </div>

          {/* Time */}
          <p className="text-xs text-gray-400">{toast.time.toLocaleTimeString()}</p>

          {/* Actions */}
          <div className="flex gap-2">
            {toast.patientId && (
              <Link
                to={`/patients/${toast.patientId}`}
                className="flex items-center gap-1 text-xs font-medium text-blue-600 hover:underline"
              >
                <ExternalLink className="w-3 h-3" />
                View patient
              </Link>
            )}
            <button
              onClick={() => handleAcknowledge(toast)}
              className={`flex items-center gap-1 text-xs font-medium ${
                toast.isCritical ? 'text-red-700 hover:underline' : 'text-amber-700 hover:underline'
              }`}
            >
              <CheckCircle className="w-3 h-3" />
              Acknowledge
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// AlertBell — compact bell icon for the navbar, opened as a dropdown
// ---------------------------------------------------------------------------
export function AlertBell({ count, onMuteToggle, muted }) {
  return (
    <div className="relative flex items-center">
      <button
        onClick={onMuteToggle}
        title={muted ? 'Unmute alerts' : 'Mute alerts'}
        className="relative p-1.5 rounded hover:bg-blue-700 text-blue-100 hover:text-white transition-colors"
      >
        <Bell className="w-4 h-4" />
        {count > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[16px] h-4 flex items-center justify-center rounded-full bg-red-500 text-white text-[10px] font-bold px-0.5">
            {count > 99 ? '99+' : count}
          </span>
        )}
      </button>
    </div>
  );
}
