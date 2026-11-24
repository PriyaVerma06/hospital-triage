/** Skeleton — loading placeholder bar. */
export function Skeleton({ className = 'h-4 w-full' }) {
  return <div className={`animate-pulse bg-gray-200 rounded ${className}`} />;
}

/** SkeletonCard — card-shaped loading placeholder. */
export function SkeletonCard() {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-3">
      <Skeleton className="h-5 w-32" />
      <Skeleton className="h-8 w-20" />
      <Skeleton className="h-3 w-24" />
    </div>
  );
}

/** SkeletonTable — table-shaped loading placeholder. */
export function SkeletonTable({ rows = 5 }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}
