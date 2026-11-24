/**
 * Unit tests for src/lib/validation.js
 * Run with:  npm test
 *
 * Tests:
 *  - Valid full form passes validateForm
 *  - Each vital field rejects out-of-range values
 *  - sbp <= dbp triggers cross-field error
 *  - softWarning flags SpO₂ 89 (critically low) but not 97
 *  - validateField rejects missing name / bad gender
 */
import { describe, it, expect } from 'vitest';
import { validateField, validateForm, softWarning } from './validation.js';

// A fully valid form baseline
const VALID = {
  name: 'Jane Doe',
  age:  35,
  gender: 'F',
  symptoms: 'headache',
  sbp:  120,
  dbp:  80,
  hr:   72,
  spo2: 98,
  temp: 37.0,
  rr:   16,
};

// ---------------------------------------------------------------------------
// validateField — single-field tests
// ---------------------------------------------------------------------------
describe('validateField', () => {
  it('passes name when non-empty', () => {
    expect(validateField('name', 'Alice')).toBeNull();
  });

  it('fails name when empty string', () => {
    expect(validateField('name', '')).not.toBeNull();
  });

  it('fails name when whitespace only', () => {
    expect(validateField('name', '   ')).not.toBeNull();
  });

  it('passes gender M', () => {
    expect(validateField('gender', 'M')).toBeNull();
  });

  it('passes gender F', () => {
    expect(validateField('gender', 'F')).toBeNull();
  });

  it('fails gender when invalid value', () => {
    expect(validateField('gender', 'X')).not.toBeNull();
  });

  // Age
  it('passes age 0', ()  => { expect(validateField('age', 0)).toBeNull(); });
  it('passes age 120', () => { expect(validateField('age', 120)).toBeNull(); });
  it('fails age -1',  ()  => { expect(validateField('age', -1)).not.toBeNull(); });
  it('fails age 121', ()  => { expect(validateField('age', 121)).not.toBeNull(); });

  // SBP
  it('passes sbp 50',  () => { expect(validateField('sbp', 50)).toBeNull(); });
  it('passes sbp 300', () => { expect(validateField('sbp', 300)).toBeNull(); });
  it('fails sbp 49',   () => { expect(validateField('sbp', 49)).not.toBeNull(); });
  it('fails sbp 301',  () => { expect(validateField('sbp', 301)).not.toBeNull(); });

  // DBP
  it('passes dbp 30',  () => { expect(validateField('dbp', 30)).toBeNull(); });
  it('passes dbp 200', () => { expect(validateField('dbp', 200)).toBeNull(); });
  it('fails dbp 29',   () => { expect(validateField('dbp', 29)).not.toBeNull(); });
  it('fails dbp 201',  () => { expect(validateField('dbp', 201)).not.toBeNull(); });

  // HR
  it('passes hr 20',  () => { expect(validateField('hr', 20)).toBeNull(); });
  it('passes hr 250', () => { expect(validateField('hr', 250)).toBeNull(); });
  it('fails hr 19',   () => { expect(validateField('hr', 19)).not.toBeNull(); });
  it('fails hr 251',  () => { expect(validateField('hr', 251)).not.toBeNull(); });

  // SpO2
  it('passes spo2 50',  () => { expect(validateField('spo2', 50)).toBeNull(); });
  it('passes spo2 100', () => { expect(validateField('spo2', 100)).toBeNull(); });
  it('fails spo2 49',   () => { expect(validateField('spo2', 49)).not.toBeNull(); });
  it('fails spo2 101',  () => { expect(validateField('spo2', 101)).not.toBeNull(); });

  // Temp
  it('passes temp 30', () => { expect(validateField('temp', 30)).toBeNull(); });
  it('passes temp 45', () => { expect(validateField('temp', 45)).toBeNull(); });
  it('fails temp 29',  () => { expect(validateField('temp', 29)).not.toBeNull(); });
  it('fails temp 46',  () => { expect(validateField('temp', 46)).not.toBeNull(); });

  // RR
  it('passes rr 4',  () => { expect(validateField('rr', 4)).toBeNull(); });
  it('passes rr 60', () => { expect(validateField('rr', 60)).toBeNull(); });
  it('fails rr 3',   () => { expect(validateField('rr', 3)).not.toBeNull(); });
  it('fails rr 61',  () => { expect(validateField('rr', 61)).not.toBeNull(); });
});

// ---------------------------------------------------------------------------
// validateForm — full form tests
// ---------------------------------------------------------------------------
describe('validateForm', () => {
  it('valid form passes with no errors', () => {
    const { valid, errors } = validateForm(VALID);
    expect(valid).toBe(true);
    expect(Object.keys(errors)).toHaveLength(0);
  });

  it('fails when sbp equals dbp (cross-field rule)', () => {
    const { valid, errors } = validateForm({ ...VALID, sbp: 80, dbp: 80 });
    expect(valid).toBe(false);
    expect(errors.sbp).toBeTruthy();
  });

  it('fails when sbp is less than dbp', () => {
    const { valid, errors } = validateForm({ ...VALID, sbp: 70, dbp: 80 });
    expect(valid).toBe(false);
    expect(errors.sbp).toBeTruthy();
  });

  it('reports missing name', () => {
    const { valid, errors } = validateForm({ ...VALID, name: '' });
    expect(valid).toBe(false);
    expect(errors.name).toBeTruthy();
  });

  it('reports out-of-range spo2', () => {
    const { valid, errors } = validateForm({ ...VALID, spo2: 49 });
    expect(valid).toBe(false);
    expect(errors.spo2).toBeTruthy();
  });

  it('reports out-of-range rr', () => {
    const { valid, errors } = validateForm({ ...VALID, rr: 3 });
    expect(valid).toBe(false);
    expect(errors.rr).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// softWarning — danger-but-valid value warnings
// ---------------------------------------------------------------------------
describe('softWarning', () => {
  it('flags SpO₂ 89 as critically low', () => {
    const w = softWarning('spo2', 89);
    expect(w).toBeTruthy();
    expect(w.toLowerCase()).toContain('critically');
  });

  it('does NOT warn for SpO₂ 97 (normal)', () => {
    expect(softWarning('spo2', 97)).toBeNull();
  });

  it('flags HR 141 as very high', () => {
    const w = softWarning('hr', 141);
    expect(w).toBeTruthy();
    expect(w.toLowerCase()).toContain('high');
  });

  it('does NOT warn for HR 80 (normal)', () => {
    expect(softWarning('hr', 80)).toBeNull();
  });

  it('flags SBP 85 as hypotensive', () => {
    const w = softWarning('sbp', 85);
    expect(w).toBeTruthy();
  });

  it('flags temp 39.5 as high fever', () => {
    expect(softWarning('temp', 39.5)).toBeTruthy();
  });

  it('returns null for unknown field', () => {
    expect(softWarning('gender', 'M')).toBeNull();
  });
});
