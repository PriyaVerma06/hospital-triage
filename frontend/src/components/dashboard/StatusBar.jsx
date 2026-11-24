/**
 * StatusBar — top row of the dashboard.
 * Shows: live connection pill, and five summary cards.
 * The "Waiting" card turns red when any waiting patient is Level 1 or 2.
 */
import { Wifi, WifiOff, RefreshCw } from 'lucide-react';

/** Connection status pill */
function ConnectionPill({ status }) {
  const configs = {
    live:         { icon: Wifi,       label: 'Live',           cls: 'bg-green-100 text-green-700 border-green-300' },
    connecting:   { icon: RefreshCw,  label: 'Connecting…',    cls: 'bg-blue-100 text-blue-700 border-blue-300' },
    reconnecting: { icon: RefreshCw,  label: 'Reconnecting…',  cls: 'bg-amber-100 text-amber-700 border-amber-300' },
    offline:      { icon: WifiOff,    label: 'Offline',        cls: 'bg-red-100 text-red-700 border-red-300' },
  };
  const cfg = configs[status] ?? configs.offline;
  const Icon = cfg.icon;
  const spin = status === 'connecting' || status === 'reconnecting';

  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full border ${cfg.cls}`}>
      <Icon className={`w-3.5 h-3.5 ${spin ? 'animate-spin' : ''}`} />
      {cfg.label}
    </span>
  );
}

/** Single metric card */
function MetricCard({ label, value, highlight }) {
  return (
    <div className={`rounded-xl border p-4 flex flex-col gap-1 shadow-sm ${
      highlight ? 'bg-red-50 border-red-300' : 'bg-white border-gray-200'
    }`}>
      <span className={`text-2xl font-bold ${highlight ? 'text-red-600' : 'text-gray-800'}`}>
        {value ?? '—'}
      </span>
      <span className={`text-xs font-medium ${highlight ? 'text-red-500' : 'text-gray-500'}`}>
        {label}
      </span>
    </div>
  );
}

export default function StatusBar({ status, queue, resources }) {
  // "Waiting" card goes red if any waiting patient is level 1 or 2
  const hasCriticalWaiting = queue?.some((p) => p.urgency_level <= 2) ?? false;

  const icu   = resources?.beds_by_ward?.ICU;
  const freeIcu      = icu ? icu.available : '—';
  const freeVents    = resources?.free_ventilators ?? '—';
  const docsAvail    = resources?.doctors_available ?? '—';
  const waiting      = resources?.patients_waiting ?? queue?.length ?? '—';
  const assigned     = resources
    ? (resources.beds_by_ward?.ICU?.occupied ?? 0) +
      (resources.beds_by_ward?.EMERGENCY?.occupied ?? 0) +
      (resources.beds_by_ward?.GENERAL?.occupied ?? 0)
    : '—';

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <ConnectionPill status={status} />
        <span className="text-sm text-gray-500">Live hospital resource monitor</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <MetricCard
          label="Waiting"
          value={waiting}
          highlight={hasCriticalWaiting}
        />
        <MetricCard label="Assigned" value={assigned} />
        <MetricCard label="Free ICU Beds" value={freeIcu} />
        <MetricCard label="Free Ventilators" value={freeVents} />
        <MetricCard label="Doctors Available" value={docsAvail} />
      </div>
    </div>
  );
}
