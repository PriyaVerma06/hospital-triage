/**
 * Admin/ActivityLogTab — paginated admin action log.
 */
import { useState, useEffect, useCallback } from 'react';
import { ChevronDown } from 'lucide-react';
import { getAdminLogs } from '../../lib/api.js';
import ErrorBanner from '../ui/ErrorBanner.jsx';
import EmptyState from '../ui/EmptyState.jsx';
import { SkeletonTable } from '../ui/Skeleton.jsx';

const INITIAL_LIMIT = 50;
const LOAD_MORE = 50;

export default function ActivityLogTab() {
  const [logs, setLogs]     = useState([]);
  const [limit, setLimit]   = useState(INITIAL_LIMIT);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(null);
  const [hasMore, setHasMore] = useState(false);

  const load = useCallback(async (l) => {
    setLoading(true); setError(null);
    try {
      // Fetch one extra to know if there are more
      const data = await getAdminLogs(l + 1);
      setHasMore(data.length > l);
      setLogs(data.slice(0, l));
    } catch (e) { setError(e.message ?? 'Failed to load logs'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(limit); }, [limit, load]);

  return (
    <div className="space-y-4">
      {error && <ErrorBanner message={error} onRetry={() => load(limit)} />}

      {loading && logs.length === 0 ? <SkeletonTable rows={8} /> : logs.length === 0 ? (
        <EmptyState icon="📋" title="No activity recorded" />
      ) : (
        <>
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead className="border-b border-gray-100">
                <tr className="text-xs text-gray-500 text-left">
                  <th className="px-4 py-3 font-medium">Time</th>
                  <th className="px-4 py-3 font-medium">User ID</th>
                  <th className="px-4 py-3 font-medium">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-xs text-gray-400 whitespace-nowrap">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-gray-500">{log.user_id ?? '—'}</td>
                    <td className="px-4 py-3 text-gray-700">{log.action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {hasMore && (
            <div className="flex justify-center">
              <button
                onClick={() => setLimit((l) => l + LOAD_MORE)}
                disabled={loading}
                className="flex items-center gap-1.5 text-sm text-blue-600 hover:underline disabled:opacity-60"
              >
                <ChevronDown className="w-4 h-4" /> Load more
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
