import type { components } from '../api/schema';
type Finding = components['schemas']['Finding'];
const key = (finding: Finding) => JSON.stringify([(finding.entity_ids ?? []).slice().sort(), finding.evidence_ids.slice().sort(), finding.observation_ids.slice().sort(), (finding.contradicting_evidence_ids ?? []).slice().sort()]);
const identifier = (finding: Finding) => finding.kind === 'relationship' &&
  (finding.rule.startsWith('candidate_link_shared_identifier:') || finding.rule.startsWith('candidate_identifier_group:'));
/** Fold alternate detector views only when all subjects and citations match exactly. */
export function groupFindingViews(findings: Finding[]) {
  const seeds = new Map(findings.filter(f => identifier(f) && f.entity_ids?.length).map(f => [key(f), f]));
  const related = new Map<string, Finding[]>();
  for (const finding of findings) {
    const primary = seeds.get(key(finding));
    if (primary && primary.id !== finding.id && ['cluster', 'corroboration'].includes(finding.kind)) {
      const group = related.get(primary.id) ?? []; group.push(finding); related.set(primary.id, group);
    }
  }
  const folded = new Set([...related.values()].flat().map(f => f.id));
  return findings.filter(f => !folded.has(f.id)).map(primary => ({ primary, related: related.get(primary.id) ?? [] }));
}
