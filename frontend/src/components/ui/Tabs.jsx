/**
 * Tabs — simple controlled tab bar.
 * Usage:
 *   <Tabs tabs={[{key, label, hidden?}]} active={key} onChange={setKey} />
 */
export default function Tabs({ tabs, active, onChange }) {
  return (
    <div className="flex gap-1 border-b border-gray-200 mb-5 overflow-x-auto">
      {tabs.filter((t) => !t.hidden).map((tab) => (
        <button
          key={tab.key}
          onClick={() => onChange(tab.key)}
          className={`px-4 py-2 text-sm font-medium whitespace-nowrap transition-colors border-b-2 -mb-px ${
            active === tab.key
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
