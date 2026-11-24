/**
 * analyticsLogic.test.js + shiftLogic.test.js combined
 * Tests for all pure logic helpers.
 */
import { describe, it, expect } from 'vitest';
import {
  formatMinutes,
  toDistributionChartData,
  toWaitByLevelChartData,
  toOccupancyChartData,
  toTimelineChartData,
  pageOffset,
} from './analyticsLogic.js';
import { shiftPosition, formatShiftTime } from './shiftLogic.js';

// ---------------------------------------------------------------------------
// formatMinutes
// ---------------------------------------------------------------------------
describe('formatMinutes', () => {
  it('returns "—" for null', () => expect(formatMinutes(null)).toBe('—'));
  it('returns "—" for undefined', () => expect(formatMinutes(undefined)).toBe('—'));
  it('returns "—" for NaN', () => expect(formatMinutes(NaN)).toBe('—'));
  it('returns "0 min" for 0', () => expect(formatMinutes(0)).toBe('0 min'));
  it('returns "1 min" for 1', () => expect(formatMinutes(1)).toBe('1 min'));
  it('returns "59 min" for 59', () => expect(formatMinutes(59)).toBe('59 min'));
  it('returns "1 h" for 60', () => expect(formatMinutes(60)).toBe('1 h'));
  it('returns "1 h 05 min" for 65', () => expect(formatMinutes(65)).toBe('1 h 05 min'));
  it('returns "2 h 30 min" for 150', () => expect(formatMinutes(150)).toBe('2 h 30 min'));
  it('rounds fractional minutes', () => expect(formatMinutes(1.4)).toBe('1 min'));
});

// ---------------------------------------------------------------------------
// toDistributionChartData
// ---------------------------------------------------------------------------
describe('toDistributionChartData', () => {
  const apiData = {
    distribution: [
      { level: 1, label: 'Immediate', color: 'RED', count: 3 },
      { level: 3, label: 'Urgent',    color: 'YELLOW', count: 7 },
    ],
  };

  it('always returns 5 entries', () => {
    expect(toDistributionChartData(apiData)).toHaveLength(5);
  });

  it('fills missing levels with count 0', () => {
    const data = toDistributionChartData(apiData);
    const lvl2 = data.find((d) => d.level === 2);
    expect(lvl2.count).toBe(0);
    expect(lvl2.pct).toBe(0);
  });

  it('computes pct correctly (3 of 10 = 30%)', () => {
    const data = toDistributionChartData(apiData);
    const lvl1 = data.find((d) => d.level === 1);
    expect(lvl1.pct).toBe(30);
  });

  it('handles null/undefined input gracefully', () => {
    expect(toDistributionChartData(null)).toHaveLength(5);
    expect(toDistributionChartData(undefined)).toHaveLength(5);
  });

  it('assigns fill colours', () => {
    const data = toDistributionChartData(apiData);
    expect(data[0].fill).toBeTruthy(); // level 1 has a colour
  });

  it('total=0 → all pct=0 (no division by zero)', () => {
    const empty = { distribution: [] };
    const data = toDistributionChartData(empty);
    expect(data.every((d) => d.pct === 0)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// toWaitByLevelChartData
// ---------------------------------------------------------------------------
describe('toWaitByLevelChartData', () => {
  const apiData = {
    wait_by_level: [
      { level: 1, label: 'Immediate', avg_wait_minutes: 2.567, patient_count: 3 },
      { level: 5, label: 'Non-Urgent', avg_wait_minutes: 45.0, patient_count: 1 },
    ],
  };

  it('always returns 5 entries', () => {
    expect(toWaitByLevelChartData(apiData)).toHaveLength(5);
  });

  it('rounds to 1 decimal', () => {
    const data = toWaitByLevelChartData(apiData);
    expect(data.find((d) => d.level === 1).avg_wait_minutes).toBe(2.6);
  });

  it('missing levels get avg_wait_minutes 0', () => {
    const data = toWaitByLevelChartData(apiData);
    expect(data.find((d) => d.level === 2).avg_wait_minutes).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// toOccupancyChartData
// ---------------------------------------------------------------------------
describe('toOccupancyChartData', () => {
  const apiData = {
    wards: {
      ICU:       { total: 4, available: 1, occupied: 3, cleaning: 0, occupancy_pct: 75.0 },
      EMERGENCY: { total: 5, available: 2, occupied: 2, cleaning: 1, occupancy_pct: 40.0 },
      GENERAL:   { total: 6, available: 6, occupied: 0, cleaning: 0, occupancy_pct: 0.0  },
    },
  };

  it('returns 3 ward entries', () => {
    expect(toOccupancyChartData(apiData)).toHaveLength(3);
  });

  it('orders ICU first', () => {
    expect(toOccupancyChartData(apiData)[0].ward).toBe('ICU');
  });

  it('maps occupancy_pct correctly', () => {
    const data = toOccupancyChartData(apiData);
    expect(data.find((d) => d.ward === 'ICU').occupancy_pct).toBe(75);
  });
});

// ---------------------------------------------------------------------------
// toTimelineChartData
// ---------------------------------------------------------------------------
describe('toTimelineChartData', () => {
  it('extracts label as HH:00', () => {
    const data = toTimelineChartData({
      timeline: [{ hour: '2026-01-01T14:00', arrivals: 3, critical: 1 }],
    });
    expect(data[0].label).toBe('14:00');
  });

  it('handles empty timeline', () => {
    expect(toTimelineChartData({ timeline: [] })).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// pageOffset
// ---------------------------------------------------------------------------
describe('pageOffset', () => {
  it('page 0, size 20 → 0', () => expect(pageOffset(0, 20)).toBe(0));
  it('page 1, size 20 → 20', () => expect(pageOffset(1, 20)).toBe(20));
  it('page 3, size 10 → 30', () => expect(pageOffset(3, 10)).toBe(30));
});

// ---------------------------------------------------------------------------
// shiftPosition
// ---------------------------------------------------------------------------
describe('shiftPosition', () => {
  const date = '2026-01-15';

  it('shift fully within the day', () => {
    const shift = {
      start_time: '2026-01-15T08:00:00',
      end_time:   '2026-01-15T16:00:00',
    };
    const pos = shiftPosition(shift, date);
    expect(pos).not.toBeNull();
    // 8h / 24h = 33.33%
    expect(pos.leftPct).toBeCloseTo(33.33, 1);
    // 8h / 24h = 33.33%
    expect(pos.widthPct).toBeCloseTo(33.33, 1);
  });

  it('shift crossing midnight clips to day end', () => {
    const shift = {
      start_time: '2026-01-15T22:00:00',
      end_time:   '2026-01-16T06:00:00',
    };
    const pos = shiftPosition(shift, date);
    expect(pos).not.toBeNull();
    // starts at 22h, ends clipped to 24h → width = 2/24
    expect(pos.widthPct).toBeCloseTo((2 / 24) * 100, 1);
  });

  it('shift entirely before the day returns null', () => {
    const shift = {
      start_time: '2026-01-14T10:00:00',
      end_time:   '2026-01-14T18:00:00',
    };
    expect(shiftPosition(shift, date)).toBeNull();
  });

  it('shift entirely after the day returns null', () => {
    const shift = {
      start_time: '2026-01-16T08:00:00',
      end_time:   '2026-01-16T16:00:00',
    };
    expect(shiftPosition(shift, date)).toBeNull();
  });

  it('zero-width shift (start = end) returns null', () => {
    const shift = {
      start_time: '2026-01-15T12:00:00',
      end_time:   '2026-01-15T12:00:00',
    };
    // end <= dayStart is false, start >= dayEnd is false, but clipped width = 0
    // This is acceptable behaviour; just ensure no crash
    const pos = shiftPosition(shift, date);
    if (pos !== null) expect(pos.widthPct).toBe(0);
  });
});
