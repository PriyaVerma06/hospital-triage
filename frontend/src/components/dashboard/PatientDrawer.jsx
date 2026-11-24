/**
 * PatientDrawer — slide-over panel showing full patient details.
 * Used by both PriorityQueue and ActivePatients rows.
 *
 * Props:
 *   patient  — the patient object (queue or assigned)
 *   doctors  — full doctors list (to look up assigned_doctor_id)
 *   onClose  — called when the drawer should close
 *   onDischarge — called after successful discharge (refresh trigger)
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { X, ExternalLink, LogOut, AlertCircle } from 'lucide-react';
import { LevelBadge } from '../../lib/urgency.jsx';
import { getPatientAudit, dischargePatient } from '../../lib/api.js';
import { formatWaitTime } from '../../lib/dashboardLogic.js';

/** Labelled vital row */
function VitalRow({ label, value, unit }) {
  return (
    <div className="flex justify-between py-1 border-b border-gray-100 last:border-0">
      <span className="text-gray-500 text-sm">{label}</span>
      <span className="font-medium text-sm">
        {value ?? '—'}{value != null && unit ? ` ${unit}` : ''}
      </span>
    </div>
  );
}

export default function PatientDrawer({ patient, doctors, onClose, onDischarge }) {
  const [audit, setAudit] = useState([]);
  const [auditLoading, setAuditLoading] = useState(true);
  const [discharging, setDischarging] = useState(false);
  const [confirmDischarge, setConfirmDischarge] = useState(false);
  const [dischargeError, setDischargeError] = useState(null);

  // Look up doctor name
  const doctor = doctors?.find((d) => d.id === patient?.assigned_doctor_id);

  useEffect(() => {
    if (!patient) return;
    setAuditLoading(true);
    getPatientAudit(patient.id)
      .then(setAudit)
      .catch(() => setAudit([]))
      .finally(() => setAuditLoading(false));
  }, [patient?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Close on Escape
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  if (!patient) return null;

  async function handleDischarge() {
    setDischarging(true);
    setDischargeError(null);
    try {
      await dischargePatient(patient.id);
      setConfirmDischarge(false);
      onDischarge?.();
      onClose();
    } catch (err) {
      setDischargeError(err.message ?? 'Discharge failed');
    } finally {
      setDischarging(false);
    }
  }

  const tagList = patient.reason_tags ?? [];
  const waitDisplay = patient.wait_minutes != null
    ? formatWaitTime(patient.wait_minutes) : null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 z-40"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer panel */}
      <div className="fixed right-0 top-0 h-full w-full max-w-md bg-white z-50 shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-start justify-between p-4 border-b">
          <div>
            <h2 className="font-bold text-lg text-gray-900">{patient.name}</h2>
            <p className="text-sm text-gray-500">
              {patient.age}y · {patient.gender === 'M' ? 'Male' : 'Female'}
              {patient.assigned_bed_id && ` · Bed ${patient.assigned_bed_id}`}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <LevelBadge level={patient.urgency_level} size="sm" />
            <button
              onClick={onClose}
              className="p-1 rounded hover:bg-gray-100"
              aria-label="Close"
            >
              <X className="w-5 h-5 text-gray-500" />
            </button>
          </div>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-5">
          {/* Status + timing */}
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="bg-gray-100 px-2 py-1 rounded-full font-medium">
              {patient.status}
            </span>
            {waitDisplay && (
              <span className="bg-blue-50 text-blue-700 px-2 py-1 rounded-full font-medium">
                Wait: {waitDisplay}
              </span>
            )}
            {doctor && (
              <span className="bg-purple-50 text-purple-700 px-2 py-1 rounded-full font-medium">
                Dr. {doctor.name}
              </span>
            )}
          </div>

          {/* Symptoms */}
          {patient.symptoms && (
            <div>
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                Symptoms
              </h3>
              <p className="text-sm text-gray-700">{patient.symptoms}</p>
            </div>
          )}

          {/* Reason tags */}
          {tagList.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                Triage Flags
              </h3>
              <div className="flex flex-wrap gap-1">
                {tagList.map((tag) => (
                  <span
                    key={tag}
                    className="text-xs bg-red-50 text-red-700 border border-red-200 px-2 py-0.5 rounded-full"
                  >
                    {tag.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Vitals */}
          <div>
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Vitals
            </h3>
            <div className="bg-gray-50 rounded-lg px-3 py-2">
              <VitalRow label="Blood Pressure" value={patient.sbp != null ? `${patient.sbp}/${patient.dbp}` : null} unit="mmHg" />
              <VitalRow label="Heart Rate" value={patient.hr} unit="bpm" />
              <VitalRow label="SpO₂" value={patient.spo2} unit="%" />
              <VitalRow label="Temperature" value={patient.temp} unit="°C" />
              <VitalRow label="Resp. Rate" value={patient.rr} unit="br/min" />
            </div>
          </div>

          {/* Audit history */}
          <div>
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Audit History
            </h3>
            {auditLoading ? (
              <p className="text-xs text-gray-400">Loading…</p>
            ) : audit.length === 0 ? (
              <p className="text-xs text-gray-400">No audit events.</p>
            ) : (
              <ul className="space-y-1">
                {audit.map((entry) => (
                  <li key={entry.id} className="text-xs flex gap-2">
                    <span className="text-gray-400 shrink-0">
                      {new Date(entry.timestamp).toLocaleTimeString()}
                    </span>
                    <span className="text-gray-700">{entry.event}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Discharge error */}
          {dischargeError && (
            <div className="flex items-center gap-2 text-red-600 text-sm bg-red-50 p-2 rounded">
              <AlertCircle className="w-4 h-4 shrink-0" />
              {dischargeError}
            </div>
          )}
        </div>

        {/* Footer actions */}
        <div className="p-4 border-t flex gap-2">
          <Link
            to={`/patients/${patient.id}`}
            className="flex-1 flex items-center justify-center gap-1 text-sm font-medium bg-blue-600 text-white px-3 py-2 rounded-lg hover:bg-blue-700 transition-colors"
            onClick={onClose}
          >
            <ExternalLink className="w-4 h-4" />
            Open full record
          </Link>

          {/* Discharge flow */}
          {!confirmDischarge ? (
            <button
              onClick={() => setConfirmDischarge(true)}
              className="flex items-center gap-1 text-sm font-medium text-red-600 border border-red-300 px-3 py-2 rounded-lg hover:bg-red-50 transition-colors"
            >
              <LogOut className="w-4 h-4" />
              Discharge
            </button>
          ) : (
            <div className="flex gap-2">
              <button
                onClick={handleDischarge}
                disabled={discharging}
                className="text-sm font-medium bg-red-600 text-white px-3 py-2 rounded-lg hover:bg-red-700 disabled:opacity-60 transition-colors"
              >
                {discharging ? 'Discharging…' : 'Confirm'}
              </button>
              <button
                onClick={() => setConfirmDischarge(false)}
                className="text-sm text-gray-600 px-3 py-2 rounded-lg hover:bg-gray-100"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
