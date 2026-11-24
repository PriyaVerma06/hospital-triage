/**
 * ActivePatients — table of ASSIGNED patients.
 *
 * Features:
 * - Shows name, level badge, bed, doctor, reason tags, time since assigned
 * - For DOCTOR users: "My patients" toggle (default on) shows their own first
 * - Clicking a row opens PatientDrawer
 */
import { useState, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext.jsx';
import { LevelBadge } from '../../lib/urgency.jsx';
import PatientDrawer from './PatientDrawer.jsx';

/** Format relative time from ISO string */
function timeSince(isoString) {
  if (!isoString) return '—';
  const diff = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return '< 1 min ago';
  if (mins < 60) return `${mins} min ago`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m === 0 ? `${h}h ago` : `${h}h ${m}m ago`;
}

export default function ActivePatients({ assigned, doctors, recentlyEscalated, onRefresh }) {
  const { user, hasRole } = useAuth();
  const [myOnly, setMyOnly] = useState(true);
  const [selected, setSelected] = useState(null);

  const isDoctor = hasRole('DOCTOR');

  // Separate "my" patients from "others" for DOCTOR view
  let list = assigned;
  if (isDoctor && myOnly && user?.doctor_id) {
    const mine   = assigned.filter((p) => p.assigned_doctor_id === user.doctor_id);
    const others = assigned.filter((p) => p.assigned_doctor_id !== user.doctor_id);
    list = [...mine, ...others];
  }

  const handleClose = useCallback(() => setSelected(null), []);

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-100">
        <h2 className="font-bold text-gray-800">Active Patients</h2>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-400">{assigned.length} assigned</span>
          {isDoctor && (
            <label className="flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={myOnly}
                onChange={(e) => setMyOnly(e.target.checked)}
                className="w-3.5 h-3.5 rounded"
              />
              My patients first
            </label>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        {list.length === 0 ? (
          <div className="text-center py-10 text-gray-400 text-sm">No assigned patients.</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 border-b border-gray-100">
                <th className="px-4 py-2 font-medium">Patient</th>
                <th className="px-4 py-2 font-medium">Level</th>
                <th className="px-4 py-2 font-medium">Bed</th>
                <th className="px-4 py-2 font-medium">Doctor</th>
                <th className="px-4 py-2 font-medium hidden md:table-cell">Tags</th>
                <th className="px-4 py-2 font-medium hidden lg:table-cell">Assigned</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {list.map((patient) => {
                const doctor = doctors?.find((d) => d.id === patient.assigned_doctor_id);
                const isMine = isDoctor && patient.assigned_doctor_id === user?.doctor_id;
                const tags   = (patient.reason_tags ?? []).slice(0, 3);
                const escalated = recentlyEscalated.has(patient.id);

                return (
                  <tr
                    key={patient.id}
                    onClick={() => setSelected(patient)}
                    className={`cursor-pointer transition-colors hover:bg-blue-50 ${
                      isMine ? 'bg-purple-50' : ''
                    } ${escalated ? 'ring-1 ring-orange-400 ring-inset' : ''}`}
                  >
                    <td className="px-4 py-2.5 font-medium text-gray-900">
                      {patient.name}
                      {isMine && (
                        <span className="ml-1.5 text-xs text-purple-600 font-normal">(mine)</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <LevelBadge level={patient.urgency_level} size="sm" />
                    </td>
                    <td className="px-4 py-2.5 text-gray-600">
                      {patient.assigned_bed_id ?? '—'}
                    </td>
                    <td className="px-4 py-2.5 text-gray-600">
                      {doctor ? `Dr. ${doctor.name}` : '—'}
                    </td>
                    <td className="px-4 py-2.5 hidden md:table-cell">
                      <div className="flex flex-wrap gap-1">
                        {tags.map((tag) => (
                          <span key={tag} className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">
                            {tag.replace(/_/g, ' ')}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-2.5 text-gray-400 text-xs hidden lg:table-cell whitespace-nowrap">
                      {timeSince(patient.assigned_at)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Drawer */}
      {selected && (
        <PatientDrawer
          patient={selected}
          doctors={doctors}
          onClose={handleClose}
          onDischarge={onRefresh}
        />
      )}
    </div>
  );
}
