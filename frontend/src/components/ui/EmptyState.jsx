/** EmptyState — centred empty-state illustration + message. */
export default function EmptyState({ icon = '📭', title, message }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center text-gray-400">
      <span className="text-4xl mb-3">{icon}</span>
      {title && <p className="font-semibold text-gray-600 mb-1">{title}</p>}
      {message && <p className="text-sm">{message}</p>}
    </div>
  );
}
