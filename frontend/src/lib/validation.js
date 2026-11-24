/**
 * Client-side validation matching the backend's Pydantic field constraints.
 * Exported as pure functions so they can be unit-tested with Vitest.
 */

/** Validation rules (mirrors backend schemas.py ranges) */
export const RULES = {
  name:     { required: true, minLength: 1 },
  age:      { required: true, min: 0,   max: 120  },
  gender:   { required: true, options: ['M', 'F'] },
  sbp:      { required: true, min: 50,  max: 300,  unit: 'mmHg', label: 'Systolic BP' },
  dbp:      { required: true, min: 30,  max: 200,  unit: 'mmHg', label: 'Diastolic BP' },
  hr:       { required: true, min: 20,  max: 250,  unit: 'bpm',  label: 'Heart Rate' },
  spo2:     { required: true, min: 50,  max: 100,  unit: '%',    label: 'SpO₂' },
  temp:     { required: true, min: 30,  max: 45,   unit: '°C',   label: 'Temperature' },
  rr:       { required: true, min: 4,   max: 60,   unit: '/min', label: 'Resp. Rate' },
};

/**
 * Validate a single field value.
 * @param {string} field  - key from RULES
 * @param {any}    value
 * @returns {string|null} error message or null if valid
 */
export function validateField(field, value) {
  const rule = RULES[field];
  if (!rule) return null;

  if (field === 'name') {
    if (!value || String(value).trim().length < 1) return 'Name is required.';
    return null;
  }
  if (field === 'gender') {
    if (!rule.options.includes(value)) return 'Please select M or F.';
    return null;
  }

  const num = Number(value);
  if (rule.required && (value === '' || value === null || value === undefined)) {
    return `${rule.label ?? field} is required.`;
  }
  if (isNaN(num)) return `${rule.label ?? field} must be a number.`;
  if (num < rule.min) return `${rule.label ?? field} must be ≥ ${rule.min} ${rule.unit ?? ''}.`;
  if (num > rule.max) return `${rule.label ?? field} must be ≤ ${rule.max} ${rule.unit ?? ''}.`;
  return null;
}

/**
 * Validate the full form object.
 * @param {object} form
 * @returns {{ errors: Record<string,string>, valid: boolean }}
 */
export function validateForm(form) {
  const errors = {};

  for (const field of Object.keys(RULES)) {
    const err = validateField(field, form[field]);
    if (err) errors[field] = err;
  }

  // Cross-field: sbp must be strictly greater than dbp
  if (!errors.sbp && !errors.dbp) {
    if (Number(form.sbp) <= Number(form.dbp)) {
      errors.sbp = 'Systolic BP must be greater than Diastolic BP.';
    }
  }

  return { errors, valid: Object.keys(errors).length === 0 };
}

/**
 * Soft warning: returns a warning string for dangerous-but-valid values.
 * These are shown as amber notices, not blocking errors.
 * @param {string} field
 * @param {number|string} value
 * @returns {string|null}
 */
export function softWarning(field, value) {
  const num = Number(value);
  if (isNaN(num)) return null;
  if (field === 'spo2' && num < 90)  return 'Critically low — consider immediate intervention.';
  if (field === 'spo2' && num < 94)  return 'Below normal — monitor closely.';
  if (field === 'hr'   && num > 140) return 'Very high heart rate.';
  if (field === 'hr'   && num < 50)  return 'Very low heart rate.';
  if (field === 'sbp'  && num < 90)  return 'Hypotensive — assess urgently.';
  if (field === 'sbp'  && num > 180) return 'Hypertensive crisis range.';
  if (field === 'temp' && num > 39)  return 'High fever.';
  if (field === 'temp' && num < 36)  return 'Hypothermia range.';
  if (field === 'rr'   && num > 25)  return 'Elevated respiratory rate.';
  return null;
}
