/**
 * dashboardLogic.test.js — Vitest unit tests for pure dashboard logic.
 * Tests: escalation detection, wait-time formatting, critical wait rule,
 * bed grouping, queue filter/search.
 */
import { describe, it, expect } from 'vitest';
import {
  detectEscalations,
  buildLevelMap,
  formatWaitTime,
  isCriticalWaitTooLong,
  groupBedsByWard,
  filterQueue,
} from './dashboardLogic.js';

// ---------------------------------------------------------------------------
// detectEscalations
// ---------------------------------------------------------------------------
describe('detectEscalations', () => {
  it('detects level 3 → 1 as escalated', () => {
    const prev = { 10: 3 };
    const next = [{ id: 10, urgency_level: 1 }];
    expect(detectEscalations(prev, next)).toContain(10);
  });

  it('does NOT flag level 1 → 3 (improvement)', () => {
    const prev = { 10: 1 };
    const next = [{ id: 10, urgency_level: 3 }];
    expect(detectEscalations(prev, next)).not.toContain(10);
  });

  it('does NOT flag a brand-new patient (not in prevMap)', () => {
    const prev = {};
    const next = [{ id: 99, urgency_level: 1 }];
    expect(detectEscalations(prev, next)).toHaveLength(0);
  });

  it('does NOT flag same level', () => {
    const prev = { 5: 2 };
    const next = [{ id: 5, urgency_level: 2 }];
    expect(detectEscalations(prev, next)).toHaveLength(0);
  });

  it('detects multiple escalations in one list', () => {
    const prev = { 1: 4, 2: 3, 3: 2 };
    const next = [
      { id: 1, urgency_level: 2 },  // escalated
      { id: 2, urgency_level: 3 },  // same
      { id: 3, urgency_level: 1 },  // escalated
    ];
    const result = detectEscalations(prev, next);
    expect(result).toContain(1);
    expect(result).toContain(3);
    expect(result).not.toContain(2);
  });

  it('ignores patients with null urgency_level', () => {
    const prev = { 7: 3 };
    const next = [{ id: 7, urgency_level: null }];
    expect(detectEscalations(prev, next)).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// buildLevelMap
// ---------------------------------------------------------------------------
describe('buildLevelMap', () => {
  it('maps id → urgency_level', () => {
    const list = [
      { id: 1, urgency_level: 2 },
      { id: 2, urgency_level: 4 },
    ];
    expect(buildLevelMap(list)).toEqual({ 1: 2, 2: 4 });
  });

  it('skips entries with null level', () => {
    const list = [{ id: 1, urgency_level: null }, { id: 2, urgency_level: 3 }];
    const map = buildLevelMap(list);
    expect(map).not.toHaveProperty('1');
    expect(map[2]).toBe(3);
  });
});

// ---------------------------------------------------------------------------
// formatWaitTime
// ---------------------------------------------------------------------------
describe('formatWaitTime', () => {
  it('returns "< 1 min" for 0', () => {
    expect(formatWaitTime(0)).toBe('< 1 min');
  });

  it('returns "< 1 min" for 0.4', () => {
    expect(formatWaitTime(0.4)).toBe('< 1 min');
  });

  it('returns "12 min" for 12', () => {
    expect(formatWaitTime(12)).toBe('12 min');
  });

  it('returns "59 min" for 59', () => {
    expect(formatWaitTime(59)).toBe('59 min');
  });

  it('returns "1h" for 60', () => {
    expect(formatWaitTime(60)).toBe('1h');
  });

  it('returns "1h 30m" for 90', () => {
    expect(formatWaitTime(90)).toBe('1h 30m');
  });

  it('returns "—" for null', () => {
    expect(formatWaitTime(null)).toBe('—');
  });

  it('returns "—" for NaN', () => {
    expect(formatWaitTime(NaN)).toBe('—');
  });
});

// ---------------------------------------------------------------------------
// isCriticalWaitTooLong
// ---------------------------------------------------------------------------
describe('isCriticalWaitTooLong', () => {
  it('returns true for level 1, wait > 5 min', () => {
    expect(isCriticalWaitTooLong({ urgency_level: 1, wait_minutes: 6 })).toBe(true);
  });

  it('returns true for level 2, wait = 5.1 min', () => {
    expect(isCriticalWaitTooLong({ urgency_level: 2, wait_minutes: 5.1 })).toBe(true);
  });

  it('returns false for level 1, wait exactly 5 min', () => {
    expect(isCriticalWaitTooLong({ urgency_level: 1, wait_minutes: 5 })).toBe(false);
  });

  it('returns false for level 3 even with long wait', () => {
    expect(isCriticalWaitTooLong({ urgency_level: 3, wait_minutes: 60 })).toBe(false);
  });

  it('returns false for level 4', () => {
    expect(isCriticalWaitTooLong({ urgency_level: 4, wait_minutes: 10 })).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// groupBedsByWard
// ---------------------------------------------------------------------------
describe('groupBedsByWard', () => {
  const beds = [
    { id: 'ICU-1', ward: 'ICU', status: 'AVAILABLE', has_ventilator: true },
    { id: 'ICU-2', ward: 'ICU', status: 'OCCUPIED', has_ventilator: false },
    { id: 'EM-1', ward: 'EMERGENCY', status: 'AVAILABLE', has_ventilator: false },
    { id: 'GEN-1', ward: 'GENERAL', status: 'AVAILABLE', has_ventilator: false },
  ];

  it('groups ICU beds together', () => {
    const groups = groupBedsByWard(beds);
    expect(groups['ICU']).toHaveLength(2);
  });

  it('creates separate groups for each ward', () => {
    const groups = groupBedsByWard(beds);
    expect(Object.keys(groups).sort()).toEqual(['EMERGENCY', 'GENERAL', 'ICU']);
  });

  it('returns empty object for empty array', () => {
    expect(groupBedsByWard([])).toEqual({});
  });
});

// ---------------------------------------------------------------------------
// filterQueue
// ---------------------------------------------------------------------------
describe('filterQueue', () => {
  const queue = [
    { id: 1, name: 'Alice Smith', color: 'RED', urgency_level: 1, wait_minutes: 3 },
    { id: 2, name: 'Bob Jones', color: 'YELLOW', urgency_level: 3, wait_minutes: 8 },
    { id: 3, name: 'Carol Red', color: 'GREEN', urgency_level: 4, wait_minutes: 1 },
    { id: 4, name: 'Dave', color: 'RED', urgency_level: 2, wait_minutes: 2 },
  ];

  it('returns all when filter is ALL', () => {
    expect(filterQueue(queue, 'ALL', '')).toHaveLength(4);
  });

  it('filters by color RED', () => {
    const result = filterQueue(queue, 'RED', '');
    expect(result).toHaveLength(2);
    expect(result.every((p) => p.color === 'RED')).toBe(true);
  });

  it('filters by color YELLOW', () => {
    const result = filterQueue(queue, 'YELLOW', '');
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe(2);
  });

  it('filters by name search (case-insensitive)', () => {
    const result = filterQueue(queue, 'ALL', 'alice');
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe(1);
  });

  it('combines color and name search', () => {
    // RED + "carol" → no match (Carol is GREEN)
    expect(filterQueue(queue, 'RED', 'carol')).toHaveLength(0);
    // RED + "alice" → 1 match
    expect(filterQueue(queue, 'RED', 'alice')).toHaveLength(1);
  });

  it('returns empty for no matches', () => {
    expect(filterQueue(queue, 'ALL', 'xyz')).toHaveLength(0);
  });
});
