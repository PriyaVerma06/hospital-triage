/**
 * Patient Intake form — designed for speed during a busy shift.
 *
 * Sections:
 *  1. Patient: name, age, gender toggle
 *  2. Symptoms: free text + quick-pick chips
 *  3. Vitals: sbp, dbp, hr, spo2, temp, rr with units
 *
 * Features:
 *  - Blur + submit validation matching backend ranges
 *  - Soft danger warnings as the nurse types
 *  - Enter moves to next field
 *  - "Fill sample patient" dropdown for demos
 *  - On success: colour-coded result card with allocation info
 *  - 422 field errors mapped onto fields; other errors as banner
 */
import { useState, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { createPatient } from '../lib/api.js';
import { validateField, validateForm, softWarning } from '../lib/validation.js';
import { LevelBadge } from '../lib/urgency.jsx';
import { ChevronDown, AlertTriangle, CheckCircle, Loader2 } from 'lucide-react';

// ---------------------------------------------------------------------------
// Sample patients for the demo dropdown
// ---------------------------------------------------------------------------
const SAMPLES = {
  Critical: {
    name: 'Alice Critical', age: 65, gender: 'F',
    symptoms: 'unconscious, not breathing, severe bleeding',
    sbp: 70, dbp: 40, hr: 150, spo2: 82, temp: 38.5, rr: 35,
  },
  Serious: {
    name: 'Bob Serious', age: 52, gender: 'M',
    symptoms: 'chest pain, difficulty breathing',
    sbp: 160, dbp: 95, hr: 115, spo2: 91, temp: 37.2, rr: 24,
  },
  Mild: {
    name: 'Carol Mild', age: 30, gender: 'F',
    symptoms: 'headache, mild fever',
    sbp: 125, dbp: 80, hr: 82, spo2: 98, temp: 38.1, rr: 17,
  },
};

// Quick-pick symptom chips
const SYMPTOM_CHIPS = [
  'Chest pain', 'Difficulty breathing', 'Unconscious',
  'Severe bleeding', 'Fever', 'Abdominal pain', 'Headache', 'Minor injury',
];

// Field tab order for Enter-to-advance
const FIELD_ORDER = ['name', 'age', 'gender', 'symptoms', 'sbp', 'dbp', 'hr', 'spo2', 'temp', 'rr'];

// Initial empty form state
const EMPTY_FORM = {
  name: '', age: '', gender: '', symptoms: '',
  sbp: '', dbp: '', hr: '', spo2: '', temp: '', rr: '',
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Labelled text / number input field */
function VitalInput({ id, label, unit, value, onChange, onBlur, error, warning, inputMode = 'numeric', step, autoFocus }) {
  return (
    <div>
      <label htmlFor={id} className="block text-xs font-medium text-gray-600 mb-1">
        {label} {unit && <span className="text-gray-400">({unit})</span>}
      </label>
      <input
        id={id}
        name={id}
        type="number"
        step={step ?? 1}
        inputMode={inputMode}
        autoFocus={autoFocus}
        value={value}
        onChange={onChange}
        onBlur={onBlur}
        className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
          error ? 'border-red-400 bg-red-50' : 'border-gray-300'
        }`}
        placeholder={unit}
      />
      {error   && <p className="text-red-500 text-xs mt-0.5">{error}</p>}
      {!error && warning && (
        <p className="text-amber-600 text-xs mt-0.5 flex items-center gap-1">
          <AlertTriangle className="w-3 h-3 inline" />{warning}
        </p>
      )}
    </div>
  );
}

/** Allocation result section shown after success */
function AllocationResult({ allocation }) {
  if (!allocation) return null;
  if (allocation.assigned) {
    return (
      <div className="bg-green-50 border border-green-200 rounded-xl p-4 mt-4">
        <div className="flex items-center gap-2 text-green-700 font-semibold mb-1">
          <CheckCircle className="w-4 h-4" />
          Resources Assigned
        </div>
        <p className="text-sm text-green-800">
          <strong>Bed:</strong> {allocation.bed_id} &nbsp;|&nbsp; <strong>Doctor ID:</strong> {allocation.doctor_id}
        </p>
        <p className="text-xs text-green-700 mt-1">{allocation.message}</p>
      </div>
    );
  }
  return (
    <div className="bg-amber-50 border border-amber-300 rounded-xl p-4 mt-4">
      <div className="flex items-center gap-2 text-amber-700 font-semibold mb-1">
        <AlertTriangle className="w-4 h-4" />
        Waitlisted
      </div>
      <p className="text-xs text-amber-700">{allocation.message}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Intake component
// ---------------------------------------------------------------------------
export default function Intake() {
  const [form, setForm]       = useState(EMPTY_FORM);
  const [touched, setTouched] = useState({});
  const [errors, setErrors]   = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [banner, setBanner]   = useState('');   // server-level error banner
  const [result, setResult]   = useState(null); // successful intake response
  const [sampleOpen, setSampleOpen] = useState(false);

  // Refs for Enter-to-advance
  const fieldRefs = useRef({});

  // Update a single field value and clear its error
  const setField = useCallback((name, value) => {
    setForm((f) => ({ ...f, [name]: value }));
    setErrors((e) => ({ ...e, [name]: undefined }));
  }, []);

  // Validate a field on blur
  function handleBlur(name) {
    setTouched((t) => ({ ...t, [name]: true }));
    const err = validateField(name, form[name]);
    setErrors((e) => ({ ...e, [name]: err }));
  }

  // Enter key: advance to next field
  function handleKeyDown(e, name) {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    const idx = FIELD_ORDER.indexOf(name);
    const next = FIELD_ORDER[idx + 1];
    if (next && fieldRefs.current[next]) {
      fieldRefs.current[next].focus();
    }
  }

  // Append chip text to symptoms textarea
  function appendChip(chip) {
    setForm((f) => {
      const sep = f.symptoms && !f.symptoms.endsWith(', ') ? ', ' : '';
      return { ...f, symptoms: f.symptoms + sep + chip.toLowerCase() };
    });
  }

  // Fill a sample patient for demo
  function fillSample(key) {
    setForm(SAMPLES[key]);
    setErrors({});
    setTouched({});
    setSampleOpen(false);
    setBanner('');
    setResult(null);
  }

  // Reset to blank form
  function reset() {
    setForm(EMPTY_FORM);
    setErrors({});
    setTouched({});
    setBanner('');
    setResult(null);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setBanner('');

    // Mark all fields touched and validate
    const allTouched = Object.fromEntries(FIELD_ORDER.map((f) => [f, true]));
    setTouched(allTouched);
    const { errors: errs, valid } = validateForm(form);
    setErrors(errs);
    if (!valid) return;

    setSubmitting(true);
    try {
      const payload = {
        name:     form.name.trim(),
        age:      Number(form.age),
        gender:   form.gender,
        symptoms: form.symptoms,
        sbp:      Number(form.sbp),
        dbp:      Number(form.dbp),
        hr:       Number(form.hr),
        spo2:     Number(form.spo2),
        temp:     Number(form.temp),
        rr:       Number(form.rr),
      };
      const data = await createPatient(payload);
      setResult(data);
    } catch (err) {
      if (err.fieldErrors) {
        // 422 — map server field errors onto the form
        setErrors((e) => ({ ...e, ...err.fieldErrors }));
      } else {
        setBanner(err.message ?? 'An unexpected error occurred. Please try again.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  // ---------------------------------------------------------------------------
  // Success Result Card
  // ---------------------------------------------------------------------------
  if (result) {
    const confidencePct = result.confidence != null
      ? `${Math.round(result.confidence * 100)}%`
      : '—';
    return (
      <div className="max-w-xl mx-auto">
        <div className="bg-white rounded-2xl shadow-lg p-6">
          {/* Level badge */}
          <div className="flex items-center gap-3 mb-4">
            <LevelBadge level={result.urgency_level} size="lg" />
            <span className="text-gray-500 text-sm">Model confidence: <strong>{confidencePct}</strong></span>
          </div>

          {/* Patient name */}
          <p className="text-lg font-semibold text-gray-800 mb-1">{result.name}</p>
          <p className="text-sm text-gray-500 mb-4">
            Age {result.age} · {result.gender === 'M' ? 'Male' : 'Female'} · Status: {result.status}
          </p>

          {/* Reason tags */}
          {result.reason_tags?.length > 0 && (
            <div className="mb-4">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">Triage reasons</p>
              <div className="flex flex-wrap gap-1.5">
                {result.reason_tags.map((tag) => (
                  <span key={tag} className="text-xs bg-blue-50 text-blue-700 border border-blue-200 rounded-full px-2.5 py-0.5">
                    {tag.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Allocation result */}
          <AllocationResult allocation={result.allocation} />

          {/* Action buttons */}
          <div className="flex gap-3 mt-6">
            <button
              onClick={reset}
              className="flex-1 bg-blue-700 hover:bg-blue-800 text-white font-semibold rounded-lg py-2.5 text-sm transition-colors"
            >
              New patient
            </button>
            <Link
              to={`/patients/${result.id}`}
              className="flex-1 text-center border border-blue-700 text-blue-700 hover:bg-blue-50 font-semibold rounded-lg py-2.5 text-sm transition-colors"
            >
              View patient
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Intake Form
  // ---------------------------------------------------------------------------
  const isFormValid = Object.keys(validateForm(form).errors).length === 0;

  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Patient Intake</h1>

        {/* Sample patient dropdown */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setSampleOpen((o) => !o)}
            className="flex items-center gap-1 text-sm border border-gray-300 rounded-lg px-3 py-1.5 hover:bg-gray-50 text-gray-600"
          >
            Fill sample <ChevronDown className="w-3 h-3" />
          </button>
          {sampleOpen && (
            <div className="absolute right-0 mt-1 w-36 bg-white border border-gray-200 rounded-lg shadow-lg z-10">
              {Object.keys(SAMPLES).map((key) => (
                <button
                  key={key}
                  onClick={() => fillSample(key)}
                  className="block w-full text-left px-4 py-2 text-sm hover:bg-gray-50 text-gray-700"
                >
                  {key}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Server error banner */}
      {banner && (
        <div className="mb-4 bg-red-50 border border-red-300 text-red-700 rounded-lg px-4 py-3 text-sm flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          {banner}
        </div>
      )}

      <form onSubmit={handleSubmit} noValidate className="space-y-6">
        {/* ── Section 1: Patient ── */}
        <section className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">Patient</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* Name */}
            <div className="sm:col-span-2">
              <label htmlFor="name" className="block text-xs font-medium text-gray-600 mb-1">Full name</label>
              <input
                id="name"
                type="text"
                autoFocus
                value={form.name}
                ref={(el) => { fieldRefs.current.name = el; }}
                onChange={(e) => setField('name', e.target.value)}
                onBlur={() => handleBlur('name')}
                onKeyDown={(e) => handleKeyDown(e, 'name')}
                placeholder="Patient's full name"
                className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${errors.name ? 'border-red-400 bg-red-50' : 'border-gray-300'}`}
              />
              {errors.name && touched.name && <p className="text-red-500 text-xs mt-0.5">{errors.name}</p>}
            </div>

            {/* Age */}
            <div>
              <label htmlFor="age" className="block text-xs font-medium text-gray-600 mb-1">Age (years)</label>
              <input
                id="age"
                type="number"
                inputMode="numeric"
                min={0} max={120}
                value={form.age}
                ref={(el) => { fieldRefs.current.age = el; }}
                onChange={(e) => setField('age', e.target.value)}
                onBlur={() => handleBlur('age')}
                onKeyDown={(e) => handleKeyDown(e, 'age')}
                className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${errors.age && touched.age ? 'border-red-400 bg-red-50' : 'border-gray-300'}`}
              />
              {errors.age && touched.age && <p className="text-red-500 text-xs mt-0.5">{errors.age}</p>}
            </div>
          </div>

          {/* Gender toggle */}
          <div className="mt-4">
            <p className="text-xs font-medium text-gray-600 mb-1">Gender</p>
            <div className="flex gap-2">
              {['M', 'F'].map((g) => (
                <button
                  key={g}
                  type="button"
                  ref={(el) => { if (g === 'M') fieldRefs.current.gender = el; }}
                  onClick={() => { setField('gender', g); handleBlur('gender'); }}
                  className={`px-6 py-2 rounded-lg text-sm font-semibold border-2 transition-colors ${
                    form.gender === g
                      ? 'border-blue-700 bg-blue-700 text-white'
                      : 'border-gray-300 text-gray-600 hover:border-blue-400'
                  }`}
                >
                  {g === 'M' ? 'Male' : 'Female'}
                </button>
              ))}
            </div>
            {errors.gender && touched.gender && <p className="text-red-500 text-xs mt-1">{errors.gender}</p>}
          </div>
        </section>

        {/* ── Section 2: Symptoms ── */}
        <section className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">Symptoms</h2>

          {/* Quick-pick chips */}
          <div className="flex flex-wrap gap-1.5 mb-3">
            {SYMPTOM_CHIPS.map((chip) => (
              <button
                key={chip}
                type="button"
                onClick={() => appendChip(chip)}
                className="text-xs px-3 py-1 rounded-full border border-gray-300 hover:border-blue-400 hover:bg-blue-50 text-gray-600 hover:text-blue-700 transition-colors"
              >
                + {chip}
              </button>
            ))}
          </div>

          <textarea
            id="symptoms"
            ref={(el) => { fieldRefs.current.symptoms = el; }}
            value={form.symptoms}
            onChange={(e) => setField('symptoms', e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) handleKeyDown(e, 'symptoms'); }}
            rows={3}
            placeholder="Describe symptoms… or use the chips above"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
          />
        </section>

        {/* ── Section 3: Vitals ── */}
        <section className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">Vitals</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            {/* Blood Pressure row */}
            {[
              { id: 'sbp', label: 'Systolic BP',  unit: 'mmHg' },
              { id: 'dbp', label: 'Diastolic BP', unit: 'mmHg' },
              { id: 'hr',  label: 'Heart Rate',   unit: 'bpm' },
              { id: 'spo2', label: 'SpO₂',        unit: '%', step: '0.1' },
              { id: 'temp', label: 'Temperature', unit: '°C', step: '0.1' },
              { id: 'rr',   label: 'Resp. Rate',  unit: '/min' },
            ].map(({ id, label, unit, step }) => (
              <VitalInput
                key={id}
                id={id}
                label={label}
                unit={unit}
                step={step}
                value={form[id]}
                onChange={(e) => setField(id, e.target.value)}
                onBlur={() => handleBlur(id)}
                error={touched[id] ? errors[id] : undefined}
                warning={softWarning(id, form[id])}
              />
            ))}
          </div>
          {/* Hidden refs for Enter navigation */}
          {['sbp','dbp','hr','spo2','temp','rr'].map((id) => (
            <input key={id} type="hidden" ref={(el) => { if (el) fieldRefs.current[id] = document.getElementById(id); }} />
          ))}
        </section>

        {/* Submit */}
        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-blue-700 hover:bg-blue-800 disabled:bg-blue-300 text-white font-bold rounded-xl py-3 text-base transition-colors flex items-center justify-center gap-2"
        >
          {submitting ? (
            <><Loader2 className="w-4 h-4 animate-spin" /> Triaging…</>
          ) : (
            'Submit & Triage'
          )}
        </button>
      </form>
    </div>
  );
}
