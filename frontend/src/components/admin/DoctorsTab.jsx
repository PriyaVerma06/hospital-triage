/**
 * Admin/DoctorsTab — CRUD for doctors + availability toggle.
 */
import { useState, useEffect, useCallback } from 'react';
import { Plus, Pencil, Trash2 } from 'lucide-react';
import { getDoctors, adminCreateDoctor, adminUpdateDoctor, adminDeleteDoctor } from '../../lib/api.js';
import Modal from '../ui/Modal.jsx';
import ConfirmDialog from '../ui/ConfirmDialog.jsx';
import ErrorBanner from '../ui/ErrorBanner.jsx';
import EmptyState from '../ui/EmptyState.jsx';
import { SkeletonTable } from '../ui/Skeleton.jsx';

const SPECIALTIES = ['Emergency', 'Cardiology', 'General'];

export default function DoctorsTab() {
  const [doctors, setDoctors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [banner, setBanner] = useState(null);
  const [showAdd, setShowAdd] = useState(false);
  const [editDoc, setEditDoc] = useState(null);
  const [deleteDoc, setDeleteDoc] = useState(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: '', specialty: 'Emergency', is_available: true });

  const load = useCallback(async () => {
    setError(null);
    try { setDoctors(await getDoctors()); }
    catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  function openAdd() { setForm({ name: '', specialty: 'Emergency', is_available: true }); setShowAdd(true); }
  function openEdit(doc) { setForm({ name: doc.name, specialty: doc.specialty, is_available: doc.is_available }); setEditDoc(doc); }

  async function handleSave() {
    setSaving(true); setBanner(null);
    try {
      let res;
      if (editDoc) {
        res = await adminUpdateDoctor(editDoc.id, form);
        if (res?.warning) setBanner({ type: 'warn', msg: res.warning });
        else setBanner({ type: 'ok', msg: `Dr. ${res.name} updated.` });
        setEditDoc(null);
      } else {
        res = await adminCreateDoctor(form);
        setBanner({ type: 'ok', msg: `Dr. ${res.name} created.` });
        setShowAdd(false);
      }
      load();
    } catch (e) {
      setBanner({ type: 'err', msg: e.message ?? 'Failed to save' });
    } finally { setSaving(false); }
  }

  async function handleDelete() {
    setSaving(true); setBanner(null);
    try {
      await adminDeleteDoctor(deleteDoc.id);
      setBanner({ type: 'ok', msg: `Dr. ${deleteDoc.name} deleted.` });
      setDeleteDoc(null); load();
    } catch (e) {
      setBanner({ type: 'err', msg: e.message ?? 'Delete failed' });
      setDeleteDoc(null);
    } finally { setSaving(false); }
  }

  async function toggleAvailability(doc) {
    try {
      const res = await adminUpdateDoctor(doc.id, { is_available: !doc.is_available });
      if (res?.warning) setBanner({ type: 'warn', msg: res.warning });
      load();
    } catch (e) {
      setBanner({ type: 'err', msg: e.message });
    }
  }

  const FormBody = () => (
    <>
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-1">Full name</label>
        <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500" />
      </div>
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-1">Specialty</label>
        <select value={form.specialty} onChange={(e) => setForm((f) => ({ ...f, specialty: e.target.value }))}
          className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none">
          {SPECIALTIES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>
      <label className="flex items-center gap-2 text-sm cursor-pointer mb-4">
        <input type="checkbox" checked={form.is_available} onChange={(e) => setForm((f) => ({ ...f, is_available: e.target.checked }))} className="w-4 h-4 rounded" />
        Initially available
      </label>
    </>
  );

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button onClick={openAdd} className="flex items-center gap-1.5 text-sm font-semibold bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors">
          <Plus className="w-4 h-4" /> Add doctor
        </button>
      </div>

      {banner && (
        <div className={`text-sm px-4 py-2 rounded-lg border ${
          banner.type === 'ok'   ? 'bg-green-50 text-green-700 border-green-200' :
          banner.type === 'warn' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                                   'bg-red-50 text-red-700 border-red-200'}`}>
          {banner.msg}
        </div>
      )}
      {error && <ErrorBanner message={error} onRetry={load} />}

      {loading ? <SkeletonTable rows={5} /> : doctors.length === 0 ? (
        <EmptyState icon="👨‍⚕️" title="No doctors" />
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-gray-100">
              <tr className="text-xs text-gray-500 text-left">
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Specialty</th>
                <th className="px-4 py-3 font-medium">Active patients</th>
                <th className="px-4 py-3 font-medium">Available</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {doctors.map((doc) => (
                <tr key={doc.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">Dr. {doc.name}</td>
                  <td className="px-4 py-3 text-gray-600">{doc.specialty}</td>
                  <td className="px-4 py-3 text-gray-600">{doc.active_patients_count}</td>
                  <td className="px-4 py-3">
                    <button onClick={() => toggleAvailability(doc)}
                      className={`text-xs font-semibold px-2.5 py-1 rounded-full transition-colors ${
                        doc.is_available ? 'bg-green-100 text-green-700 hover:bg-green-200' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                      }`}>
                      {doc.is_available ? 'On duty' : 'Off duty'}
                    </button>
                  </td>
                  <td className="px-4 py-3 flex gap-2">
                    <button onClick={() => openEdit(doc)} className="p-1 rounded hover:bg-gray-100">
                      <Pencil className="w-4 h-4 text-gray-500" />
                    </button>
                    <button onClick={() => setDeleteDoc(doc)}
                      disabled={doc.active_patients_count > 0}
                      title={doc.active_patients_count > 0 ? 'Cannot delete: has active patients' : 'Delete'}
                      className="p-1 rounded hover:bg-red-50 disabled:opacity-30 disabled:cursor-not-allowed">
                      <Trash2 className="w-4 h-4 text-red-500" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={showAdd} onClose={() => setShowAdd(false)} title="Add Doctor">
        <FormBody />
        <div className="flex justify-end gap-2">
          <button onClick={() => setShowAdd(false)} className="px-4 py-2 text-sm text-gray-600 rounded-lg hover:bg-gray-100">Cancel</button>
          <button onClick={handleSave} disabled={!form.name || saving}
            className="px-4 py-2 text-sm font-semibold bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-60">
            {saving ? 'Saving…' : 'Create'}
          </button>
        </div>
      </Modal>

      <Modal open={!!editDoc} onClose={() => setEditDoc(null)} title={`Edit Dr. ${editDoc?.name}`}>
        <FormBody />
        <div className="flex justify-end gap-2">
          <button onClick={() => setEditDoc(null)} className="px-4 py-2 text-sm text-gray-600 rounded-lg hover:bg-gray-100">Cancel</button>
          <button onClick={handleSave} disabled={saving}
            className="px-4 py-2 text-sm font-semibold bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-60">
            {saving ? 'Saving…' : 'Update'}
          </button>
        </div>
      </Modal>

      <ConfirmDialog open={!!deleteDoc} danger title={`Delete Dr. ${deleteDoc?.name}?`}
        message="This cannot be undone." confirmLabel="Delete" loading={saving}
        onConfirm={handleDelete} onCancel={() => setDeleteDoc(null)} />
    </div>
  );
}
