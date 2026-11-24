/**
 * Pagination — prev/next + page indicator.
 * page is 0-based.
 */
export default function Pagination({ page, hasMore, onPrev, onNext, loading }) {
  return (
    <div className="flex items-center justify-between pt-3 border-t border-gray-100">
      <button
        onClick={onPrev}
        disabled={page === 0 || loading}
        className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        ← Prev
      </button>
      <span className="text-xs text-gray-400">Page {page + 1}</span>
      <button
        onClick={onNext}
        disabled={!hasMore || loading}
        className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        Next →
      </button>
    </div>
  );
}
