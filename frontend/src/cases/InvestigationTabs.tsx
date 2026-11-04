import { useRef } from 'react';

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
  { id: 'evidence', label: 'Evidence & Intake', path: 'M3 7h7l2 2h9v11H3V7Zm0 0V4h7l2 3' },
  { id: 'triage', label: 'Triage & Priority', path: 'M4 5h16M4 12h11M4 19h6M18 10v10m-3-3 3 3 3-3' },
  { id: 'graph', label: 'Knowledge Graph', path: 'M9 6a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm12 0a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm-6 13a3 3 0 1 1-6 0 3 3 0 0 1 6 0ZM9 6h6M7 9l4 7m6-7-4 7' },
  { id: 'entities-events', label: 'Entities & Events', path: 'M8 7a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm-6 13v-3a3 3 0 0 1 6 0v3M12 5h9M12 12h9M12 19h9' },
  { id: 'findings', label: 'Findings & Citations', path: 'M16 10a6 6 0 1 1-12 0 6 6 0 0 1 12 0Zm-2 4 6 6M7 8h6M7 11h4' },
  { id: 'questions', label: 'Questions & Answers', path: 'M4 4h16v13H9l-5 4V4Zm5 4a3 3 0 0 1 6 0c0 2-3 2-3 4m0 2v1' },
  { id: 'overview', label: 'Case Overview', path: 'M4 3v18h17M8 17v-5m5 5V8m5 9V4' },
] as const;
export type InvestigationTab = typeof tabs[number]['id'];

export function InvestigationTabs({ activeTab, onSelect }: { activeTab: InvestigationTab; onSelect: (tab: InvestigationTab) => void }) {
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  return <div className="investigation-tabs" role="tablist" aria-label="Investigation navigation">
    {tabs.map((tab, index) => <button key={tab.id} ref={element => { buttons.current[index] = element; }}
      type="button" role="tab" id={`tab-${tab.id}`} aria-controls={`panel-${tab.id}`} aria-selected={activeTab === tab.id}
      tabIndex={activeTab === tab.id ? 0 : -1} onClick={() => onSelect(tab.id)} onKeyDown={event => {
        const next = event.key === 'ArrowRight' ? (index + 1) % tabs.length : event.key === 'ArrowLeft' ? (index + tabs.length - 1) % tabs.length :
          event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : null;
        if (next !== null) { event.preventDefault(); onSelect(tabs[next]!.id); buttons.current[next]?.focus(); }
      }}>
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={tab.path} /></svg>
      {tab.label}
    </button>)}
  </div>;
}
