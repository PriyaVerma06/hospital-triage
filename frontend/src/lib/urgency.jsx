/**
 * Urgency level metadata for triage colour-coding.
 * Single source of truth used across badges, cards, and queue views.
 */

/** @type {Record<number, {label: string, color: string, bg: string, text: string, border: string}>} */
const LEVELS = {
  1: { label: 'Immediate',   color: 'red',    bg: 'bg-red-600',    text: 'text-white',      border: 'border-red-600' },
  2: { label: 'Emergent',    color: 'orange',  bg: 'bg-orange-500', text: 'text-white',      border: 'border-orange-500' },
  3: { label: 'Urgent',      color: 'yellow',  bg: 'bg-yellow-400', text: 'text-yellow-900', border: 'border-yellow-400' },
  4: { label: 'Less Urgent', color: 'green',   bg: 'bg-green-500',  text: 'text-white',      border: 'border-green-500' },
  5: { label: 'Routine',     color: 'green',   bg: 'bg-green-700',  text: 'text-white',      border: 'border-green-700' },
};

const UNKNOWN = { label: 'Unknown', color: 'gray', bg: 'bg-gray-400', text: 'text-white', border: 'border-gray-400' };

/**
 * Returns display metadata for an urgency level (1-5).
 * @param {number|null|undefined} level
 */
export function levelInfo(level) {
  return LEVELS[level] ?? UNKNOWN;
}

/**
 * Reusable badge component showing triage level + label.
 * @param {{ level: number, size?: 'sm'|'md'|'lg' }} props
 */
export function LevelBadge({ level, size = 'md' }) {
  const info = levelInfo(level);
  const sizeClass = {
    sm: 'text-xs px-2 py-0.5',
    md: 'text-sm px-3 py-1',
    lg: 'text-base px-4 py-1.5 font-bold',
  }[size] ?? 'text-sm px-3 py-1';

  return (
    <span className={`inline-flex items-center gap-1 rounded-full font-semibold ${info.bg} ${info.text} ${sizeClass}`}>
      {level != null && <span>L{level}</span>}
      <span>{info.label}</span>
    </span>
  );
}
