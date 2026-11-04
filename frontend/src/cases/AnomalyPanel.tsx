import { EvidenceLinks, MissingInformation, SourceObservations } from './detectorPanelShared';
import type { DetectorPanelProps } from './detectorPanelShared';

export function AnomalyPanel({ finding, citations, inspectEvidence }: DetectorPanelProps) {
  return <section className="detector-panel" aria-label="Anomaly analysis">
    <h4>Abnormal data points</h4>
    <p className="detector-disclaimer">Investigative attention only; abnormal is not proof of guilt.</p>
    {finding?.kind === 'anomaly' ? <>
      <p>{finding.summary}</p><h4>Evidence containing flagged data</h4>
      <EvidenceLinks ids={finding.evidence_ids} inspectEvidence={inspectEvidence} />
      <SourceObservations finding={finding} citations={citations} inspectEvidence={inspectEvidence} />
      <MissingInformation finding={finding} />
    </> : <p>No anomaly finding selected.</p>}
  </section>;
}
