/**
 * Analytics page — four charts + KPI cards with live socket auto-refresh.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  AreaChart, Area, Cell,
} from 'recharts';
import { RefreshCw } from 'lucide-react';
import { useLive } from '../context/LiveContext.jsx';
import {
  getAnalyticsSummary, getTriageDistribution, getOccupancy,
  getWaitByLevel, getTimeline,
} from '../lib/api.js';
import {
  formatMinutes, toDistributionChartData, toWaitByLevelChartData,
  toOccupancyChartData, toTimelineChartData,
} from '../lib/analyticsLogic.js';
import StatCard from '../components/ui/StatCard.jsx';
import ErrorBanner from '../components/ui/ErrorBanner.jsx';
import { SkeletonCard } from '../components/ui/Skeleton.jsx';
import EmptyState from '../components/ui/EmptyState.jsx';

const WINDOWS = [
  { label: '6 h',    hours: 6   },
  { label: '24 h',   hours: 24  },
  { label: '7 days', hours: 168 },
  { label: '30 days',hours: 720 },
];

const DEBOUNCE_MS = 500;
const POLL_MS = 60000;

/** Panel wrapper */
function ChartPanel({ title, children }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
      <h3 className="font-semibold text-gray-700 mb-4">{title}</h3>
      {children}
    </div>
  );
}

export default function Analytics() {
  const [hours, setHours] = useState(24);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [summary, setSummary] = useState(null);
  const [distribution, setDistribution] = useState(null);
  const [occupancy, setOccupancy] = useState(null);
  const [waitByLevel, setWaitByLevel] = useState(null);
  const [timeline, setTimeline] = useState(null);

  const { subscribe, status } = useLive();
  const debounceRef = useRef(null);
  const pollRef = useRef(null);
  const hoursRef = useRef(hours);
  useEffect(() => { hoursRef.current = hours; }, [hours]);

  const fetchAll = useCallback(async (h) => {
    const win = h ?? hoursRef.current;
    setError(null);
    try {
      const [s, d, o, w, t] = await Promise.all([
        getAnalyticsSummary(win),
        getTriageDistribution(win),
        getOccupancy(),
        getWaitByLevel(win),
        getTimeline(win),
      ]);
      setSummary(s);
      setDistribution(d);
      setOccupancy(o);
      setWaitByLevel(w);
      setTimeline(t);
    } catch (err) {
      setError(err.message ?? 'Failed to load analytics');
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial + on hours change
  useEffect(() => {
    setLoading(true);
    fetchAll(hours);
  }, [hours]); // eslint-disable-line react-hooks/exhaustive-deps

  // Socket-triggered refresh (debounced)
  useEffect(() => {
    const unsub = subscribe((ev) => {
      if (ev.type === 'queue_changed' || ev.type === 'resources_changed' || ev.type === 'patient_created') {
        clearTimeout(debounceRef.current);
        debounceRef.current = setTimeout(() => fetchAll(), DEBOUNCE_MS);
      }
    });
    return unsub;
  }, [subscribe, fetchAll]);

  // Fallback poll when socket not live
  useEffect(() => {
    if (status === 'live') { clearInterval(pollRef.current); return; }
    pollRef.current = setInterval(() => fetchAll(), POLL_MS);
    return () => clearInterval(pollRef.current);
  }, [status, fetchAll]);

  const distData  = toDistributionChartData(distribution);
  const waitData  = toWaitByLevelChartData(waitByLevel);
  const occData   = toOccupancyChartData(occupancy);
  const timeData  = toTimelineChartData(timeline);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold text-gray-800">Analytics</h1>
        <div className="flex items-center gap-2">
          {/* Time window selector */}
          <div className="flex gap-1">
            {WINDOWS.map((w) => (
              <button
                key={w.hours}
                onClick={() => setHours(w.hours)}
                className={`text-xs font-semibold px-3 py-1.5 rounded-lg border transition-colors ${
                  hours === w.hours
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-600 border-gray-300 hover:border-gray-400'
                }`}
              >
                {w.label}
              </button>
            ))}
          </div>
          <button
            onClick={() => { setLoading(true); fetchAll(); }}
            className="p-1.5 rounded-lg border border-gray-300 hover:bg-gray-50"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 text-gray-500 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {error && <ErrorBanner message={error} onRetry={() => { setLoading(true); fetchAll(); }} />}

      {/* KPI cards */}
      {loading && !summary ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : summary ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <StatCard label="Total Patients" value={summary.total_patients} />
          <StatCard label="Avg Wait" value={formatMinutes(summary.avg_wait_minutes)} />
          <StatCard label="Critical (L1-2)" value={summary.critical_count} highlight={summary.critical_count > 0} />
          <StatCard label="Currently Waiting" value={summary.waiting} highlight={summary.waiting > 0} />
          <StatCard label="Assigned" value={summary.assigned} />
          <StatCard label="Discharged" value={summary.discharged} />
        </div>
      ) : null}

      {/* Charts grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Triage distribution */}
        <ChartPanel title="Triage Distribution">
          {distData.every((d) => d.count === 0) ? (
            <EmptyState icon="📊" title="No data" message="No patients in this time window." />
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={distData} margin={{ top: 0, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip formatter={(v) => [v, 'Patients']} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {distData.map((d) => <Cell key={d.level} fill={d.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartPanel>

        {/* Avg wait by level */}
        <ChartPanel title="Avg Wait by Level (min)">
          {waitData.every((d) => d.avg_wait_minutes === 0) ? (
            <EmptyState icon="⏱️" title="No wait data" message="No patients with wait times recorded." />
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={waitData} margin={{ top: 0, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => [`${v} min`, 'Avg wait']} />
                <Bar dataKey="avg_wait_minutes" radius={[4, 4, 0, 0]}>
                  {waitData.map((d) => <Cell key={d.level} fill={d.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartPanel>

        {/* Bed occupancy */}
        <ChartPanel title="Bed Occupancy by Ward">
          {occData.length === 0 ? (
            <EmptyState icon="🛏️" title="No bed data" />
          ) : (
            <>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={occData} layout="vertical" margin={{ top: 0, right: 30, left: 10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} />
                  <YAxis type="category" dataKey="ward" tick={{ fontSize: 11 }} width={80} />
                  <Tooltip />
                  <Legend iconSize={10} wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="available" stackId="a" fill="#86efac" name="Available" radius={[0,0,0,0]} />
                  <Bar dataKey="occupied"  stackId="a" fill="#f87171" name="Occupied" />
                  <Bar dataKey="cleaning"  stackId="a" fill="#fcd34d" name="Cleaning" radius={[0,4,4,0]} />
                </BarChart>
              </ResponsiveContainer>
              {/* Ventilators */}
              {occupancy?.ventilators && (
                <div className="mt-3 flex gap-4 text-xs text-gray-500 border-t pt-3">
                  <span>Ventilators free: <strong>{occupancy.ventilators.free}</strong></span>
                  <span>In use: <strong>{occupancy.ventilators.in_use}</strong></span>
                  <span>Total: <strong>{occupancy.ventilators.total}</strong></span>
                </div>
              )}
            </>
          )}
        </ChartPanel>

        {/* Arrivals timeline */}
        <ChartPanel title="Arrivals Timeline">
          {timeData.length === 0 ? (
            <EmptyState icon="📈" title="No timeline data" />
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={timeData} margin={{ top: 0, right: 10, left: -10, bottom: 0 }}>
                <defs>
                  <linearGradient id="arrGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}   />
                  </linearGradient>
                  <linearGradient id="critGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#ef4444" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0}   />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="label" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip />
                <Legend iconSize={10} wrapperStyle={{ fontSize: 11 }} />
                <Area type="monotone" dataKey="arrivals" stroke="#3b82f6" fill="url(#arrGrad)" name="Arrivals" strokeWidth={2} />
                <Area type="monotone" dataKey="critical"  stroke="#ef4444" fill="url(#critGrad)" name="Critical" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </ChartPanel>
      </div>
    </div>
  );
}
