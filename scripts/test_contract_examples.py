"""Validate explicit synthetic wire examples; not running application responses."""
import copy
import json
import os
from pathlib import Path
import unittest
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

CASE_ID = "00000000-0000-4000-8000-000000000001"
EVIDENCE_ID = "00000000-0000-4000-8000-000000000002"
RUN_ID = "00000000-0000-4000-8000-000000000003"
OBSERVATION_ID = "00000000-0000-4000-8000-000000000004"


class WireExamples(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads(Path(os.environ["EVORA_CONTRACT_BUNDLE"]).read_text())

    def validator(self, name):
        root = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$ref": "#/components/schemas/" + name,
            "components": self.spec["components"],
        }
        Draft202012Validator.check_schema(root)
        return Draft202012Validator(root, format_checker=FormatChecker())

    def answer(self, supported):
        return {
            "case_id": CASE_ID, "question": "Which row mentions D-7 and D-8?",
            "supported": supported, "answer": "The synthetic message co-mentions both candidate devices." if supported else "Insufficient evidence.",
            "citations": [{"claim": "The message co-mentions D-7 and D-8.", "evidence_id": EVIDENCE_ID, "source_locator": "row 2, body"}] if supported else [],
            "retrieval_version": "synthetic-test-v1",
        }

    def test_supported_answer_with_citation_is_valid(self):
        self.validator("CaseAnswer").validate(self.answer(True))

    def test_supported_answer_without_citation_is_invalid(self):
        answer = self.answer(True)
        answer["citations"] = []
        self.assertFalse(self.validator("CaseAnswer").is_valid(answer))

    def test_unsupported_answer_without_citations_is_valid(self):
        self.validator("CaseAnswer").validate(self.answer(False))

    def test_unsupported_answer_with_citation_is_invalid(self):
        answer = self.answer(False)
        answer["citations"] = self.answer(True)["citations"]
        self.assertFalse(self.validator("CaseAnswer").is_valid(answer))

    def test_empty_graph_before_analysis_is_valid(self):
        self.validator("Graph").validate({"case_id": CASE_ID, "nodes": [], "edges": []})

    def test_nonempty_graph_without_run_is_invalid(self):
        graph = {"case_id": CASE_ID, "nodes": [{"id": EVIDENCE_ID, "case_id": CASE_ID, "kind": "evidence", "label": "Synthetic message", "evidence_ids": [EVIDENCE_ID]}], "edges": []}
        self.assertFalse(self.validator("Graph").is_valid(graph))
        graph["analysis_run_id"] = RUN_ID
        self.validator("Graph").validate(graph)

    def test_finding_page_requires_run_for_total_or_nonempty_items(self):
        finding = {
            "id": OBSERVATION_ID, "case_id": CASE_ID, "analysis_run_id": RUN_ID,
            "kind": "relationship", "summary": "Synthetic candidate co-mention",
            "evidence_ids": [EVIDENCE_ID], "observation_ids": [OBSERVATION_ID],
            "rule": "synthetic-test-v1", "confidence": 0.5,
        }
        for items, total in (([], 1), ([finding], 0), ([finding], 1)):
            with self.subTest(total=total, item_count=len(items)):
                page = {"items": items, "total": total, "limit": 20, "offset": 20}
                self.assertFalse(self.validator("FindingPage").is_valid(page))
                page["analysis_run_id"] = RUN_ID
                self.validator("FindingPage").validate(page)

    def test_empty_finding_page_before_analysis_is_valid(self):
        self.validator("FindingPage").validate({"items": [], "total": 0, "limit": 20, "offset": 0})

    def test_empty_selected_completed_pages_with_run_are_valid(self):
        # Empty payloads cannot prove whether a completed snapshot exists.
        # Producers MUST include its ID whenever a completed run was selected.
        page = {"analysis_run_id": RUN_ID, "items": [], "total": 0, "limit": 20, "offset": 0}
        for name in ("FindingPage", "TriagePage"):
            with self.subTest(schema=name):
                self.validator(name).validate(page)

    def test_scored_triage_page_requires_snapshot_id(self):
        result = {
            "id": OBSERVATION_ID, "case_id": CASE_ID, "evidence_id": EVIDENCE_ID,
            "analysis_run_id": RUN_ID, "score": 30, "priority": "P3",
            "factors": [], "explanation": "Synthetic schema test only",
            "created_at": "2026-01-12T10:05:00Z",
        }
        page = {"items": [{"evidence_id": EVIDENCE_ID, "latest_result": result}],
                "total": 1, "limit": 20, "offset": 0}
        self.assertFalse(self.validator("TriagePage").is_valid(page))
        page["analysis_run_id"] = RUN_ID
        self.validator("TriagePage").validate(page)

    def test_unscored_triage_before_analysis_is_valid(self):
        self.validator("TriagePage").validate({
            "items": [{"evidence_id": EVIDENCE_ID}], "total": 1,
            "limit": 20, "offset": 0,
        })

    def test_graph_edge_requires_observation_provenance(self):
        edge = {"id": RUN_ID, "case_id": CASE_ID, "from_id": EVIDENCE_ID, "to_id": OBSERVATION_ID, "kind": "candidate_link", "evidence_ids": [EVIDENCE_ID], "confidence": 0.5}
        self.assertFalse(self.validator("GraphEdge").is_valid(edge))
        edge["observation_ids"] = [OBSERVATION_ID]
        self.validator("GraphEdge").validate(edge)
        edge["observation_ids"] = []
        self.assertFalse(self.validator("GraphEdge").is_valid(edge))

    def test_snapshot_rejects_duplicate_ids_and_invalid_hash(self):
        # Shape-only example; digest consistency is an implementation acceptance test.
        snapshot = {"case_id": CASE_ID, "evidence_ids": [EVIDENCE_ID], "processing_run_ids": [RUN_ID], "observation_ids": [OBSERVATION_ID], "sha256": "a" * 64}
        self.validator("AnalysisInputSnapshot").validate(snapshot)
        duplicate = copy.deepcopy(snapshot)
        duplicate["evidence_ids"].append(EVIDENCE_ID)
        self.assertFalse(self.validator("AnalysisInputSnapshot").is_valid(duplicate))
        snapshot["sha256"] = "not-a-digest"
        self.assertFalse(self.validator("AnalysisInputSnapshot").is_valid(snapshot))

    def test_analysis_run_requires_snapshot(self):
        run: dict[str, Any] = {"id": RUN_ID, "case_id": CASE_ID, "status": "queued", "trigger": "initial", "algorithm_version": "synthetic-test-v1", "created_at": "2026-01-12T10:04:00Z"}
        self.assertFalse(self.validator("AnalysisRun").is_valid(run))
        run["input_snapshot"] = {"case_id": CASE_ID, "evidence_ids": [], "processing_run_ids": [], "observation_ids": [], "sha256": "a" * 64}
        self.validator("AnalysisRun").validate(run)

    def test_completed_processing_requires_finish_time(self):
        run = {"id": RUN_ID, "case_id": CASE_ID, "evidence_id": EVIDENCE_ID, "status": "completed", "processor_version": "synthetic-test-v1", "created_at": "2026-01-12T10:04:00Z"}
        self.assertFalse(self.validator("ProcessingRun").is_valid(run))
        run["finished_at"] = "2026-01-12T10:05:00Z"
        self.validator("ProcessingRun").validate(run)

    def test_failed_processing_requires_error(self):
        run = {"id": RUN_ID, "case_id": CASE_ID, "evidence_id": EVIDENCE_ID, "status": "failed", "processor_version": "synthetic-test-v1", "created_at": "2026-01-12T10:04:00Z", "finished_at": "2026-01-12T10:05:00Z"}
        self.assertFalse(self.validator("ProcessingRun").is_valid(run))
        run["error"] = "Synthetic unsupported format"
        self.validator("ProcessingRun").validate(run)

    def test_completed_analysis_requires_finish_time(self):
        run: dict[str, Any] = {"id": RUN_ID, "case_id": CASE_ID, "status": "completed", "trigger": "initial", "algorithm_version": "synthetic-test-v1", "created_at": "2026-01-12T10:04:00Z", "input_snapshot": {"case_id": CASE_ID, "evidence_ids": [], "processing_run_ids": [], "observation_ids": [], "sha256": "a" * 64}}
        self.assertFalse(self.validator("AnalysisRun").is_valid(run))
        run["finished_at"] = "2026-01-12T10:05:00Z"
        self.validator("AnalysisRun").validate(run)

    def test_failed_analysis_requires_error(self):
        run: dict[str, Any] = {"id": RUN_ID, "case_id": CASE_ID, "status": "failed", "trigger": "initial", "algorithm_version": "synthetic-test-v1", "created_at": "2026-01-12T10:04:00Z", "finished_at": "2026-01-12T10:05:00Z", "input_snapshot": {"case_id": CASE_ID, "evidence_ids": [], "processing_run_ids": [], "observation_ids": [], "sha256": "a" * 64}}
        self.assertFalse(self.validator("AnalysisRun").is_valid(run))
        run["error"] = "Synthetic projection failure"
        self.validator("AnalysisRun").validate(run)

    def transcript_segment(self):
        return {
            "id": OBSERVATION_ID, "case_id": CASE_ID, "evidence_id": EVIDENCE_ID,
            "processing_run_id": RUN_ID, "kind": "transcript.segment",
            "source_locator": "media:start_ms=1250;end_ms=3500",
            "raw_value": "Meet [unclear] at the station.",
            "normalized_value": "Meet [unclear] at the station.",
            "extraction_confidence": 0.4,
        }

    def revision_request(self):
        return {
            "processing_run_id": RUN_ID, "base_processing_run_id": RUN_ID,
            "expected_latest_revision_id": None,
            "corrected_text": "Meet D-7 at the station.",
            "reason": "Synthetic permitted listening check.",
        }

    def revision(self):
        return {
            "id": "00000000-0000-4000-8000-000000000005",
            "case_id": CASE_ID, "evidence_id": EVIDENCE_ID,
            "source_observation_id": OBSERVATION_ID, "processing_run_id": RUN_ID,
            "base_processing_run_id": RUN_ID, "previous_revision_id": None,
            "corrected_text": "Meet D-7 at the station.",
            "reason": "Synthetic permitted listening check.", "actor_id": "synthetic-actor",
            "created_at": "2026-01-12T10:06:00Z",
            "derived_processing_run_id": "00000000-0000-4000-8000-000000000006",
            "derived_observation_id": "00000000-0000-4000-8000-000000000007",
        }

    def test_contract_preserves_existing_operations_and_adds_structured_interpretation(self):
        original = {
            "createCase", "listCases", "getCase", "uploadEvidence", "listEvidence",
            "getEvidence", "downloadEvidence", "startProcessing", "listProcessingRuns",
            "getProcessingRun", "listObservations", "listEntities", "listEvents",
            "startAnalysis", "listAnalysisRuns", "getAnalysisRun", "getGraph",
            "listFindings", "reviewFinding", "listFindingReviews", "listTriage",
            "getTriageHistory", "setPriorityOverride", "askCaseQuestion", "listAuditEvents",
            "updateCaseMembership", "listProviderModels", "connectChatGPT", "touchLocalSession",
            "getLocalSession", "updateSettings", "analyzeVideo", "disconnectChatGPT",
            "analyzeImage", "createLocalAccount", "listAccountAudit", "changeLocalPassword",
            "getSettings", "getMediaCapabilities", "setupLocalAdministrator", "recoverLocalAccount",
            "updateLocalAccount", "loginLocalAccount", "getChatGPTStatus", "listLocalAccounts",
            "listCaseMembers", "getAuthStatus", "logoutLocalAccount",
        }
        actual = [operation["operationId"] for path in self.spec["paths"].values()
                  for method, operation in path.items()
                  if method in {"get", "post", "put", "patch", "delete"}]
        expected = original | {"appendTranscriptRevision", "listTranscriptRevisions", "interpretEvidence"}
        self.assertEqual(set(actual), expected)
        self.assertEqual(len(actual), len(expected))
        self.assertEqual(self.spec["info"]["version"], "0.3.0")

    def test_structured_interpretation_request_and_run_metadata(self):
        operation=self.spec['paths']['/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs/interpret-as']['post']
        schema=operation['requestBody']['content']['application/json']['schema']
        validator=Draft202012Validator(schema)
        validator.validate({'kind':'mobile_log'})
        for invalid in ({'kind':'audio'},{'kind':'mobile_log','extra':True},{}):
            self.assertFalse(validator.is_valid(invalid))
        run={'id':RUN_ID,'case_id':CASE_ID,'evidence_id':EVIDENCE_ID,'status':'queued','processor_version':'processing-lifecycle/5',
             'created_at':'2026-01-12T10:04:00Z','source_kind':'document','processing_kind':'mobile_log'}
        self.validator('ProcessingRun').validate(run)
        run['processing_kind']='audio'
        self.assertFalse(self.validator('ProcessingRun').is_valid(run))

    def test_audio_kind_and_existing_video_kind_are_valid(self):
        for kind in ("audio", "video"):
            with self.subTest(kind=kind):
                self.validator("EvidenceKind").validate(kind)

    def test_speech_unclear_and_unavailable_score_examples(self):
        segment = self.transcript_segment()
        self.validator("Observation").validate(segment)
        self.assertNotIn("observed_at_utc", segment)
        segment["extraction_confidence"] = 0  # Unavailable-score sentinel, not calibration.
        self.validator("Observation").validate(segment)

    def test_media_locator_syntax_rejects_utc_negative_and_noncanonical_offsets(self):
        for locator in ("2026-01-12T10:00:00Z", "media:start_ms=-1;end_ms=10",
                        "media:start_ms=01;end_ms=10", "media:start_ms=1.5;end_ms=10",
                        "row 2", "media:start_ms=10"):
            with self.subTest(locator=locator):
                segment = self.transcript_segment()
                segment["source_locator"] = locator
                self.assertFalse(self.validator("Observation").is_valid(segment))
        # Increasing end/duration bounds and capture-time mapping require runtime
        # decoding checks; JSON Schema validates syntax, not those relationships.

    def test_no_audio_and_silence_status_examples(self):
        for status in ("no_audio", "silence"):
            with self.subTest(status=status):
                observation = self.transcript_segment()
                observation.update(kind="transcript.status", source_locator="entire original artifact",
                                   raw_value="", normalized_value=status, extraction_confidence=0)
                self.validator("Observation").validate(observation)
        observation["normalized_value"] = "invented speech"
        self.assertFalse(self.validator("Observation").is_valid(observation))

    def test_corrected_segment_keeps_machine_text_and_links_revision(self):
        machine = self.transcript_segment()
        derived = copy.deepcopy(machine)
        revision = self.revision()
        derived.update(id=revision["derived_observation_id"],
                       processing_run_id=revision["derived_processing_run_id"],
                       normalized_value=revision["corrected_text"],
                       source_observation_id=OBSERVATION_ID, transcript_revision_id=revision["id"])
        self.validator("Observation").validate(derived)
        for field in ("raw_value", "source_locator", "extraction_confidence", "evidence_id"):
            self.assertEqual(derived[field], machine[field])
        del derived["source_observation_id"]
        self.assertFalse(self.validator("Observation").is_valid(derived))

    def test_uncorrected_materialized_segment_exposes_machine_root_without_revision(self):
        segment = self.transcript_segment()
        segment.update(id=self.revision()["derived_observation_id"],
                       processing_run_id=self.revision()["derived_processing_run_id"],
                       source_observation_id=OBSERVATION_ID)
        self.validator("Observation").validate(segment)
        self.assertNotIn("transcript_revision_id", segment)

    def test_revision_request_requires_original_run_base_and_explicit_precondition(self):
        request = self.revision_request()
        self.validator("CreateTranscriptRevision").validate(request)
        for field in ("processing_run_id", "base_processing_run_id", "expected_latest_revision_id"):
            with self.subTest(field=field):
                invalid = copy.deepcopy(request)
                del invalid[field]
                self.assertFalse(self.validator("CreateTranscriptRevision").is_valid(invalid))
        request["expected_latest_revision_id"] = self.revision()["id"]
        self.validator("CreateTranscriptRevision").validate(request)

    def test_revision_rejects_blank_text_reason_and_client_authorship(self):
        for field, value in (("corrected_text", ""), ("corrected_text", " \n\t"),
                             ("reason", ""), ("reason", "  "), ("actor_id", "forged"),
                             ("created_at", "2026-01-12T10:06:00Z"),
                             ("source_locator", "media:start_ms=0;end_ms=1"),
                             ("speaker_id", "person-1")):
            with self.subTest(field=field, value=value):
                request = self.revision_request()
                request[field] = value
                self.assertFalse(self.validator("CreateTranscriptRevision").is_valid(request))

    def test_revision_response_and_history_require_complete_lineage(self):
        revision = self.revision()
        self.validator("TranscriptRevision").validate(revision)
        page = {"items": [revision], "total": 1, "limit": 20, "offset": 0}
        self.validator("TranscriptRevisionPage").validate(page)
        for field in ("source_observation_id", "processing_run_id", "base_processing_run_id",
                      "previous_revision_id", "actor_id", "created_at",
                      "derived_processing_run_id", "derived_observation_id"):
            with self.subTest(field=field):
                invalid = copy.deepcopy(revision)
                del invalid[field]
                self.assertFalse(self.validator("TranscriptRevision").is_valid(invalid))
        # Same-case/evidence joins cannot be proven by UUID-shaped synthetic data.
        # U14B must execute real two-case and immutable snapshot acceptance tests.

    def test_revision_routes_and_bodyless_existing_commands(self):
        path = "/api/v1/cases/{caseId}/observations/{observationId}/transcript-revisions"
        endpoint = self.spec["paths"][path]
        self.assertEqual(endpoint["post"]["operationId"], "appendTranscriptRevision")
        self.assertEqual(endpoint["get"]["operationId"], "listTranscriptRevisions")
        self.assertEqual(set(endpoint["post"]["responses"]), {"201", "400", "401", "404", "409"})
        for route in ("/api/v1/cases/{caseId}/analysis-runs",
                      "/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs"):
            self.assertNotIn("requestBody", self.spec["paths"][route]["post"])

    def test_invalid_uuid_is_rejected(self):
        answer = self.answer(True)
        answer["case_id"] = "foreign-invalid-id"
        self.assertFalse(self.validator("CaseAnswer").is_valid(answer))

    def test_undeclared_response_field_is_rejected(self):
        answer = self.answer(True)
        answer["system_online"] = True
        self.assertFalse(self.validator("CaseAnswer").is_valid(answer))


if __name__ == "__main__":
    unittest.main()
