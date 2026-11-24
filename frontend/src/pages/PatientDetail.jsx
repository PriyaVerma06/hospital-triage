/**
 * Patient Detail page — /patients/:id
 *
 * Shows:
 *  - Full patient card: vitals, level badge, reason tags, status, assignment
 *  - "Update vitals" collapsible form with the same validation
 *  - Reprioritization banner when level_changed
 *  - Audit history list (newest first)
 */
import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getPatient, updateVitals, getPatientAudit } from '../lib/api.js';
import { validateField, validateForm, softWarning } from '../lib/validation.js';
import { LevelBadge } from '../lib/urgency.jsx';
import { AlertTriangle, ArrowLeft, ChevronDown, ChevronUp, Loader2, RefreshCw } from 'lucide-react';

// ---------------------------------------------------------------------------
// Vitals update form (same ranges as intake)
// ---------------------------------------------------------------------------
const VITAL_FIELDS = [
  { id: 'sbp',  label: 'Systolic BP',  unit: 'mmHg' },
  { id: 'dbp',  label: 'Diastolic BP', unit: 'mmHg' },
  { id: 'hr',   label: 'Heart Rate',   unit: 'bpm' },
  { id: 'spo2', label: 'SpO₂',         unit: '%',  step: '0.1' },
  { id: 'temp', label: 'Temperature',  unit: '°C', step: '0.1' },
  { id: 'rr',   label: 'Resp. Rate',   unit: '/min' },
];

function VitalsForm({ patientId, currentVitals, onUpdated }) {
  const [form, setForm]       = useState({
    sbp: currentVitals.sbp ?? '', dbp: currentVitals.dbp ?? '',
    hr: currentVitals.hr ?? '', spo2: currentVitals.spo2 ?? '',
    temp: currentVitals.temp ?? '', rr: currentVitals.rr ?? '',
  });
  const [touched, setTouched] = useState({});
  const [errors, setErrors]   = useState({});
  const [submitting, setSub]  = useState(false);
  const [banner, setBanner]   = useState('');

  function handleBlur(id) {
    setTouched((t) => ({ ...t, [id]: true }));
    setErrors((e) => ({ ...e, [id]: validateField(id, form[id]) }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setBanner('');
    // validate vitals subset only
    const vitalsKeys = VITAL_FIELDS.map((f) => f.id);
    const allTouched = Object.fromEntries(vitalsKeys.map((k) => [k, true]));
    setTouched(allTouched);
    const relevantForm = { ...form, name: 'x', age: 50, gender: 'M' }; // satisfy validateForm
    const { errors: errs } = validateForm(relevantForm);
    const vitalsErrors = Object.fromEntries(Object.entries(errs).filter(([k]) => vitalsKeys.includes(k)));
    setErrors(vitalsErrors);
    if (Object.keys(vitalsErrors).length > 0) return;

    setSub(true);
    try {
      const payload = {
        sbp: Number(form.sbp), dbp: Number(form.dbp),
        hr: Number(form.hr), spo2: Number(form.spo2),
        temp: Number(form.temp), rr: Number(form.rr),
      };
      const result = await updateVitals(patientId, payload);
      onUpdated(result);
    } catch (err) {
      if (err.fieldErrors) setErrors((e) => ({ ...e, ...err.fieldErrors }));
      else setBanner(err.message ?? 'Failed to update vitals.');
    } finally {
      setSub(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      {banner && (
        <p className="text-red-600 text-sm mb-3 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{banner}</p>
      )}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
        {VITAL_FIELDS.map(({ id, label, unit, step }) => (
          <div key={id}>
            <label htmlFor={`v-${id}`} className="block text-xs font-medium text-gray-600 mb-1">
              {label} <span className="text-gray-400">({unit})</span>
            </label>
            <input
              id={`v-${id}`}
              type="number"
              step={step ?? 1}
              inputMode="numeric"
              value={form[id]}
              onChange={(e) => { setForm((f) => ({ ...f, [id]: e.target.value })); setErrors((er) => ({ ...er, [id]: undefined })); }}
              onBlur={() => handleBlur(id)}
              className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${errors[id] && touched[id] ? 'border-red-400 bg-red-50' : 'border-gray-300'}`}
            />
            {errors[id] && touched[id] && <p className="text-red-500 text-xs mt-0.5">{errors[id]}</p>}
            {!errors[id] && softWarning(id, form[id]) && (
              <p className="text-amber-600 text-xs mt-0.5">{softWarning(id, form[id])}</p>
            )}
          </div>
        ))}
      </div>
      <button
        type="submit"
        disabled={submitting}
        className="w-full bg-blue-700 hover:bg-blue-800 disabled:bg-blue-300 text-white font-semibold rounded-lg py-2 text-sm transition-colors flex items-center justify-center gap-2"
      >
        {submitting ? <><Loader2 className="w-3 h-3 animate-spin" /> Updating…</> : 'Update Vitals & Re-triage'}
      </button>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Vitals display grid
// ---------------------------------------------------------------------------
function VitalsGrid({ p }) {
  const vitals = [
    { label: 'Systolic BP',  value: p.sbp,  unit: 'mmHg' },
    { label: 'Diastolic BP', value: p.dbp,  unit: 'mmHg' },
    { label: 'Heart Rate',   value: p.hr,   unit: 'bpm' },
    { label: 'SpO₂',         value: p.spo2, unit: '%' },
    { label: 'Temperature',  value: p.temp, unit: '°C' },
    { label: 'Resp. Rate',   value: p.rr,   unit: '/min' },
  ];
  return (
    <div className="grid grid-cols-3 sm:grid-cols-6 gap-3 mt-4">
      {vitals.map(({ label, value, unit }) => (
        <div key={label} className="text-center bg-gray-50 rounded-lg p-2">
          <p className="text-xs text-gray-500 mb-0.5">{label}</p>
          <p className="text-lg font-bold text-gray-800">{value ?? '—'}<span className="text-xs font-normal text-gray-500 ml-0.5">{unit}</span></p>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------
function StatusBadge({ status }) {
  const cls = {
    WAITING:    'bg-amber-100 text-amber-800',
    ASSIGNED:   'bg-blue-100 text-blue-800',
    DISCHARGED: 'bg-gray-100 text-gray-600',
  }[status] ?? 'bg-gray-100 text-gray-600';
  return <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${cls}`}>{status}</span>;
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export default function PatientDetail() {
  const { id } = useParams();
  const [patient, setPatient]   = useState(null);
  const [audit, setAudit]       = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState('');
  const [showVitals, setShowVitals] = useState(false);
  const [updateResult, setUpdateResult] = useState(null); // last vitals update response

  useEffect(() => {
    setLoading(true);
    Promise.all([getPatient(id), getPatientAudit(id)])
      .then(([p, a]) => { setPatient(p); setAudit(a ?? []); })
      .catch((err) => setError(err.message ?? 'Failed to load patient.'))
      .finally(() => setLoading(false));
  }, [id]);

  function handleVitalsUpdated(result) {
    setPatient(result);       // update displayed data
    setUpdateResult(result);  // store for banner
    setShowVitals(false);
    // Refresh audit log
    getPatientAudit(id).then(setAudit).catch(() => {});
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[40vh] text-gray-400 gap-2">
        <Loader2 className="animate-spin w-5 h-5" /> Loading patient…
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-16">
        <p className="text-red-500 font-semibold mb-2">{error}</p>
        <Link to="/" className="text-blue-700 text-sm hover:underline">← Go back</Link>
      </div>
    );
  }

  if (!patient) return null;

  return (
    <div className="max-w-2xl mx-auto space-y-5">
      {/* Back link */}
      <Link to="/intake" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-800">
        <ArrowLeft className="w-4 h-4" /> Back to Intake
      </Link>

      {/* Re-prioritization banner */}
      {updateResult?.level_changed && (
        <div className="bg-orange-50 border border-orange-300 text-orange-800 rounded-xl px-4 py-3 text-sm font-medium flex items-center gap-2">
          <RefreshCw className="w-4 h-4" />
          Re-prioritized from Level {updateResult.previous_level} to Level {updateResult.urgency_level}
        </div>
      )}

      {/* Patient card */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h1 className="text-xl font-bold text-gray-800">{patient.name}</h1>
            <p className="text-sm text-gray-500">
              Age {patient.age} · {patient.gender === 'M' ? 'Male' : 'Female'} · ID #{patient.id}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {patient.urgency_level && <LevelBadge level={patient.urgency_level} size="md" />}
            <StatusBadge status={patient.status} />
          </div>
        </div>

        {/* Symptoms */}
        {patient.symptoms && (
          <p className="text-sm text-gray-700 bg-gray-50 rounded-lg px-3 py-2 mb-3">
            <span className="font-medium text-gray-500">Symptoms: </span>{patient.symptoms}
          </p>
        )}

        {/* Reason tags */}
        {patient.reason_tags?.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-3">
            {patient.reason_tags.map((tag) => (
              <span key={tag} className="text-xs bg-blue-50 text-blue-700 border border-blue-200 rounded-full px-2.5 py-0.5">
                {tag.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        )}

        {/* Assignment info */}
        {(patient.assigned_bed_id || patient.assigned_doctor_id) && (
          <div className="text-sm text-gray-600 mb-3">
            {patient.assigned_bed_id && <span className="mr-4">🛏 Bed: <strong>{patient.assigned_bed_id}</strong></span>}
            {patient.assigned_doctor_id && <span>👨‍⚕️ Doctor: <strong>#{patient.assigned_doctor_id}</strong></span>}
          </div>
        )}

        {/* Vitals grid */}
        <VitalsGrid p={patient} />
      </div>

      {/* Update Vitals section */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
        <button
          onClick={() => setShowVitals((v) => !v)}
          className="w-full flex items-center justify-between text-left"
        >
          <span className="text-sm font-semibold text-gray-700">Update Vitals & Re-triage</span>
          {showVitals ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
        </button>
        {showVitals && (
          <div className="mt-4 border-t border-gray-100 pt-4">
            <VitalsForm
              patientId={patient.id}
              currentVitals={patient}
              onUpdated={handleVitalsUpdated}
            />
          </div>
        )}
      </div>

      {/* Audit log */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-3">Audit History</h2>
        {audit.length === 0 ? (
          <p className="text-gray-400 text-sm">No audit events yet.</p>
        ) : (
          <ul className="space-y-2">
            {audit.map((entry) => (
              <li key={entry.id} className="flex items-start gap-3 text-sm">
                <span className="text-gray-400 text-xs mt-0.5 w-32 shrink-0">
                  {new Date(entry.timestamp).toLocaleString()}
                </span>
                <span className="text-gray-700">{entry.event}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
