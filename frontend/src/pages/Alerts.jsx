/**
 * Alerts page — list of clinical alerts with acknowledge + live updates.
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import { Bell, CheckCircle, ExternalLink } from 'lucide-react';
import { useAuth } from '../context/AuthContext.jsx';
import { useLive } from '../context/LiveContext.jsx';
import { getAlerts, acknowledgeAlert, getDoctors } from '../lib/api.js';
import { LevelBadge } from '../lib/urgency.jsx';
import ErrorBanner from '../components/ui/ErrorBanner.jsx';
import EmptyState from '../components/ui/EmptyState.jsx';
import { SkeletonTable } from '../components/ui/Skeleton.jsx';

export default function Alerts() {
  const { user, hasRole } = useAuth();
  const { subscribe } = useLive();

  const [unackOnly, setUnackOnly] = useState(true);
  const [doctorFilter, setDoctorFilter] = useState('');
  const [alerts, setAlerts] = useState([]);
  const [doctors, setDoctors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [ackingId, setAckingId] = useState(null);

  const isDoctor = hasRole('DOCTOR');

  const fetchAlerts = useCallback(async () => {
    setError(null);
    try {
      const params = {};
      if (unackOnly) params.unacknowledged_only = true;
      if (doctorFilter) params.doctor_id = doctorFilter;
      const data = await getAlerts(params);
      setAlerts(data ?? []);
    } catch (err) {
      setError(err.message ?? 'Failed to load alerts');
    } finally {
      setLoading(false);
    }
  }, [unackOnly, doctorFilter]);

  // Initial load + re-fetch when filter changes
  useEffect(() => { setLoading(true); fetchAlerts(); }, [fetchAlerts]);

  // Load doctors for the filter dropdown (non-doctor roles)
  useEffect(() => {
    if (!isDoctor) getDoctors().then(setDoctors).catch(() => {});
  }, [isDoctor]);

  // Live new alerts → prepend
  useEffect(() => {
    const unsub = subscribe((ev) => {
      if (ev.type === 'alert') {
        // Refetch instead of prepend to stay consistent with filters
        fetchAlerts();
      }
    });
    return unsub;
  }, [subscribe, fetchAlerts]);

  async function handleAcknowledge(alert) {
    setAckingId(alert.id);
    try {
      await acknowledgeAlert(alert.id);
      setAlerts((prev) => prev.map((a) => a.id === alert.id ? { ...a, acknowledged: true } : a));
    } catch (err) {
      setError(err.message ?? 'Failed to acknowledge');
    } finally {
      setAckingId(null);
    }
  }

  const isCritical = (a) => a.level <= 2;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold text-gray-800 flex items-center gap-2">
          <Bell className="w-5 h-5 text-blue-600" /> Alerts
        </h1>
        <div className="flex flex-wrap items-center gap-3">
          {/* Doctor filter (non-doctors only) */}
          {!isDoctor && doctors.length > 0 && (
            <select
              value={doctorFilter}
              onChange={(e) => setDoctorFilter(e.target.value)}
              className="text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All doctors</option>
              {doctors.map((d) => (
                <option key={d.id} value={d.id}>Dr. {d.name}</option>
              ))}
            </select>
          )}
          {/* Unacknowledged toggle */}
          <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer select-none">
            <input
              type="checkbox" checked={unackOnly}
              onChange={(e) => setUnackOnly(e.target.checked)}
              className="w-4 h-4 rounded"
            />
            Unacknowledged only
          </label>
          <button onClick={fetchAlerts} className="text-xs text-blue-600 hover:underline">Refresh</button>
        </div>
      </div>

      {error && <ErrorBanner message={error} onRetry={fetchAlerts} />}

      {loading ? (
        <SkeletonTable rows={6} />
      ) : alerts.length === 0 ? (
        <EmptyState icon="🔔" title="No alerts" message={unackOnly ? 'All caught up!' : 'No alerts recorded.'} />
      ) : (
        <div className="space-y-3">
          {alerts.map((alert) => {
            const critical = isCritical(alert);
            const doctor = doctors.find((d) => d.id === alert.doctor_id);
            return (
              <div
                key={alert.id}
                className={`rounded-xl border p-4 flex flex-col sm:flex-row sm:items-center gap-3 ${
                  alert.acknowledged
                    ? 'bg-gray-50 border-gray-200 opacity-60'
                    : critical
                      ? 'bg-red-50 border-red-300'
                      : 'bg-amber-50 border-amber-300'
                }`}
              >
                {/* Left: level + message */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <LevelBadge level={alert.level} size="sm" />
                    {alert.acknowledged && (
                      <span className="text-xs text-gray-400 font-medium">Acknowledged</span>
                    )}
                    {doctor && (
                      <span className="text-xs text-gray-500">Dr. {doctor.name}</span>
                    )}
                  </div>
                  <p className={`text-sm font-medium ${critical && !alert.acknowledged ? 'text-red-800' : 'text-gray-800'}`}>
                    {alert.message}
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {new Date(alert.created_at).toLocaleString()}
                  </p>
                </div>

                {/* Right: actions */}
                <div className="flex gap-2 items-center shrink-0">
                  {alert.patient_id && (
                    <Link
                      to={`/patients/${alert.patient_id}`}
                      className="flex items-center gap-1 text-xs font-medium text-blue-600 hover:underline"
                    >
                      <ExternalLink className="w-3.5 h-3.5" /> Patient
                    </Link>
                  )}
                  {!alert.acknowledged && (
                    <button
                      onClick={() => handleAcknowledge(alert)}
                      disabled={ackingId === alert.id}
                      className="flex items-center gap-1 text-xs font-semibold text-green-700 bg-green-100 px-3 py-1.5 rounded-lg hover:bg-green-200 disabled:opacity-60 transition-colors"
                    >
                      <CheckCircle className="w-3.5 h-3.5" />
                      {ackingId === alert.id ? '…' : 'Acknowledge'}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
