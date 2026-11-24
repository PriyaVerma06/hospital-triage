/** StatCard — a simple KPI metric card. */
export default function StatCard({ label, value, sub, highlight }) {
  return (
    <div className={`rounded-xl border p-4 shadow-sm ${highlight ? 'bg-red-50 border-red-300' : 'bg-white border-gray-200'}`}>
      <p className={`text-2xl font-bold ${highlight ? 'text-red-600' : 'text-gray-800'}`}>{value ?? '—'}</p>
      <p className={`text-xs font-medium mt-0.5 ${highlight ? 'text-red-500' : 'text-gray-500'}`}>{label}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}
