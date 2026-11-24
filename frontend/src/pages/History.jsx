/**
 * History page — Patients list + global Audit log (ADMIN/DOCTOR only).
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { Search, ArrowUpCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext.jsx';
import { getPatients, getAuditLog } from '../lib/api.js';
import { LevelBadge } from '../lib/urgency.jsx';
import { pageOffset } from '../lib/analyticsLogic.js';
import Tabs from '../components/ui/Tabs.jsx';
import Pagination from '../components/ui/Pagination.jsx';
import ErrorBanner from '../components/ui/ErrorBanner.jsx';
import EmptyState from '../components/ui/EmptyState.jsx';
import { SkeletonTable } from '../components/ui/Skeleton.jsx';

const PAGE_SIZE = 20;
const DEBOUNCE_MS = 350;

const STATUS_OPTIONS = ['', 'WAITING', 'ASSIGNED', 'DISCHARGED'];

// ---- Patients tab -------------------------------------------------------
function PatientsTab() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(0);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hasMore, setHasMore] = useState(false);
  const debounceRef = useRef(null);

  const fetch = useCallback(async (s, st, p) => {
    setLoading(true);
    setError(null);
    try {
      const params = { limit: PAGE_SIZE + 1, offset: pageOffset(p, PAGE_SIZE) };
      if (s) params.search = s;
      if (st) params.status = st;
      const data = await getPatients(params);
      setHasMore(data.length > PAGE_SIZE);
      setRows(data.slice(0, PAGE_SIZE));
    } catch (err) {
      setError(err.message ?? 'Failed to load patients');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => { setPage(0); fetch(search, status, 0); }, DEBOUNCE_MS);
  }, [search, status]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { fetch(search, status, page); }, [page]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name…"
            className="w-full pl-8 pr-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value); setPage(0); }}
          className="text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All statuses</option>
          {STATUS_OPTIONS.filter(Boolean).map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      {error && <ErrorBanner message={error} onRetry={() => fetch(search, status, page)} />}

      {loading ? <SkeletonTable rows={8} /> : rows.length === 0 ? (
        <EmptyState icon="🔍" title="No patients found" message="Try adjusting your search or filter." />
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-gray-100">
              <tr className="text-xs text-gray-500 text-left">
                <th className="px-4 py-3 font-medium">Patient</th>
                <th className="px-4 py-3 font-medium">Age/Gender</th>
                <th className="px-4 py-3 font-medium">Level</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium hidden md:table-cell">Admitted</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {rows.map((p) => (
                <tr
                  key={p.id}
                  onClick={() => navigate(`/patients/${p.id}`)}
                  className="hover:bg-blue-50 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3 font-medium text-gray-900">{p.name}</td>
                  <td className="px-4 py-3 text-gray-600">{p.age}y · {p.gender}</td>
                  <td className="px-4 py-3"><LevelBadge level={p.urgency_level} size="sm" /></td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                      p.status === 'WAITING'    ? 'bg-yellow-100 text-yellow-800' :
                      p.status === 'ASSIGNED'   ? 'bg-blue-100 text-blue-800'    :
                      p.status === 'DISCHARGED' ? 'bg-gray-100 text-gray-600'    : ''
                    }`}>{p.status}</span>
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs hidden md:table-cell">
                    {p.created_at ? new Date(p.created_at).toLocaleString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Pagination
        page={page} hasMore={hasMore} loading={loading}
        onPrev={() => setPage((p) => p - 1)}
        onNext={() => setPage((p) => p + 1)}
      />
    </div>
  );
}

// ---- Audit tab -----------------------------------------------------------
function AuditTab() {
  const [searchParams] = useSearchParams();
  const initPatientId = searchParams.get('patient_id') ?? '';
  const [patientId, setPatientId] = useState(initPatientId);
  const [page, setPage] = useState(0);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hasMore, setHasMore] = useState(false);

  const fetch = useCallback(async (pid, p) => {
    setLoading(true); setError(null);
    try {
      const params = { limit: PAGE_SIZE + 1, offset: pageOffset(p, PAGE_SIZE) };
      if (pid) params.patient_id = pid;
      const data = await getAuditLog(params);
      setHasMore(data.length > PAGE_SIZE);
      setRows(data.slice(0, PAGE_SIZE));
    } catch (err) {
      setError(err.message ?? 'Failed to load audit log');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetch(patientId, 0); setPage(0); }, [patientId]); // eslint-disable-line
  useEffect(() => { fetch(patientId, page); }, [page]); // eslint-disable-line

  return (
    <div className="space-y-4">
      <div className="flex gap-3">
        <input
          value={patientId}
          onChange={(e) => { setPatientId(e.target.value); setPage(0); }}
          placeholder="Filter by patient ID…"
          className="text-sm border border-gray-200 rounded-lg px-3 py-2 w-48 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {error && <ErrorBanner message={error} onRetry={() => fetch(patientId, page)} />}

      {loading ? <SkeletonTable rows={10} /> : rows.length === 0 ? (
        <EmptyState icon="📋" title="No audit events" message="Nothing to show for the current filter." />
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-gray-100">
              <tr className="text-xs text-gray-500 text-left">
                <th className="px-4 py-3 font-medium">Time</th>
                <th className="px-4 py-3 font-medium">Patient</th>
                <th className="px-4 py-3 font-medium">Event</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {rows.map((entry) => {
                const isEsc = entry.event?.toLowerCase().includes('re-prioriti');
                return (
                  <tr key={entry.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 text-xs text-gray-400 whitespace-nowrap">
                      {new Date(entry.timestamp).toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      {entry.patient_id ? (
                        <Link to={`/patients/${entry.patient_id}`} className="text-blue-600 hover:underline font-medium">
                          {entry.patient_name ?? `#${entry.patient_id}`}
                        </Link>
                      ) : '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-700 flex items-center gap-1">
                      {isEsc && <ArrowUpCircle className="w-3.5 h-3.5 text-orange-500 shrink-0" />}
                      {entry.event}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <Pagination page={page} hasMore={hasMore} loading={loading}
        onPrev={() => setPage((p) => p - 1)} onNext={() => setPage((p) => p + 1)} />
    </div>
  );
}

// ---- Page ----------------------------------------------------------------
export default function History() {
  const { hasRole } = useAuth();
  const canSeeAudit = hasRole('ADMIN', 'DOCTOR');
  const [tab, setTab] = useState('patients');

  const tabs = [
    { key: 'patients', label: 'Patients' },
    { key: 'audit',    label: 'Audit Log', hidden: !canSeeAudit },
  ];

  return (
    <div>
      <h1 className="text-xl font-bold text-gray-800 mb-5">History</h1>
      <Tabs tabs={tabs} active={tab} onChange={setTab} />
      {tab === 'patients' && <PatientsTab />}
      {tab === 'audit'    && canSeeAudit && <AuditTab />}
    </div>
  );
}
