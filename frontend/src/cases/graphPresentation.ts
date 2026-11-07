import type { Graph } from './graphController';
type Node = Graph['nodes'][number];
const values = (value: unknown): string[] => Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : [];
export const isVisualCandidate = (node: Node) => node.kind === 'visual_candidate' || node.kind === 'visual.detected' ||
  /:frame-\d+:(?:person|vehicle)-\d+$/.test(String(node.properties?.candidate_key ?? ''));
const sourceFile = (node: Node) => typeof node.properties?.filename === 'string' || ['evidence', 'camera', 'document'].includes(node.kind);

const cache = new WeakMap<Graph, Graph>();

/** A view only: IDs remain real source IDs; no stored identity or edge is changed. */
export function compactGraph(graph: Graph): Graph {
  const cached = cache.get(graph); if (cached) return cached;
  const groups = new Map<string, Node[]>();
  for (const node of graph.nodes) {
    if (sourceFile(node) || isVisualCandidate(node) || node.kind === 'date' || ['network.activity','gps.location','transaction.record','mobile.activity'].includes(node.kind) || Array.isArray(node.properties?.entity_ids)) continue;
    if (['UTC', 'GMT', 'IP'].includes(node.label) || /\.(?:txt|csv|png|jpg|mp4|pdf)$/i.test(node.label)) continue;
    const coordinate = node.properties?.latitude !== undefined && node.properties?.longitude !== undefined ?
      `coordinates:${node.properties.latitude},${node.properties.longitude}` : undefined;
    const key = coordinate ?? (typeof node.properties?.candidate_key === 'string' ? node.properties.candidate_key : `node:${node.id}`);
    const members = groups.get(key) ?? []; members.push(node); groups.set(key, members);
  }
  const remap = new Map<string, string>();
  const nodes = [...groups.values()].map(members => {
    members.sort((a, b) => a.id.localeCompare(b.id)); const first = members[0]!;
    members.forEach(member => remap.set(member.id, first.id));
    return { ...first, evidence_ids: [...new Set(members.flatMap(member => member.evidence_ids))].sort(),
      properties: { ...first.properties, source_node_ids: members.map(member => member.id),
        observation_ids: [...new Set(members.flatMap(member => values(member.properties?.observation_ids)))].sort() } };
  });
  const edges = graph.edges.filter(edge => edge.kind !== 'shared_identifier' && remap.has(edge.from_id) && remap.has(edge.to_id))
    .map(edge => ({ ...edge, from_id: remap.get(edge.from_id)!, to_id: remap.get(edge.to_id)! }))
    .filter(edge => edge.from_id !== edge.to_id);
  const result = { ...graph, nodes, edges }; cache.set(graph, result); return result;
}
