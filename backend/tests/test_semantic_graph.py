"""Relations require explicit roles and coherent source rows."""
import unittest
from uuid import uuid4

from backend.graph_nodes import build_graph_nodes
from backend.graph_links import derive_semantic_links
from backend.parsers.messages_csv import parse_messages_csv
from backend.parsers.message_entities import project_message_entities
from backend.parsers.transactions_csv import parse_transactions_csv
from backend.parsers.transaction_events import project_transaction_records
from backend.parsers.gps_csv import parse_gps_csv
from backend.parsers.normalization import normalize_observations
from backend.parsers.candidate_entities import project_candidate_entities


class SemanticGraphTests(unittest.TestCase):
    def setUp(self):
        self.case, self.evidence, self.run, self.analysis = [uuid4() for _ in range(4)]
        self.context = dict(case_id=self.case, evidence_id=self.evidence, processing_run_id=self.run)

    def graph(self, projection, kind):
        evidence = [dict(id=str(self.evidence), case_id=str(self.case), kind=kind, filename='source')]
        entities = [x.to_wire() for x in projection.entities]
        observations = [x.observation.to_wire() for x in projection.observations]
        nodes = build_graph_nodes(str(self.case), evidence, entities, [], observations)
        edges = derive_semantic_links(str(self.case), str(self.analysis), evidence, entities, observations)
        node_ids = {node.id for node in nodes}
        for edge in edges:
            self.assertIn(edge.from_id, node_ids); self.assertIn(edge.to_id, node_ids)
            self.assertTrue(edge.observation_ids)
        return nodes, edges

    def test_explicit_message_recipient_communicates_but_body_comention_does_not(self):
        base = b'message_id,timestamp,sender,body'
        row = b'\nm1,2026-01-01T00:00:00Z,D-1,D-3 was mentioned'
        legacy = project_message_entities(parse_messages_csv(base + row + b'\n', **self.context), case_id=self.case)
        self.assertEqual(self.graph(legacy, 'message')[1], [])
        projection = project_message_entities(parse_messages_csv(
            base + b',recipient' + row + b',D-2\n', **self.context), case_id=self.case)
        nodes, edges = self.graph(projection, 'message')
        self.assertEqual([e.kind for e in edges], ['communicated_with'])
        labels = {n.id: n.label for n in nodes}
        self.assertEqual((labels[edges[0].from_id], labels[edges[0].to_id]), ('D-1', 'D-2'))

    def test_transfer_preserves_direction_and_never_infers_counterparty(self):
        base = b'timestamp,account_id,amount,currency'
        row = b'\n2026-01-01T00:00:00Z,A-1,50.00,USD'
        old = project_transaction_records(parse_transactions_csv(base+row+b'\n', **self.context), case_id=self.case)
        self.assertEqual(self.graph(old, 'transaction')[1], [])
        projection = project_transaction_records(parse_transactions_csv(
            base+b',recipient_account_id'+row+b',A-2\n', **self.context), case_id=self.case)
        nodes, edges = self.graph(projection, 'transaction')
        self.assertEqual([e.kind for e in edges], ['transferred_to'])
        labels = {n.id: n.label for n in nodes}
        self.assertEqual((labels[edges[0].from_id], labels[edges[0].to_id]), ('A-1', 'A-2'))

    def test_gps_location_is_backed_by_both_coordinates_and_device_in_same_row(self):
        projection = project_candidate_entities(normalize_observations(parse_gps_csv(
            b'timestamp,device_id,latitude,longitude\n2026-01-01T00:00:00Z,D-1,12.5,77.2\n',
            **self.context)), case_id=self.case)
        nodes, edges = self.graph(projection, 'gps')
        self.assertEqual([e.kind for e in edges], ['located_at'])
        location = next(node for node in nodes if node.kind == 'location')
        self.assertEqual(location.properties['latitude'], '12.5')
        self.assertEqual(edges[0].to_id, location.id)
        self.assertEqual(len(edges[0].observation_ids), 3)
        # Source joins remain strict even for standalone graph derivation.
        with self.assertRaises(ValueError):
            derive_semantic_links(str(uuid4()), str(self.analysis), [], [],
                                 [x.observation.to_wire() for x in projection.observations])
