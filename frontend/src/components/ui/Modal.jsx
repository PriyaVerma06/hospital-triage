/**
 * Modal — simple accessible dialog overlay.
 * Usage: <Modal open={bool} onClose={fn} title="…">content</Modal>
 */
import { useEffect } from 'react';
import { X } from 'lucide-react';

export default function Modal({ open, onClose, title, children, maxWidth = 'max-w-lg' }) {
  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <>
      <div className="fixed inset-0 bg-black/40 z-40" onClick={onClose} aria-hidden="true" />
      <div className={`fixed inset-0 z-50 flex items-center justify-center p-4`}>
        <div className={`bg-white rounded-xl shadow-2xl w-full ${maxWidth} flex flex-col max-h-[90vh]`}>
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-4 border-b">
            <h2 className="font-bold text-gray-900 text-lg">{title}</h2>
            <button onClick={onClose} className="p-1 rounded hover:bg-gray-100" aria-label="Close">
              <X className="w-5 h-5 text-gray-500" />
            </button>
          </div>
          {/* Body */}
          <div className="overflow-y-auto px-5 py-4 flex-1">{children}</div>
        </div>
      </div>
    </>
  );
}
