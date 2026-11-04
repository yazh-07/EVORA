import { EvidenceLinks, MissingInformation, SourceObservations } from './detectorPanelShared';
import type { DetectorPanelProps } from './detectorPanelShared';

export function GapPanel({ finding, citations, inspectEvidence }: DetectorPanelProps) {
  return <section className="detector-panel" aria-label="Gap analysis">
    <h4>Missing intervals and data gaps</h4>
    <p className="detector-disclaimer">Missing evidence is not proof of non-occurrence.</p>
    {finding?.kind === 'gap' ? <>
      <p>{finding.summary}</p><MissingInformation finding={finding} />
      <h4>Evidence bounding or identifying the gap</h4>
      <EvidenceLinks ids={finding.evidence_ids} inspectEvidence={inspectEvidence} />
      <SourceObservations finding={finding} citations={citations} inspectEvidence={inspectEvidence} />
    </> : <p>No gap finding selected.</p>}
  </section>;
}
