import type { components } from '../api/schema';
import './DetectorPanels.css';

export type Finding = components['schemas']['Finding'];
export type Observation = components['schemas']['Observation'];
export type DetectorPanelProps = {
  finding?: Finding | null;
  citations?: Observation[];
  inspectEvidence?: (id: string) => void;
};

export function EvidenceLinks({ ids, inspectEvidence }: { ids: string[]; inspectEvidence?: (id: string) => void }) {
  return ids.length ? <ul className="detector-evidence-links">{ids.map(id => <li key={id}>
    {inspectEvidence ? <button type="button" className="identifier" aria-label={`Inspect source evidence ${id}`}
      onClick={() => inspectEvidence(id)}>{id}</button> : <span className="identifier">{id}</span>}
  </li>)}</ul> : <p>No evidence IDs provided.</p>;
}

export function MissingInformation({ finding }: { finding: Finding }) {
  return <><h4>Missing information</h4>{finding.missing_information?.length ?
    <ul>{finding.missing_information.map((text, index) => <li key={index}>{text}</li>)}</ul> :
    <p>No additional missing information reported. Uncertainty remains unassessed.</p>}</>;
}

/** Only observations explicitly cited by this finding may appear in a detector view. */
export function SourceObservations({ finding, citations = [], inspectEvidence }: DetectorPanelProps & { finding: Finding }) {
  const sources = citations.filter(item => finding.observation_ids.includes(item.id) && item.case_id === finding.case_id &&
    finding.evidence_ids.includes(item.evidence_id));
  return <>
    <h4>Source observations and locators</h4>
    {sources.length ? <div className="detector-table" role="region" aria-label="Detector source observations" tabIndex={0}>
      <table><caption>Cited values, timestamps and locations</caption><thead><tr>
        {['Evidence', 'Observation / locator', 'Kind', 'Raw value', 'Normalized value / location', 'Time (raw)', 'Time (UTC)'].map(label => <th key={label} scope="col">{label}</th>)}
      </tr></thead><tbody>{sources.map(item => <tr key={item.id}>
        <td><EvidenceLinks ids={[item.evidence_id]} inspectEvidence={inspectEvidence} /></td>
        <td className="identifier">{item.id}<br />{item.source_locator}</td><td>{item.kind ?? 'Not provided'}</td>
        <td>{item.raw_value ?? 'Not provided'}</td><td>{item.normalized_value ?? 'Not provided'}</td>
        <td>{item.observed_at_raw ?? 'Not provided'}</td><td>{item.observed_at_utc ?? 'Not provided'}</td>
      </tr>)}</tbody></table>
    </div> : <>
      <p>Inspect finding sources to resolve frozen observation values and locators.</p>
      {finding.observation_ids.length ? <ul>{finding.observation_ids.map(id => <li key={id} className="identifier">{id}</li>)}</ul> :
        <p>No source observation IDs provided.</p>}
    </>}
  </>;
}
