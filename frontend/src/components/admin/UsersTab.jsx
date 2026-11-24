/**
 * Admin/UsersTab — user management: list, create, activate/deactivate.
 * Admin cannot deactivate themselves.
 */
import { useState, useEffect, useCallback } from 'react';
import { Plus, ToggleLeft, ToggleRight } from 'lucide-react';
import { useAuth } from '../../context/AuthContext.jsx';
import { getUsers, createUser, setUserActive, getDoctors } from '../../lib/api.js';
import Modal from '../ui/Modal.jsx';
import ErrorBanner from '../ui/ErrorBanner.jsx';
import EmptyState from '../ui/EmptyState.jsx';
import { SkeletonTable } from '../ui/Skeleton.jsx';

const ROLES = ['NURSE', 'DOCTOR', 'ADMIN'];

export default function UsersTab() {
  const { user: me } = useAuth();
  const [users, setUsers]     = useState([]);
  const [doctors, setDoctors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);
  const [banner, setBanner]   = useState(null);
  const [showAdd, setShowAdd] = useState(false);
  const [saving, setSaving]   = useState(false);
  const [form, setForm]       = useState({ username: '', password: '', full_name: '', role: 'NURSE', doctor_id: '' });
  const [formErrors, setFormErrors] = useState({});

  const load = useCallback(async () => {
    setError(null);
    try {
      const [u, d] = await Promise.all([getUsers(), getDoctors()]);
      setUsers(u ?? []);
      setDoctors(d ?? []);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  function validate() {
    const errs = {};
    if (!form.username || form.username.length < 3) errs.username = 'Min 3 chars';
    if (!form.password || form.password.length < 6) errs.password = 'Min 6 chars';
    if (!form.full_name) errs.full_name = 'Required';
    if (form.role === 'DOCTOR' && !form.doctor_id) errs.doctor_id = 'Required for DOCTOR role';
    return errs;
  }

  async function handleCreate() {
    const errs = validate();
    if (Object.keys(errs).length) { setFormErrors(errs); return; }
    setSaving(true); setBanner(null);
    try {
      const payload = { ...form };
      if (payload.role !== 'DOCTOR') delete payload.doctor_id;
      else payload.doctor_id = Number(payload.doctor_id);
      await createUser(payload);
      setBanner({ type: 'ok', msg: `User "${form.username}" created.` });
      setShowAdd(false);
      setForm({ username: '', password: '', full_name: '', role: 'NURSE', doctor_id: '' });
      load();
    } catch (e) {
      setBanner({ type: 'err', msg: e.message ?? 'Failed to create user' });
    } finally { setSaving(false); }
  }

  async function toggleActive(u) {
    if (u.id === me?.id) return; // prevent self-deactivation
    try {
      await setUserActive(u.id, !u.is_active);
      setBanner({ type: 'ok', msg: `User "${u.username}" ${!u.is_active ? 'activated' : 'deactivated'}.` });
      load();
    } catch (e) { setBanner({ type: 'err', msg: e.message }); }
  }

  const rolePill = (role) => ({
    NURSE:  'bg-teal-100 text-teal-800',
    DOCTOR: 'bg-purple-100 text-purple-800',
    ADMIN:  'bg-red-100 text-red-800',
  }[role] ?? 'bg-gray-100 text-gray-700');

  const Field = ({ label, name, type = 'text', children }) => (
    <div className="mb-4">
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      {children ?? (
        <input type={type} value={form[name]}
          onChange={(e) => { setForm((f) => ({ ...f, [name]: e.target.value })); setFormErrors((f) => ({ ...f, [name]: '' })); }}
          className={`w-full text-sm border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 ${formErrors[name] ? 'border-red-400' : 'border-gray-200'}`} />
      )}
      {formErrors[name] && <p className="text-xs text-red-500 mt-0.5">{formErrors[name]}</p>}
    </div>
  );

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button onClick={() => { setFormErrors({}); setShowAdd(true); }}
          className="flex items-center gap-1.5 text-sm font-semibold bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors">
          <Plus className="w-4 h-4" /> Create user
        </button>
      </div>

      {banner && (
        <div className={`text-sm px-4 py-2 rounded-lg border ${banner.type === 'ok' ? 'bg-green-50 text-green-700 border-green-200' : 'bg-red-50 text-red-700 border-red-200'}`}>
          {banner.msg}
        </div>
      )}
      {error && <ErrorBanner message={error} onRetry={load} />}

      {loading ? <SkeletonTable rows={6} /> : users.length === 0 ? (
        <EmptyState icon="👤" title="No users" />
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-gray-100">
              <tr className="text-xs text-gray-500 text-left">
                <th className="px-4 py-3 font-medium">Username</th>
                <th className="px-4 py-3 font-medium">Full name</th>
                <th className="px-4 py-3 font-medium">Role</th>
                <th className="px-4 py-3 font-medium hidden md:table-cell">Doctor</th>
                <th className="px-4 py-3 font-medium">Active</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {users.map((u) => {
                const doc = doctors.find((d) => d.id === u.doctor_id);
                const isMe = u.id === me?.id;
                return (
                  <tr key={u.id} className={`hover:bg-gray-50 ${isMe ? 'bg-blue-50' : ''}`}>
                    <td className="px-4 py-3 font-mono font-medium text-gray-900">
                      {u.username} {isMe && <span className="text-xs text-blue-500 font-normal">(you)</span>}
                    </td>
                    <td className="px-4 py-3 text-gray-700">{u.full_name}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${rolePill(u.role)}`}>{u.role}</span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs hidden md:table-cell">
                      {doc ? `Dr. ${doc.name}` : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => toggleActive(u)}
                        disabled={isMe}
                        title={isMe ? 'Cannot deactivate yourself' : u.is_active ? 'Deactivate' : 'Activate'}
                        className="disabled:opacity-40 disabled:cursor-not-allowed"
                      >
                        {u.is_active
                          ? <ToggleRight className="w-6 h-6 text-green-500" />
                          : <ToggleLeft className="w-6 h-6 text-gray-400" />}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Create user modal */}
      <Modal open={showAdd} onClose={() => setShowAdd(false)} title="Create User">
        <Field label="Username" name="username" />
        <Field label="Password" name="password" type="password" />
        <Field label="Full name" name="full_name" />
        <Field label="Role" name="role">
          <select value={form.role}
            onChange={(e) => setForm((f) => ({ ...f, role: e.target.value, doctor_id: '' }))}
            className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none">
            {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </Field>
        {form.role === 'DOCTOR' && (
          <Field label="Linked doctor" name="doctor_id">
            <select value={form.doctor_id}
              onChange={(e) => { setForm((f) => ({ ...f, doctor_id: e.target.value })); setFormErrors((f) => ({ ...f, doctor_id: '' })); }}
              className={`w-full text-sm border rounded-lg px-3 py-2 focus:outline-none ${formErrors.doctor_id ? 'border-red-400' : 'border-gray-200'}`}>
              <option value="">— Select doctor —</option>
              {doctors.map((d) => <option key={d.id} value={d.id}>Dr. {d.name}</option>)}
            </select>
            {formErrors.doctor_id && <p className="text-xs text-red-500 mt-0.5">{formErrors.doctor_id}</p>}
          </Field>
        )}
        <div className="flex justify-end gap-2 mt-2">
          <button onClick={() => setShowAdd(false)} className="px-4 py-2 text-sm text-gray-600 rounded-lg hover:bg-gray-100">Cancel</button>
          <button onClick={handleCreate} disabled={saving}
            className="px-4 py-2 text-sm font-semibold bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-60">
            {saving ? 'Creating…' : 'Create'}
          </button>
        </div>
      </Modal>
    </div>
  );
}
