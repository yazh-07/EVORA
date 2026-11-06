"""Transcription planning regressions, not model or application tests."""
import copy
import json
import os
from pathlib import Path
import unittest

if __package__:
    from . import verify_coordination as audit
else:
    import verify_coordination as audit


class TranscriptionScopeTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.rows = audit.parse_catalog((root / "fixtures/planning/transcription-task-catalog.txt").read_text(), strict=True)
        self.spec = json.loads(Path(os.environ["EVORA_CONTRACT_BUNDLE"]).read_text())

    def test_transcription_dependency_handoffs_pass(self):
        audit.verify_transcription_handoffs(self.rows, audit.dependency_closure(self.rows))

    def test_removing_transcription_from_common_outputs_fails(self):
        rows = copy.deepcopy(self.rows)
        rows["P05C"]["dependencies"].discard("P16B")
        with self.assertRaisesRegex(ValueError, "Transcription handoff P05C"):
            audit.verify_transcription_handoffs(rows, audit.dependency_closure(rows))

    def test_missing_correction_audit_prerequisite_fails(self):
        rows = copy.deepcopy(self.rows)
        rows["U14B"]["dependencies"].discard("F06")
        with self.assertRaisesRegex(ValueError, "Transcription handoff U14B"):
            audit.verify_transcription_handoffs(rows, audit.dependency_closure(rows))

    def test_missing_transcript_workflow_integration_fails(self):
        rows = copy.deepcopy(self.rows)
        rows["I03B"]["dependencies"].discard("U14C")
        with self.assertRaisesRegex(ValueError, "Transcription handoff I03B"):
            audit.verify_transcription_handoffs(rows, audit.dependency_closure(rows))

    def test_speech_tasks_not_optional_or_late(self):
        for task, checkpoint in {"P16": "3B", "P16B": "3B", "U14": "3C", "U14B": "3C", "U14C": "3C"}.items():
            with self.subTest(task=task):
                rows = copy.deepcopy(self.rows)
                rows[task]["checkpoint"] = "6C"
                with self.assertRaisesRegex(ValueError, "Transcription checkpoint"):
                    audit.verify_transcription_handoffs(rows, audit.dependency_closure(rows))

    def test_renamed_operation_fails_even_at_same_count(self):
        spec = copy.deepcopy(self.spec)
        for item in spec["paths"].values():
            for operation in item.values():
                if isinstance(operation, dict) and operation.get("operationId") == "appendTranscriptRevision":
                    operation["operationId"] = "silentlyRenamedCorrection"
        with self.assertRaisesRegex(ValueError, "Expected preserved operations"):
            audit.verify_spec(spec)

    def test_old_draft_version_fails(self):
        spec = copy.deepcopy(self.spec)
        spec["info"]["version"] = "0.2.0"
        with self.assertRaisesRegex(ValueError, "version 0.3.0"):
            audit.verify_spec(spec)

    def test_current_media_addition_cannot_be_renamed_or_duplicated(self):
        for replacement in ('silentlyRenamedImage','appendTranscriptRevision'):
            spec=copy.deepcopy(self.spec)
            for item in spec['paths'].values():
                for operation in item.values():
                    if isinstance(operation,dict) and operation.get('operationId')=='analyzeImage':
                        operation['operationId']=replacement
            with self.assertRaisesRegex(ValueError,'Expected preserved operations|Duplicate operation'):
                audit.verify_spec(spec)

    def test_broken_contract_reference_is_rejected(self):
        spec=copy.deepcopy(self.spec)
        spec['components']['schemas']['BrokenFixture']={'$ref':'#/components/schemas/MissingFixture'}
        with self.assertRaisesRegex(ValueError,'Broken reference'):audit.verify_spec(spec)


if __name__ == "__main__":
    unittest.main()
