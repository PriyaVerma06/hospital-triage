/**
 * API client for the hospital triage backend.
 * Automatically attaches Bearer token from localStorage.
 * Handles 401 session expiry, 422 validation errors, and other HTTP errors.
 */
import { API_BASE } from '../config.js';

/** Read token stored by AuthContext */
function getToken() {
  return localStorage.getItem('triage_token');
}

/** Clear session on 401 and redirect to login */
function clearSession() {
  localStorage.removeItem('triage_token');
  localStorage.removeItem('triage_user');
  window.location.href = '/login';
}

/**
 * Generic fetch wrapper.
 * @param {string} path       - path relative to API_BASE (e.g. "/patients")
 * @param {RequestInit} opts  - fetch options
 * @returns {Promise<any>}    - parsed JSON response
 */
export async function request(path, opts = {}) {
  const token = getToken();
  const headers = { ...(opts.headers ?? {}) };

  // Attach Bearer token when available
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Don't set Content-Type for FormData (browser sets boundary automatically)
  if (!(opts.body instanceof FormData) && opts.body && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(`${API_BASE}${path}`, { ...opts, headers });

  // Session expired — clear and redirect
  if (res.status === 401) {
    clearSession();
    return;
  }

  // FastAPI 422 Validation Error — convert detail array to field→message map
  if (res.status === 422) {
    const body = await res.json();
    const fieldErrors = {};
    if (Array.isArray(body.detail)) {
      for (const err of body.detail) {
        // loc is e.g. ["body", "sbp"] — take the last element as the field name
        const field = err.loc?.[err.loc.length - 1] ?? 'general';
        fieldErrors[field] = err.msg;
      }
    }
    const error = new Error('Validation failed');
    error.fieldErrors = fieldErrors;
    error.status = 422;
    throw error;
  }

  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      message = body.detail ?? message;
    } catch {
      // non-JSON error body
    }
    const error = new Error(message);
    error.status = res.status;
    throw error;
  }

  // 204 No Content
  if (res.status === 204) return null;

  return res.json();
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

/**
 * Login with OAuth2 form data.
 * Returns { access_token, token_type, user }
 */
export async function login(username, password) {
  const form = new FormData();
  form.append('username', username);
  form.append('password', password);
  return request('/auth/login', { method: 'POST', body: form });
}

/** Validate current token and return the current user object. */
export async function getMe() {
  return request('/auth/me');
}

// ---------------------------------------------------------------------------
// Patients
// ---------------------------------------------------------------------------

/**
 * Submit a new patient intake.
 * @param {object} data - must include all required vitals fields
 */
export async function createPatient(data) {
  return request('/patients', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/** Fetch a single patient by ID. */
export async function getPatient(id) {
  return request(`/patients/${id}`);
}

/**
 * Update vitals for an existing patient.
 * @param {number} id
 * @param {object} vitals - sbp, dbp, hr, spo2, temp, rr
 */
export async function updateVitals(id, vitals) {
  return request(`/patients/${id}/vitals`, {
    method: 'PUT',
    body: JSON.stringify(vitals),
  });
}

/** Fetch the list of patients (with optional status filter). */
export async function getPatients(params = {}) {
  const qs = new URLSearchParams(params).toString();
  return request(`/patients${qs ? '?' + qs : ''}`);
}

/** Fetch the WAITING queue. */
export async function getQueue() {
  return request('/queue');
}

/** Fetch audit log for a patient. */
export async function getPatientAudit(id) {
  return request(`/patients/${id}/audit`);
}

// ---------------------------------------------------------------------------
// Resources
// ---------------------------------------------------------------------------

/** Fetch resource summary (beds, doctors, ventilators). */
export async function getResourcesSummary() {
  return request('/resources/summary');
}

/** Fetch all beds. */
export async function getBeds() {
  return request('/beds');
}

/** Fetch all doctors. */
export async function getDoctors() {
  return request('/doctors');
}

// ---------------------------------------------------------------------------
// Alerts
// ---------------------------------------------------------------------------

/**
 * Fetch alerts. Pass { unacknowledged_only: true } to filter.
 * @param {object} params
 */
export async function getAlerts(params = {}) {
  const qs = new URLSearchParams(params).toString();
  return request(`/alerts${qs ? '?' + qs : ''}`);
}

/**
 * Acknowledge an alert.
 * @param {number} id
 */
export async function acknowledgeAlert(id) {
  return request(`/alerts/${id}/acknowledge`, { method: 'PUT' });
}

// ---------------------------------------------------------------------------
// Discharge
// ---------------------------------------------------------------------------

/**
 * Discharge a patient.
 * @param {number} id
 */
export async function dischargePatient(id) {
  return request(`/patients/${id}/discharge`, { method: 'PUT' });
}

// ---------------------------------------------------------------------------
// Global audit log (ADMIN + DOCTOR)
// ---------------------------------------------------------------------------

/** GET /audit with optional pagination and patient_id filter */
export async function getAuditLog(params = {}) {
  const qs = new URLSearchParams(params).toString();
  return request(`/audit${qs ? '?' + qs : ''}`);
}

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------

export async function getAnalyticsSummary(hours = 24) {
  return request(`/analytics/summary?hours=${hours}`);
}

export async function getTriageDistribution(hours = 24) {
  return request(`/analytics/triage-distribution?hours=${hours}`);
}

export async function getOccupancy() {
  return request('/analytics/occupancy');
}

export async function getWaitByLevel(hours = 24) {
  return request(`/analytics/wait-by-level?hours=${hours}`);
}

export async function getTimeline(hours = 24) {
  return request(`/analytics/timeline?hours=${hours}`);
}

// ---------------------------------------------------------------------------
// Admin — Beds
// ---------------------------------------------------------------------------

export async function adminCreateBed(data) {
  return request('/admin/beds', { method: 'POST', body: JSON.stringify(data) });
}

export async function adminUpdateBed(id, data) {
  return request(`/admin/beds/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}

export async function adminDeleteBed(id) {
  return request(`/admin/beds/${id}`, { method: 'DELETE' });
}

export async function updateBedStatus(id, status) {
  return request(`/beds/${id}/status`, { method: 'PUT', body: JSON.stringify({ status }) });
}

// ---------------------------------------------------------------------------
// Admin — Doctors
// ---------------------------------------------------------------------------

export async function adminCreateDoctor(data) {
  return request('/admin/doctors', { method: 'POST', body: JSON.stringify(data) });
}

export async function adminUpdateDoctor(id, data) {
  return request(`/admin/doctors/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}

export async function adminDeleteDoctor(id) {
  return request(`/admin/doctors/${id}`, { method: 'DELETE' });
}

// ---------------------------------------------------------------------------
// Admin — Shifts
// ---------------------------------------------------------------------------

export async function getShifts(params = {}) {
  const qs = new URLSearchParams(params).toString();
  return request(`/admin/shifts${qs ? '?' + qs : ''}`);
}

export async function adminCreateShift(data) {
  return request('/admin/shifts', { method: 'POST', body: JSON.stringify(data) });
}

export async function adminDeleteShift(id) {
  return request(`/admin/shifts/${id}`, { method: 'DELETE' });
}

export async function applyShifts() {
  return request('/admin/shifts/apply', { method: 'POST' });
}

// ---------------------------------------------------------------------------
// Admin — Logs
// ---------------------------------------------------------------------------

export async function getAdminLogs(limit = 50) {
  return request(`/admin/logs?limit=${limit}`);
}

// ---------------------------------------------------------------------------
// Users
// ---------------------------------------------------------------------------

export async function getUsers() {
  return request('/users');
}

export async function createUser(data) {
  return request('/users', { method: 'POST', body: JSON.stringify(data) });
}

export async function setUserActive(id, is_active) {
  return request(`/users/${id}/active`, { method: 'PUT', body: JSON.stringify({ is_active }) });
}
