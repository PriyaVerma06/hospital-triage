/**
 * DoctorPanel — one card per doctor.
 * Shows name, specialty, availability pill, and a load bar (patients/5).
 * Highlights the logged-in doctor's own card.
 */
import { useAuth } from '../../context/AuthContext.jsx';

const MAX_LOAD = 5;

/** Colour for load bar segments */
function loadBarColor(count) {
  const pct = count / MAX_LOAD;
  if (pct >= 0.8) return 'bg-red-500';
  if (pct >= 0.5) return 'bg-amber-400';
  return 'bg-green-500';
}

export default function DoctorPanel({ doctors }) {
  const { user } = useAuth();

  if (!doctors || doctors.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
        <h2 className="font-bold text-gray-800 mb-2">Doctors</h2>
        <p className="text-sm text-gray-400">No doctors found.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
      <h2 className="font-bold text-gray-800 mb-3">Doctors</h2>
      <div className="space-y-2">
        {doctors.map((doc) => {
          const isMe  = user?.doctor_id === doc.id;
          const count = doc.active_patients_count ?? 0;

          return (
            <div
              key={doc.id}
              className={`rounded-lg border p-3 transition-colors ${
                isMe
                  ? 'border-purple-300 bg-purple-50'
                  : 'border-gray-100 bg-gray-50 hover:bg-gray-100'
              }`}
            >
              <div className="flex items-center justify-between mb-1.5">
                <div>
                  <span className="text-sm font-semibold text-gray-800">
                    Dr. {doc.name}
                    {isMe && (
                      <span className="ml-1.5 text-xs text-purple-600 font-normal">(you)</span>
                    )}
                  </span>
                  <p className="text-xs text-gray-400">{doc.specialty}</p>
                </div>
                <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                  doc.is_available
                    ? 'bg-green-100 text-green-700'
                    : 'bg-gray-200 text-gray-500'
                }`}>
                  {doc.is_available ? 'On duty' : 'Off duty'}
                </span>
              </div>

              {/* Load bar */}
              <div className="flex items-center gap-2">
                <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${loadBarColor(count)}`}
                    style={{ width: `${Math.min((count / MAX_LOAD) * 100, 100)}%` }}
                  />
                </div>
                <span className="text-xs text-gray-500 tabular-nums w-8 text-right">
                  {count}/{MAX_LOAD}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
