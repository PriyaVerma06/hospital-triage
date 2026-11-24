/**
 * Admin/BedsTab — CRUD for hospital beds + status control.
 */
import { useState, useEffect, useCallback } from 'react';
import { Plus, Pencil, Trash2, Wind } from 'lucide-react';
import { getBeds, adminCreateBed, adminUpdateBed, adminDeleteBed, updateBedStatus } from '../../lib/api.js';
import Modal from '../ui/Modal.jsx';
import ConfirmDialog from '../ui/ConfirmDialog.jsx';
import ErrorBanner from '../ui/ErrorBanner.jsx';
import EmptyState from '../ui/EmptyState.jsx';
import { SkeletonTable } from '../ui/Skeleton.jsx';

const WARDS = ['ICU', 'EMERGENCY', 'GENERAL'];

function FormField({ label, children }) {
  return (
    <div className="mb-4">
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      {children}
    </div>
  );
}

export default function BedsTab() {
  const [beds, setBeds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [banner, setBanner] = useState(null); // success/error message
  const [wardFilter, setWardFilter] = useState('');

  // Modal states
  const [showAdd, setShowAdd] = useState(false);
  const [editBed, setEditBed] = useState(null);
  const [deleteBed, setDeleteBed] = useState(null);
  const [saving, setSaving] = useState(false);

  // Form state
  const [form, setForm] = useState({ id: '', ward: 'ICU', has_ventilator: true });

  const load = useCallback(async () => {
    setError(null);
    try { setBeds(await getBeds()); }
    catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  function openAdd() { setForm({ id: '', ward: 'ICU', has_ventilator: true }); setShowAdd(true); }
  function openEdit(bed) { setForm({ ward: bed.ward, has_ventilator: bed.has_ventilator }); setEditBed(bed); }

  async function handleSave() {
    setSaving(true); setBanner(null);
    try {
      if (editBed) {
        await adminUpdateBed(editBed.id, { ward: form.ward, has_ventilator: form.has_ventilator });
        setBanner({ type: 'ok', msg: `Bed ${editBed.id} updated.` });
        setEditBed(null);
      } else {
        await adminCreateBed(form);
        setBanner({ type: 'ok', msg: `Bed ${form.id} created.` });
        setShowAdd(false);
      }
      load();
    } catch (e) {
      setBanner({ type: 'err', msg: e.message ?? 'Failed to save bed' });
    } finally { setSaving(false); }
  }

  async function handleDelete() {
    setSaving(true); setBanner(null);
    try {
      await adminDeleteBed(deleteBed.id);
      setBanner({ type: 'ok', msg: `Bed ${deleteBed.id} deleted.` });
      setDeleteBed(null); load();
    } catch (e) {
      setBanner({ type: 'err', msg: e.message ?? 'Delete failed' });
      setDeleteBed(null);
    } finally { setSaving(false); }
  }

  async function handleStatusChange(bed, status) {
    try {
      await updateBedStatus(bed.id, status);
      load();
    } catch (e) {
      setBanner({ type: 'err', msg: e.message });
    }
  }

  const filtered = wardFilter ? beds.filter((b) => b.ward === wardFilter) : beds;

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex flex-wrap gap-3 items-center justify-between">
        <div className="flex gap-2">
          {['', ...WARDS].map((w) => (
            <button key={w} onClick={() => setWardFilter(w)}
              className={`text-xs font-semibold px-3 py-1.5 rounded-lg border transition-colors ${
                wardFilter === w ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 border-gray-300 hover:border-gray-400'
              }`}
            >{w || 'All'}</button>
          ))}
        </div>
        <button onClick={openAdd} className="flex items-center gap-1.5 text-sm font-semibold bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors">
          <Plus className="w-4 h-4" /> Add bed
        </button>
      </div>

      {banner && (
        <div className={`text-sm px-4 py-2 rounded-lg ${banner.type === 'ok' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'}`}>
          {banner.msg}
        </div>
      )}
      {error && <ErrorBanner message={error} onRetry={load} />}

      {loading ? <SkeletonTable rows={6} /> : filtered.length === 0 ? (
        <EmptyState icon="🛏️" title="No beds" />
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-gray-100">
              <tr className="text-xs text-gray-500 text-left">
                <th className="px-4 py-3 font-medium">ID</th>
                <th className="px-4 py-3 font-medium">Ward</th>
                <th className="px-4 py-3 font-medium">Vent</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Quick status</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {filtered.map((bed) => {
                const occupied = bed.status === 'OCCUPIED';
                return (
                  <tr key={bed.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono font-medium text-gray-900">{bed.id}</td>
                    <td className="px-4 py-3 text-gray-600">{bed.ward}</td>
                    <td className="px-4 py-3">{bed.has_ventilator ? <Wind className="w-4 h-4 text-blue-500" /> : '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                        bed.status === 'AVAILABLE' ? 'bg-green-100 text-green-700' :
                        bed.status === 'OCCUPIED'  ? 'bg-red-100 text-red-700' :
                                                     'bg-amber-100 text-amber-700'
                      }`}>{bed.status}</span>
                    </td>
                    <td className="px-4 py-3">
                      {!occupied && (
                        <select
                          value={bed.status}
                          onChange={(e) => handleStatusChange(bed, e.target.value)}
                          className="text-xs border border-gray-200 rounded px-2 py-1 focus:outline-none"
                        >
                          <option value="AVAILABLE">AVAILABLE</option>
                          <option value="CLEANING">CLEANING</option>
                        </select>
                      )}
                    </td>
                    <td className="px-4 py-3 flex gap-2">
                      <button onClick={() => openEdit(bed)} disabled={occupied}
                        title={occupied ? 'Cannot edit OCCUPIED bed' : 'Edit'}
                        className="p-1 rounded hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed">
                        <Pencil className="w-4 h-4 text-gray-500" />
                      </button>
                      <button onClick={() => setDeleteBed(bed)} disabled={occupied}
                        title={occupied ? 'Cannot delete OCCUPIED bed' : 'Delete'}
                        className="p-1 rounded hover:bg-red-50 disabled:opacity-30 disabled:cursor-not-allowed">
                        <Trash2 className="w-4 h-4 text-red-500" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Add modal */}
      <Modal open={showAdd} onClose={() => setShowAdd(false)} title="Add Bed">
        <FormField label="Bed ID">
          <input value={form.id} onChange={(e) => setForm((f) => ({ ...f, id: e.target.value }))}
            placeholder="e.g. ICU-05"
            className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </FormField>
        <FormField label="Ward">
          <select value={form.ward} onChange={(e) => setForm((f) => ({ ...f, ward: e.target.value, has_ventilator: e.target.value === 'ICU' }))}
            className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none">
            {WARDS.map((w) => <option key={w} value={w}>{w}</option>)}
          </select>
        </FormField>
        <FormField label="">
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input type="checkbox" checked={form.has_ventilator} onChange={(e) => setForm((f) => ({ ...f, has_ventilator: e.target.checked }))} className="w-4 h-4 rounded" />
            Has ventilator
          </label>
        </FormField>
        <div className="flex justify-end gap-2 mt-2">
          <button onClick={() => setShowAdd(false)} className="px-4 py-2 text-sm text-gray-600 rounded-lg hover:bg-gray-100">Cancel</button>
          <button onClick={handleSave} disabled={!form.id || saving}
            className="px-4 py-2 text-sm font-semibold bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-60">
            {saving ? 'Saving…' : 'Create'}
          </button>
        </div>
      </Modal>

      {/* Edit modal */}
      <Modal open={!!editBed} onClose={() => setEditBed(null)} title={`Edit Bed ${editBed?.id}`}>
        <FormField label="Ward">
          <select value={form.ward} onChange={(e) => setForm((f) => ({ ...f, ward: e.target.value }))}
            className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none">
            {WARDS.map((w) => <option key={w} value={w}>{w}</option>)}
          </select>
        </FormField>
        <FormField label="">
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input type="checkbox" checked={form.has_ventilator} onChange={(e) => setForm((f) => ({ ...f, has_ventilator: e.target.checked }))} className="w-4 h-4 rounded" />
            Has ventilator
          </label>
        </FormField>
        <div className="flex justify-end gap-2 mt-2">
          <button onClick={() => setEditBed(null)} className="px-4 py-2 text-sm text-gray-600 rounded-lg hover:bg-gray-100">Cancel</button>
          <button onClick={handleSave} disabled={saving}
            className="px-4 py-2 text-sm font-semibold bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-60">
            {saving ? 'Saving…' : 'Update'}
          </button>
        </div>
      </Modal>

      {/* Delete confirm */}
      <ConfirmDialog
        open={!!deleteBed} danger
        title={`Delete bed ${deleteBed?.id}?`}
        message="This cannot be undone."
        confirmLabel="Delete"
        loading={saving}
        onConfirm={handleDelete}
        onCancel={() => setDeleteBed(null)}
      />
    </div>
  );
}
