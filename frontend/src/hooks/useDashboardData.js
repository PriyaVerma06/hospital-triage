/**
 * useDashboardData — loads and keeps live all dashboard data.
 *
 * - Parallel initial fetch: queue, assigned patients, beds, doctors, resources
 * - Subscribes to live socket events via LiveContext; debounces re-fetches 300 ms
 * - Falls back to polling every 15 s while socket is not "live"
 * - Tracks "recentlyEscalated" patient ids for 8 s when urgency worsens
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { useLive } from '../context/LiveContext.jsx';
import { request } from '../lib/api.js';
import { detectEscalations, buildLevelMap } from '../lib/dashboardLogic.js';

const DEBOUNCE_MS = 300;
const POLL_INTERVAL_MS = 15000;
const ESCALATION_TTL_MS = 8000;

/** Fetch all five data slices in parallel. */
async function fetchAll() {
  const [queue, assigned, beds, doctors, resources] = await Promise.all([
    request('/queue'),
    request('/patients?status=ASSIGNED'),
    request('/beds'),
    request('/doctors'),
    request('/resources/summary'),
  ]);
  return { queue, assigned, beds, doctors, resources };
}

export function useDashboardData() {
  const { status, subscribe } = useLive();

  const [data, setData] = useState({
    queue: [],
    assigned: [],
    beds: [],
    doctors: [],
    resources: null,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [recentlyEscalated, setRecentlyEscalated] = useState(new Set());

  // Track previous urgency levels to detect escalations
  const prevLevelsRef = useRef({});
  // Timeout ids for expiring escalation highlights
  const escalationTimersRef = useRef({});
  // Debounce timer
  const debounceTimerRef = useRef(null);
  // Poll timer
  const pollTimerRef = useRef(null);

  const refresh = useCallback(async () => {
    try {
      const fresh = await fetchAll();
      setError(null);

      // Detect escalations in queue + assigned
      const allPatients = [...(fresh.queue ?? []), ...(fresh.assigned ?? [])];
      const escalatedIds = detectEscalations(prevLevelsRef.current, allPatients);
      prevLevelsRef.current = buildLevelMap(allPatients);

      if (escalatedIds.length > 0) {
        setRecentlyEscalated((prev) => {
          const next = new Set(prev);
          for (const id of escalatedIds) next.add(id);
          return next;
        });

        // Schedule expiry for each newly escalated patient
        for (const id of escalatedIds) {
          clearTimeout(escalationTimersRef.current[id]);
          escalationTimersRef.current[id] = setTimeout(() => {
            setRecentlyEscalated((prev) => {
              const next = new Set(prev);
              next.delete(id);
              return next;
            });
          }, ESCALATION_TTL_MS);
        }
      }

      setData(fresh);
    } catch (err) {
      setError(err.message ?? 'Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  }, []);

  /** Debounced refresh — collapses event bursts into one fetch. */
  const debouncedRefresh = useCallback(() => {
    clearTimeout(debounceTimerRef.current);
    debounceTimerRef.current = setTimeout(refresh, DEBOUNCE_MS);
  }, [refresh]);

  // Initial load
  useEffect(() => {
    refresh();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Subscribe to live events
  useEffect(() => {
    const unsubscribe = subscribe((event) => {
      const { type } = event;
      // These events mean data has changed — re-fetch
      if (
        type === 'patient_created' ||
        type === 'patient_updated' ||
        type === 'queue_changed' ||
        type === 'bed_changed' ||
        type === 'resources_changed' ||
        type === 'patient_discharged'
      ) {
        debouncedRefresh();
      }
    });
    return unsubscribe;
  }, [subscribe, debouncedRefresh]);

  // After a socket reconnect, do a full refresh immediately
  useEffect(() => {
    if (status === 'live') {
      refresh();
    }
  }, [status]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fallback polling when socket is not live
  useEffect(() => {
    if (status === 'live') {
      clearInterval(pollTimerRef.current);
      return;
    }
    pollTimerRef.current = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(pollTimerRef.current);
  }, [status, refresh]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      clearTimeout(debounceTimerRef.current);
      clearInterval(pollTimerRef.current);
      for (const t of Object.values(escalationTimersRef.current)) clearTimeout(t);
    };
  }, []);

  return { ...data, loading, error, refresh, recentlyEscalated };
}
