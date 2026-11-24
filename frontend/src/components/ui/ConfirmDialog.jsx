/**
 * ConfirmDialog — reusable confirm/cancel dialog.
 * Usage: <ConfirmDialog open={bool} onConfirm={fn} onCancel={fn}
 *           title="…" message="…" confirmLabel="Delete" danger />
 */
import Modal from './Modal.jsx';

export default function ConfirmDialog({
  open, onConfirm, onCancel,
  title = 'Are you sure?',
  message,
  confirmLabel = 'Confirm',
  danger = false,
  loading = false,
}) {
  return (
    <Modal open={open} onClose={onCancel} title={title} maxWidth="max-w-sm">
      {message && <p className="text-gray-700 text-sm mb-5">{message}</p>}
      <div className="flex justify-end gap-2">
        <button
          onClick={onCancel}
          className="px-4 py-2 text-sm text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={onConfirm}
          disabled={loading}
          className={`px-4 py-2 text-sm font-semibold text-white rounded-lg transition-colors disabled:opacity-60 ${
            danger ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'
          }`}
        >
          {loading ? 'Please wait…' : confirmLabel}
        </button>
      </div>
    </Modal>
  );
}
