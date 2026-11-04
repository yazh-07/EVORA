import { EvidenceLinks, SourceObservations } from './detectorPanelShared';
import type { DetectorPanelProps } from './detectorPanelShared';

export function ClusterPanel({ finding, citations, inspectEvidence }: DetectorPanelProps) {
  return <section className="detector-panel" aria-label="Cluster analysis">
    <h4>Connected evidence and candidate entities</h4>
    {finding?.kind === 'cluster' ? <>
      <p>{finding.summary}</p><h4>Evidence in this group</h4>
      <EvidenceLinks ids={finding.evidence_ids} inspectEvidence={inspectEvidence} />
      <h4>Entity IDs in this group</h4>
      {finding.entity_ids?.length ? <ul>{finding.entity_ids.map(id => <li key={id} className="identifier">{id}</li>)}</ul> :
        <p>No entity IDs provided.</p>}
      <p>Connected candidates require verification; group membership does not establish identity or guilt.</p>
      <SourceObservations finding={finding} citations={citations} inspectEvidence={inspectEvidence} />
    </> : <p>No cluster finding selected.</p>}
  </section>;
}
