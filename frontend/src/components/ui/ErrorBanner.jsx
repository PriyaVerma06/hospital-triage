/** ErrorBanner — inline error with an optional retry button. */
import { AlertCircle } from 'lucide-react';

export default function ErrorBanner({ message, onRetry }) {
  return (
    <div className="flex items-center gap-3 bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3">
      <AlertCircle className="w-5 h-5 shrink-0" />
      <span className="text-sm flex-1">{message}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          className="text-sm font-semibold underline hover:no-underline"
        >
          Retry
        </button>
      )}
    </div>
  );
}
