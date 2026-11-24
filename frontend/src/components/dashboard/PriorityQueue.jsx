/**
 * PriorityQueue — ordered list of WAITING patients.
 *
 * Features:
 * - Color-coded left border per triage level
 * - Wait time (bold red when level 1-2 and > 5 min)
 * - Reason-tag chips
 * - Escalation highlight (pulsing ring + "Escalated" badge)
 * - Filter chips: All / Red / Yellow / Green
 * - Name search box
 * - Clicking a row opens PatientDrawer
 * - Smooth CSS transition on reorder (layout transition via unique key)
 */
import { useState, useCallback } from 'react';
import { Search, ArrowUpCircle } from 'lucide-react';
import { LevelBadge, levelInfo } from '../../lib/urgency.jsx';
import { formatWaitTime, isCriticalWaitTooLong, filterQueue } from '../../lib/dashboardLogic.js';
import PatientDrawer from './PatientDrawer.jsx';

const COLOR_FILTERS = ['ALL', 'RED', 'YELLOW', 'GREEN'];

/** Left border colour by queue colour field */
function borderColor(color) {
  return { RED: 'border-red-500', YELLOW: 'border-yellow-400', GREEN: 'border-green-500' }[color] ?? 'border-gray-300';
}

/** Row background tint by queue colour */
function rowBg(color) {
  return { RED: 'bg-red-50', YELLOW: 'bg-yellow-50', GREEN: 'bg-green-50' }[color] ?? 'bg-white';
}

export default function PriorityQueue({ queue, doctors, recentlyEscalated, onRefresh }) {
  const [colorFilter, setColorFilter] = useState('ALL');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null);

  const filtered = filterQueue(queue, colorFilter, search);

  const handleClose = useCallback(() => setSelected(null), []);

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm flex flex-col h-full">
      {/* Panel header */}
      <div className="p-4 border-b border-gray-100">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-bold text-gray-800">Priority Queue</h2>
          <span className="text-xs text-gray-400 font-medium">{queue.length} waiting</span>
        </div>

        {/* Filter chips */}
        <div className="flex flex-wrap gap-2 mb-3">
          {COLOR_FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setColorFilter(f)}
              className={`text-xs font-semibold px-3 py-1 rounded-full border transition-colors ${
                colorFilter === f
                  ? { ALL: 'bg-gray-800 text-white border-gray-800',
                      RED: 'bg-red-600 text-white border-red-600',
                      YELLOW: 'bg-yellow-400 text-yellow-900 border-yellow-400',
                      GREEN: 'bg-green-600 text-white border-green-600' }[f]
                  : 'bg-white text-gray-600 border-gray-300 hover:border-gray-400'
              }`}
            >
              {f === 'ALL' ? 'All' : f.charAt(0) + f.slice(1).toLowerCase()}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name…"
            className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Queue list */}
      <div className="flex-1 overflow-y-auto divide-y divide-gray-100">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-gray-400">
            <span className="text-3xl mb-2">🏥</span>
            <p className="text-sm font-medium">No patients waiting</p>
          </div>
        ) : (
          filtered.map((patient, idx) => {
            const escalated = recentlyEscalated.has(patient.id);
            const tooLong   = isCriticalWaitTooLong(patient);
            const tags      = patient.reason_tags ?? [];

            return (
              <button
                key={patient.id}
                onClick={() => setSelected(patient)}
                className={`w-full text-left flex items-stretch border-l-4 ${borderColor(patient.color)} ${rowBg(patient.color)}
                  hover:brightness-95 transition-all duration-300 ${escalated ? 'ring-2 ring-orange-400 ring-inset' : ''}`}
                style={{ transition: 'background 0.3s, transform 0.3s' }}
              >
                {/* Rank */}
                <div className="w-8 shrink-0 flex items-center justify-center text-gray-400 text-xs font-bold pl-2">
                  {idx + 1}
                </div>

                {/* Main content */}
                <div className="flex-1 px-3 py-3 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-gray-900 text-sm truncate">{patient.name}</span>
                    <span className="text-xs text-gray-500">
                      {patient.age}y · {patient.gender === 'M' ? 'M' : 'F'}
                    </span>
                    <LevelBadge level={patient.urgency_level} size="sm" />
                    {escalated && (
                      <span className="inline-flex items-center gap-0.5 text-xs font-bold text-orange-600 bg-orange-100 px-2 py-0.5 rounded-full animate-pulse">
                        <ArrowUpCircle className="w-3 h-3" /> Escalated
                      </span>
                    )}
                  </div>

                  {/* Tags */}
                  {tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1.5">
                      {tags.slice(0, 4).map((tag) => (
                        <span key={tag} className="text-xs bg-white/60 border border-gray-200 px-1.5 py-0.5 rounded">
                          {tag.replace(/_/g, ' ')}
                        </span>
                      ))}
                      {tags.length > 4 && (
                        <span className="text-xs text-gray-400">+{tags.length - 4} more</span>
                      )}
                    </div>
                  )}
                </div>

                {/* Wait time */}
                <div className="shrink-0 flex items-center pr-3">
                  <span className={`text-sm font-semibold tabular-nums ${tooLong ? 'text-red-600 font-bold' : 'text-gray-500'}`}>
                    {formatWaitTime(patient.wait_minutes)}
                  </span>
                </div>
              </button>
            );
          })
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
