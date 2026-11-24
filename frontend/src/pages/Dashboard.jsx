/**
 * Dashboard page — live hospital wall monitor.
 *
 * Layout:
 *   [Doctor alert strip — DOCTOR only, unacknowledged alerts]
 *   [StatusBar — connection + 5 metric cards]
 *   [PriorityQueue (wide)] | [BedMap + DoctorPanel stacked]
 *   [ActivePatients (full width)]
 *
 * Data comes from useDashboardData which subscribes to the shared
 * LiveContext socket and refreshes on events.
 */
import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Plus, RefreshCw, Bell } from 'lucide-react';
import { useAuth } from '../context/AuthContext.jsx';
import { useLive } from '../context/LiveContext.jsx';
import { useDashboardData } from '../hooks/useDashboardData.js';
import { getAlerts } from '../lib/api.js';
import StatusBar     from '../components/dashboard/StatusBar.jsx';
import PriorityQueue from '../components/dashboard/PriorityQueue.jsx';
import ActivePatients from '../components/dashboard/ActivePatients.jsx';
import BedMap        from '../components/dashboard/BedMap.jsx';
import DoctorPanel   from '../components/dashboard/DoctorPanel.jsx';

/**
 * DoctorAlertStrip — compact unacknowledged-alert banner for DOCTOR users.
 * Fetches /alerts on mount and increments count on live "alert" socket events.
 * Links to /alerts for full management.
 */
function DoctorAlertStrip() {
  const { subscribe } = useLive();
  const [count, setCount] = useState(0);

  useEffect(() => {
    getAlerts({ unacknowledged_only: true })
      .then((data) => setCount(data?.length ?? 0))
      .catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const unsub = subscribe((ev) => {
      if (ev.type === 'alert') setCount((c) => c + 1);
    });
    return unsub;
  }, [subscribe]);

  if (count === 0) return null;

  return (
    <div className="flex items-center gap-3 bg-red-50 border border-red-300 text-red-800 rounded-xl px-4 py-2.5">
      <Bell className="w-4 h-4 shrink-0 animate-bounce" />
      <span className="text-sm font-semibold">
        {count} unacknowledged alert{count !== 1 ? 's' : ''}
      </span>
      <Link to="/alerts" className="ml-auto text-sm font-semibold text-red-700 underline hover:no-underline">
        View alerts →
      </Link>
    </div>
  );
}

export default function Dashboard() {
  const { hasRole } = useAuth();
  const { status }  = useLive();
  const {
    queue, assigned, beds, doctors, resources,
    loading, error, refresh, recentlyEscalated,
  } = useDashboardData();

  const isDoctor = hasRole('DOCTOR');

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3 text-gray-400">
        <RefreshCw className="w-8 h-8 animate-spin" />
        <p className="text-sm">Loading dashboard…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3">
        <p className="text-red-600 font-semibold">{error}</p>
        <button onClick={refresh} className="text-sm text-blue-600 underline hover:no-underline">Retry</button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Doctor alert strip — only visible to DOCTOR users */}
      {isDoctor && <DoctorAlertStrip />}

      {/* Top row: status + summary cards + optional "New patient" button */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div className="flex-1">
          <StatusBar status={status} queue={queue} resources={resources} />
        </div>

        {/* "New patient" for NURSE */}
        {hasRole('NURSE') && (
          <Link
            to="/intake"
            className="inline-flex items-center gap-1.5 self-start sm:mt-1 text-sm font-semibold bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors shadow-sm"
          >
            <Plus className="w-4 h-4" />
            New patient
          </Link>
        )}
      </div>

      {/* Main grid: Queue left, Bed Map + Doctor Panel right */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Priority queue — takes 2 of 3 columns */}
        <div className="lg:col-span-2 min-h-[420px] flex flex-col">
          <PriorityQueue
            queue={queue}
            doctors={doctors}
            recentlyEscalated={recentlyEscalated}
            onRefresh={refresh}
          />
        </div>

        {/* Right column: Bed Map above Doctor Panel */}
        <div className="flex flex-col gap-5">
          <BedMap beds={beds} assigned={assigned} doctors={doctors} onRefresh={refresh} />
          <DoctorPanel doctors={doctors} />
        </div>
      </div>

      {/* Full-width active patients */}
      <ActivePatients
        assigned={assigned}
        doctors={doctors}
        recentlyEscalated={recentlyEscalated}
        onRefresh={refresh}
      />
    </div>
  );
}
