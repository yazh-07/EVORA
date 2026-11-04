import { EvidenceLinks, MissingInformation, SourceObservations } from './detectorPanelShared';
import type { DetectorPanelProps } from './detectorPanelShared';

export function HypothesisPanel({ finding, citations, inspectEvidence }: DetectorPanelProps) {
  return <section className="detector-panel" aria-label="Hypothesis analysis">
    <h4>Alternative hypothesis</h4>
    {finding?.kind === 'hypothesis' ? <>
      <p>{finding.summary}</p>
      <p>Hypotheses are alternatives for investigation and require human verification.</p>
      <div className="detector-comparison">
        <div><h4>Supporting evidence</h4><EvidenceLinks ids={finding.evidence_ids} inspectEvidence={inspectEvidence} /></div>
        <div><h4>Contradicting evidence</h4><EvidenceLinks ids={finding.contradicting_evidence_ids ?? []} inspectEvidence={inspectEvidence} /></div>
      </div>
      <MissingInformation finding={finding} />
      <SourceObservations finding={finding} citations={citations} inspectEvidence={inspectEvidence} />
    </> : <p>No hypothesis finding selected.</p>}
  </section>;
}
