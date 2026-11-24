/**
 * Admin/ShiftsTab — day-view shift scheduler with 24-hour timeline.
 * Shows each doctor's shifts as horizontal bars; add/delete with 409 inline error.
 */
import { useState, useEffect, useCallback } from 'react';
import { Plus, Trash2, Zap } from 'lucide-react';
import { getDoctors, getShifts, adminCreateShift, adminDeleteShift, applyShifts } from '../../lib/api.js';
import { shiftPosition, formatShiftTime } from '../../lib/shiftLogic.js';
import ConfirmDialog from '../ui/ConfirmDialog.jsx';
import ErrorBanner from '../ui/ErrorBanner.jsx';
import EmptyState from '../ui/EmptyState.jsx';

/** Format a Date to "YYYY-MM-DD" for input[type=date] and API calls */
function toDateStr(d) {
  return d.toISOString().slice(0, 10);
}

/** 24-hour tick labels */
const HOUR_TICKS = [0, 6, 12, 18, 24];

export default function ShiftsTab() {
  const today = toDateStr(new Date());
  const [date, setDate]       = useState(today);
  const [doctors, setDoctors] = useState([]);
  const [shifts, setShifts]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);
  const [banner, setBanner]   = useState(null);

  // Add-shift form
  const [showAdd, setShowAdd]       = useState(false);
  const [form, setForm]             = useState({ doctor_id: '', start_time: '', end_time: '' });
  const [formError, setFormError]   = useState(null);
  const [saving, setSaving]         = useState(false);

  // Delete confirm
  const [delShift, setDelShift]     = useState(null);

  // Apply shifts result
  const [applyResult, setApplyResult] = useState(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [docs, sh] = await Promise.all([
        getDoctors(),
        getShifts({ date }),
      ]);
      setDoctors(docs);
      setShifts(sh);
    } catch (e) {
      setError(e.message ?? 'Failed to load shifts');
    } finally { setLoading(false); }
  }, [date]);

  useEffect(() => { load(); }, [load]);

  async function handleAddShift() {
    setFormError(null); setSaving(true);
    try {
      await adminCreateShift({
        doctor_id: Number(form.doctor_id),
        start_time: form.start_time,
        end_time: form.end_time,
      });
      setBanner({ type: 'ok', msg: 'Shift created.' });
      setShowAdd(false);
      load();
    } catch (e) {
      setFormError(e.message ?? 'Failed to create shift');
    } finally { setSaving(false); }
  }

  async function handleDelete() {
    setSaving(true);
    try {
      await adminDeleteShift(delShift.id);
      setBanner({ type: 'ok', msg: `Shift ${delShift.id} deleted.` });
      setDelShift(null); load();
    } catch (e) {
      setBanner({ type: 'err', msg: e.message ?? 'Delete failed' });
      setDelShift(null);
    } finally { setSaving(false); }
  }

  async function handleApply() {
    setBanner(null); setApplyResult(null);
    try {
      const changes = await applyShifts();
      setApplyResult(changes);
      setBanner({ type: 'ok', msg: `Applied: ${changes.length} doctor(s) updated.` });
      load();
    } catch (e) {
      setBanner({ type: 'err', msg: e.message ?? 'Apply failed' });
    }
  }

  // Group shifts by doctor
  const shiftsByDoctor = {};
  for (const s of shifts) {
    if (!shiftsByDoctor[s.doctor_id]) shiftsByDoctor[s.doctor_id] = [];
    shiftsByDoctor[s.doctor_id].push(s);
  }

  return (
    <div className="space-y-5">
      {/* Toolbar */}
      <div className="flex flex-wrap gap-3 items-center justify-between">
        <div className="flex gap-2 items-center">
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)}
            className="text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <div className="flex gap-2">
          <button onClick={handleApply}
            className="flex items-center gap-1.5 text-sm font-semibold bg-amber-500 text-white px-4 py-2 rounded-lg hover:bg-amber-600 transition-colors">
            <Zap className="w-4 h-4" /> Apply shifts now
          </button>
          <button onClick={() => { setForm({ doctor_id: doctors[0]?.id ?? '', start_time: '', end_time: '' }); setFormError(null); setShowAdd(true); }}
            className="flex items-center gap-1.5 text-sm font-semibold bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors">
            <Plus className="w-4 h-4" /> Add shift
          </button>
        </div>
      </div>

      {banner && (
        <div className={`text-sm px-4 py-2 rounded-lg border ${banner.type === 'ok' ? 'bg-green-50 text-green-700 border-green-200' : 'bg-red-50 text-red-700 border-red-200'}`}>
          {banner.msg}
        </div>
      )}
      {applyResult && applyResult.length > 0 && (
        <div className="text-xs bg-blue-50 border border-blue-200 rounded-lg p-3 space-y-1">
          {applyResult.map((r) => (
            <div key={r.doctor_id}>Dr. {r.name} → {r.changed_to ? 'On duty' : 'Off duty'}</div>
          ))}
        </div>
      )}
      {error && <ErrorBanner message={error} onRetry={load} />}

      {/* 24-hour timeline */}
      {loading ? (
        <div className="h-40 bg-gray-100 animate-pulse rounded-xl" />
      ) : doctors.length === 0 ? (
        <EmptyState icon="🗓️" title="No doctors" />
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4 overflow-x-auto">
          {/* Hour ticks header */}
          <div className="relative mb-2 ml-28 mr-16">
            <div className="flex justify-between text-xs text-gray-400">
              {HOUR_TICKS.map((h) => (
                <span key={h}>{String(h).padStart(2, '0')}:00</span>
              ))}
            </div>
          </div>

          {/* Doctor rows */}
          <div className="space-y-2">
            {doctors.map((doc) => {
              const docShifts = shiftsByDoctor[doc.id] ?? [];
              return (
                <div key={doc.id} className="flex items-center gap-2">
                  {/* Doctor name label */}
                  <div className="w-28 shrink-0 text-xs font-medium text-gray-700 truncate">
                    Dr. {doc.name}
                  </div>

                  {/* Timeline bar */}
                  <div className="flex-1 relative h-8 bg-gray-100 rounded-lg overflow-hidden">
                    {docShifts.map((sh) => {
                      const pos = shiftPosition(sh, date);
                      if (!pos) return null;
                      return (
                        <div
                          key={sh.id}
                          title={`${formatShiftTime(sh.start_time)} – ${formatShiftTime(sh.end_time)}`}
                          className="absolute top-0.5 bottom-0.5 bg-blue-400 rounded flex items-center px-1 group"
                          style={{ left: `${pos.leftPct}%`, width: `${pos.widthPct}%` }}
                        >
                          <span className="text-white text-xs truncate leading-none">
                            {formatShiftTime(sh.start_time)}
                          </span>
                          {/* Delete button on hover */}
                          <button
                            onClick={() => setDelShift(sh)}
                            className="hidden group-hover:flex ml-auto p-0.5 rounded bg-blue-600 hover:bg-red-600 transition-colors"
                            title="Delete shift"
                          >
                            <Trash2 className="w-3 h-3 text-white" />
                          </button>
                        </div>
                      );
                    })}
                    {docShifts.length === 0 && (
                      <span className="absolute inset-0 flex items-center px-2 text-xs text-gray-400">No shifts this day</span>
                    )}
                  </div>

                  {/* Availability indicator */}
                  <div className="w-14 shrink-0">
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${doc.is_available ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {doc.is_available ? 'On' : 'Off'}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Add shift form (inline panel) */}
      {showAdd && (
        <div className="bg-gray-50 border border-gray-200 rounded-xl p-5">
          <h3 className="font-semibold text-gray-800 mb-4">Add Shift</h3>
          {formError && (
            <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2 mb-3">
              {formError}
            </div>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Doctor</label>
              <select value={form.doctor_id} onChange={(e) => setForm((f) => ({ ...f, doctor_id: e.target.value }))}
                className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500">
                {doctors.map((d) => <option key={d.id} value={d.id}>Dr. {d.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Start</label>
              <input type="datetime-local" value={form.start_time}
                onChange={(e) => setForm((f) => ({ ...f, start_time: e.target.value }))}
                className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">End</label>
              <input type="datetime-local" value={form.end_time}
                onChange={(e) => setForm((f) => ({ ...f, end_time: e.target.value }))}
                className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
          </div>
          <div className="flex justify-end gap-2 mt-4">
            <button onClick={() => setShowAdd(false)} className="px-4 py-2 text-sm text-gray-600 rounded-lg hover:bg-gray-200">Cancel</button>
            <button onClick={handleAddShift}
              disabled={!form.doctor_id || !form.start_time || !form.end_time || saving}
              className="px-4 py-2 text-sm font-semibold bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-60">
              {saving ? 'Saving…' : 'Create shift'}
            </button>
          </div>
        </div>
      )}

      {/* Delete confirm */}
      <ConfirmDialog open={!!delShift} danger title="Delete shift?"
        message={delShift ? `${formatShiftTime(delShift.start_time)} – ${formatShiftTime(delShift.end_time)}` : ''}
        confirmLabel="Delete" loading={saving}
        onConfirm={handleDelete} onCancel={() => setDelShift(null)} />
    </div>
  );
}
