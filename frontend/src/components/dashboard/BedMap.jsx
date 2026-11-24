/**
 * BedMap — visual grid of all beds grouped by ward.
 *
 * Tile colours:
 *   AVAILABLE → green
 *   OCCUPIED  → red (shows patient name + level badge)
 *   CLEANING  → amber
 *
 * Features:
 * - Per-ward header with occupied count and thin progress bar
 * - Ventilator icon on beds that have one
 * - Clicking an occupied tile opens PatientDrawer
 * - Legend at the bottom
 */
import { useState, useCallback } from 'react';
import { Wind } from 'lucide-react';
import { LevelBadge } from '../../lib/urgency.jsx';
import { groupBedsByWard } from '../../lib/dashboardLogic.js';
import PatientDrawer from './PatientDrawer.jsx';

/** Ward display order */
const WARD_ORDER = ['ICU', 'EMERGENCY', 'GENERAL'];

const WARD_LABELS = {
  ICU: 'ICU',
  EMERGENCY: 'Emergency',
  GENERAL: 'General',
};

function bedStyle(status) {
  return {
    AVAILABLE: 'bg-green-100 border-green-300 text-green-800 hover:bg-green-200',
    OCCUPIED:  'bg-red-100  border-red-300  text-red-800  hover:bg-red-200  cursor-pointer',
    CLEANING:  'bg-amber-100 border-amber-300 text-amber-800',
  }[status] ?? 'bg-gray-100 border-gray-300 text-gray-700';
}

export default function BedMap({ beds, assigned, doctors, onRefresh }) {
  const [selected, setSelected] = useState(null); // the patient whose drawer is open

  const groups = groupBedsByWard(beds);
  const handleClose = useCallback(() => setSelected(null), []);

  // Build a lookup from bed_id → assigned patient
  const bedToPatient = {};
  for (const p of assigned) {
    if (p.assigned_bed_id) bedToPatient[p.assigned_bed_id] = p;
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
      <h2 className="font-bold text-gray-800 mb-4">Bed Map</h2>

      <div className="space-y-5">
        {WARD_ORDER.filter((w) => groups[w]).map((ward) => {
          const wardBeds   = groups[ward];
          const occupied   = wardBeds.filter((b) => b.status === 'OCCUPIED').length;
          const pct        = wardBeds.length > 0 ? (occupied / wardBeds.length) * 100 : 0;

          return (
            <div key={ward}>
              {/* Ward header */}
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-bold text-gray-600 uppercase tracking-wider">
                  {WARD_LABELS[ward]}
                </span>
                <span className="text-xs text-gray-400">
                  {occupied}/{wardBeds.length} occupied
                </span>
              </div>

              {/* Progress bar */}
              <div className="h-1 w-full bg-gray-100 rounded-full mb-2 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    pct > 75 ? 'bg-red-500' : pct > 40 ? 'bg-amber-400' : 'bg-green-500'
                  }`}
                  style={{ width: `${pct}%` }}
                />
              </div>

              {/* Bed tiles */}
              <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                {wardBeds.map((bed) => {
                  const patient = bedToPatient[bed.id];
                  return (
                    <button
                      key={bed.id}
                      disabled={bed.status !== 'OCCUPIED'}
                      onClick={() => patient && setSelected(patient)}
                      className={`rounded-lg border p-2 text-left transition-colors ${bedStyle(bed.status)} ${
                        bed.status !== 'OCCUPIED' ? 'cursor-default' : ''
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-bold">{bed.id}</span>
                        {bed.has_ventilator && (
                          <Wind className="w-3 h-3 opacity-70" title="Ventilator" />
                        )}
                      </div>

                      {bed.status === 'OCCUPIED' && patient ? (
                        <div>
                          <p className="text-xs font-medium truncate">{patient.name}</p>
                          <LevelBadge level={patient.urgency_level} size="sm" />
                        </div>
                      ) : (
                        <p className="text-xs opacity-60">
                          {bed.status === 'CLEANING' ? 'Cleaning' : 'Free'}
                        </p>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 mt-4 pt-3 border-t border-gray-100">
        {[
          { color: 'bg-green-200', label: 'Available' },
          { color: 'bg-red-200',   label: 'Occupied'  },
          { color: 'bg-amber-200', label: 'Cleaning'  },
        ].map(({ color, label }) => (
          <span key={label} className="flex items-center gap-1.5 text-xs text-gray-500">
            <span className={`w-3 h-3 rounded-sm ${color}`} />
            {label}
          </span>
        ))}
        <span className="flex items-center gap-1.5 text-xs text-gray-500">
          <Wind className="w-3 h-3" /> Ventilator
        </span>
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
