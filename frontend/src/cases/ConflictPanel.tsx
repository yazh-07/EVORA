import { EvidenceLinks, MissingInformation, SourceObservations } from './detectorPanelShared';
import type { DetectorPanelProps } from './detectorPanelShared';

export function ConflictPanel({ finding, citations, inspectEvidence }: DetectorPanelProps) {
  return <section className="detector-panel" aria-label="Conflict analysis">
    <h4>Conflicting evidence, timestamps or locations</h4>
    {finding?.kind === 'conflict' ? <>
      <p>{finding.summary}</p>
      <div className="detector-comparison">
        <div><h4>Evidence involved in conflict</h4><EvidenceLinks ids={finding.evidence_ids} inspectEvidence={inspectEvidence} /></div>
        <div><h4>Contradicting evidence</h4><EvidenceLinks ids={finding.contradicting_evidence_ids ?? []} inspectEvidence={inspectEvidence} /></div>
      </div>
      <SourceObservations finding={finding} citations={citations} inspectEvidence={inspectEvidence} />
      <MissingInformation finding={finding} />
    </> : <p>No conflict finding selected.</p>}
  </section>;
}
