import { EvidenceLinks } from './detectorPanelShared';
import type { Finding, Observation } from './detectorPanelShared';

export function ReliabilityInspector({ evidenceId, observations = [], findings, observationScope, inspectEvidence }: {
  evidenceId?: string;
  observations?: Observation[];
  /** Undefined means findings have not been loaded; an empty array means none in the stated page. */
  findings?: Finding[];
  observationScope?: string;
  inspectEvidence?: (id: string) => void;
}) {
  const sources = observations.filter(item => item.evidence_id === evidenceId);
  const related = findings?.filter(item => item.evidence_ids.includes(evidenceId ?? '') || item.contradicting_evidence_ids?.includes(evidenceId ?? ''));
  const corroborating = related?.filter(item => item.kind === 'corroboration' && item.evidence_ids.includes(evidenceId ?? ''));
  const conflicts = related?.filter(item => item.kind === 'conflict');
  const unknowns = [...new Set(related?.flatMap(item => item.missing_information ?? []))];
  return <section className="detector-panel reliability-inspector" aria-label="Reliability and uncertainty">
    <h4>Source reliability and uncertainty</h4>
    {evidenceId ? <>
      <EvidenceLinks ids={[evidenceId]} inspectEvidence={inspectEvidence} />
      <dl><dt>Source reliability</dt><dd>Unknown — no source reliability assessment is provided by the API.</dd>
        <dt>Extraction confidence</dt><dd>{sources.length ? <ul>{sources.map(item => <li key={item.id}>
          <span className="identifier">{item.id}</span>: {Number.isFinite(item.extraction_confidence) ? item.extraction_confidence.toFixed(2) : 'Not provided'}
        </li>)}</ul> : 'No resolved observations in this view.'}</dd>
        <dt>Corroboration findings</dt><dd>{corroborating ? `${corroborating.length} on the current findings page.` : 'Not loaded in this view.'}</dd>
        <dt>Conflict findings</dt><dd>{conflicts ? `${conflicts.length} on the current findings page.` : 'Not loaded in this view.'}</dd>
      </dl>
      <p>{observationScope ?? 'Observations are limited to the selected finding’s frozen citations.'}</p>
      <p>Extraction confidence and finding confidence are reported scores, not source reliability. Corroboration does not establish independent sources or truth.</p>
      {corroborating?.map(item => <div key={item.id}><p>{item.summary}</p><h4>Evidence cited for corroboration</h4>
        <EvidenceLinks ids={item.evidence_ids} inspectEvidence={inspectEvidence} /></div>)}
      <h4>Uncertainty and missing information</h4>
      {unknowns.length ? <ul>{unknowns.map(text => <li key={text}>{text}</li>)}</ul> : <p>No additional uncertainty assessment is available in this view.</p>}
      <p>Missing evidence is not proof of non-occurrence.</p>
    </> : <p>Select evidence to inspect reliability and uncertainty.</p>}
  </section>;
}
