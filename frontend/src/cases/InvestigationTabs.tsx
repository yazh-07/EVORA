import { useEffect, useRef, useState } from 'react';

export const findingKinds = ['all', 'relationship', 'conflict', 'gap', 'cluster', 'anomaly', 'hypothesis'] as const;
export type FindingKindFilterValue = typeof findingKinds[number];

/** Results remain paginated by the API; this filter never implies a case-wide count. */
export function FindingKindFilter({ value, onSelect }: {
  value: FindingKindFilterValue; onSelect?: (kind: FindingKindFilterValue) => void;
}) {
  return <div className="finding-kind-filter">
    <label>Finding kind <select value={value} disabled={!onSelect} aria-describedby="finding-filter-scope"
      onChange={event => {
        const kind = event.currentTarget.value;
        if (findingKinds.some(option => option === kind)) onSelect?.(kind as FindingKindFilterValue);
      }}>
      {findingKinds.map(kind => <option key={kind} value={kind}>{kind === 'all' ? 'All kinds' : kind}</option>)}
    </select></label>
    <span id="finding-filter-scope">Filters the current page. Use Previous and Next to inspect other pages.</span>
  </div>;
}

const tabs = [
  { id: 'overview', label: 'Overview', path: 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z' },
  { id: 'evidence', label: 'Evidence', path: 'M3 7h7l2 2h9v11H3V7Zm0 0V4h7l2 3' },
  { id: 'timeline', label: 'Timeline', path: 'M12 3v18M5 6h7m0 6h7M5 18h7' },
  { id: 'investigation', label: 'Investigation', path: 'M16 10a6 6 0 1 1-12 0 6 6 0 0 1 12 0Zm-2 4 6 6M7 8h6M7 11h4' },
  { id: 'report', label: 'Report', path: 'M5 3h10l4 4v14H5V3Zm10 0v5h4M9 12h6m-6 4h6' },
] as const;
export type InvestigationTab = typeof tabs[number]['id'];

export function InvestigationTabs({ activeTab, onSelect }: { activeTab: InvestigationTab; onSelect: (tab: InvestigationTab) => void }) {
  const [vertical, setVertical] = useState(false);
  useEffect(() => {
    const media = window.matchMedia('(min-width: 851px)');
    const update = () => setVertical(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  return <div className="investigation-tabs" role="tablist" aria-orientation={vertical ? 'vertical' : 'horizontal'} aria-label="Investigation navigation">
    {tabs.map((tab, index) => <button key={tab.id} ref={element => { buttons.current[index] = element; }}
      type="button" role="tab" id={`tab-${tab.id}`} aria-controls={`panel-${tab.id}`} aria-selected={activeTab === tab.id}
      tabIndex={activeTab === tab.id ? 0 : -1} onClick={() => onSelect(tab.id)} onKeyDown={event => {
        const next = (event.key === 'ArrowRight' || event.key === 'ArrowDown') ? (index + 1) % tabs.length : (event.key === 'ArrowLeft' || event.key === 'ArrowUp') ? (index + tabs.length - 1) % tabs.length :
          event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : null;
        if (next !== null) { event.preventDefault(); onSelect(tabs[next]!.id); buttons.current[next]?.focus(); }
      }}>
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={tab.path} /></svg>
      {tab.label}
    </button>)}
  </div>;
}
