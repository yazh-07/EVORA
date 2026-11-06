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
from backend.parsers.network_csv import parse_network_csv


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

    def test_network_assigned_ip_retains_each_rows_exact_source_lineage(self):
        projection=project_candidate_entities(normalize_observations(parse_network_csv(
            b'timestamp,device_id,ip_address,event\n2026-01-01T00:00:00Z,D-1,203.0.113.1,connected\n'
            b'2026-01-01T00:00:01Z,D-2,203.0.113.2,connected\n',**self.context)),case_id=self.case)
        nodes,edges=self.graph(projection,'network_log')
        self.assertEqual(len(edges),2)
        labels={node.id:node.label for node in nodes}
        self.assertEqual({(labels[edge.from_id],labels[edge.to_id]) for edge in edges},
            {('D-1','203.0.113.1'),('D-2','203.0.113.2')})
        observations={str(item.observation.id):item.observation for item in projection.observations}
        for edge in edges:
            self.assertEqual(edge.kind,'assigned_ip')
            self.assertEqual(set(edge.evidence_ids),{str(self.evidence)})
            cited=[observations[oid] for oid in edge.observation_ids]
            self.assertEqual({item.kind for item in cited},{'network.device','network.ip','network.event'})
            self.assertEqual(len({item.source_locator.split(', ')[0] for item in cited}),1)

    def test_document_and_media_membership_remains_node_provenance_only(self):
        from backend.parsers.media_detection import parse_image
        from backend.parsers.text_document import parse_text_document
        from backend.parsers.text_entities import project_text_entities
        from backend.tests.test_media_detection import FACE
        document=parse_text_document(b'Device D-7 was recorded.\n',**self.context)
        projection=project_text_entities(document,[dict(line=0,start=7,end=10,kind='device')],case_id=self.case,max_mentions=100)
        nodes,edges=self.graph(projection,'document')
        self.assertTrue(projection.entities)
        self.assertEqual(edges,[])
        image=parse_image(FACE.read_bytes(),**self.context)
        nodes,edges=self.graph(image,'image')
        self.assertTrue(image.entities)
        self.assertEqual(edges,[])
        for projection in [projection,image]:
            for entity in projection.entities:
                self.assertEqual(entity.evidence_ids,(self.evidence,))
                self.assertTrue(entity.observation_ids)
