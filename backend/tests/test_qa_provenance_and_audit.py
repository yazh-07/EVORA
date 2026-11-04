"""F08E / U10C / I05C Q&A private provenance, audit linkage, and citation verification tests."""

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient
from jsonschema import Draft202012Validator, FormatChecker

from backend.app import create_app
from backend.auth import SyntheticTokenVerifier
from backend.qa_provenance import (MODEL_VERSION, PROMPT_TEMPLATE_VERSION,
                                   record_qa_provenance)
from backend.questions import RETRIEVAL_VERSION


ROOT = Path(__file__).resolve().parents[2]


class QAProvenanceAndAuditTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        self.app = create_app(
            root / "qa.sqlite3", storage_dir=root / "private",
            token_verifier=SyntheticTokenVerifier({
                "qa-investigator": "investigator-1",
                "qa-other": "investigator-2",
            })
        )
        await self.enterAsyncContext(self.app.router.lifespan_context(self.app))
        self.client = await self.enterAsyncContext(AsyncClient(
            transport=ASGITransport(self.app), base_url="http://test",
            headers={"Authorization": "Bearer qa-investigator"}
        ))
        bundle_path = os.environ.get("EVORA_CONTRACT_BUNDLE", "/tmp/evora-openapi.json")
        self.bundle = json.loads(Path(bundle_path).read_text())
        self.case = (await self.client.post("/api/v1/cases", json={"title": "QA Provenance Case"})).json()["id"]
        # Upload network evidence
        network_data = (ROOT / "fixtures/synthetic-case/network.csv").read_bytes()
        ev_res = await self.client.post(
            f"/api/v1/cases/{self.case}/evidence",
            data={"kind": "network_log", "source_label": "Network QA Source"},
            files={"file": ("network.csv", network_data, "text/csv")}
        )
        self.evidence = ev_res.json()
        await self.client.post(
            f"/api/v1/cases/{self.case}/evidence/{self.evidence['id']}/processing-runs",
            headers={"Idempotency-Key": str(uuid4())}
        )

    def validate(self, schema_name: str, payload: dict):
        Draft202012Validator(
            {"$ref": f"#/components/schemas/{schema_name}", "components": self.bundle["components"]},
            format_checker=FormatChecker()
        ).validate(payload)

    async def test_supported_qa_persists_provenance_and_safe_audit(self):
        response = await self.client.post(
            f"/api/v1/cases/{self.case}/questions",
            json={"question": "D-7 connected 203.0.113.7"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        answer = response.json()
        self.validate("CaseAnswer", answer)
        self.assertTrue(answer["supported"])
        self.assertGreater(len(answer["citations"]), 0)
        self.assertEqual(answer["retrieval_version"], RETRIEVAL_VERSION)
        self.assertEqual(answer["model_version"], MODEL_VERSION)
        self.assertEqual(answer["prompt_template_version"], PROMPT_TEMPLATE_VERSION)
        provenance_id = answer.get("provenance_id")
        self.assertIsNotNone(provenance_id)

        # Inspect private storage directly
        with self.app.state.database.connect() as conn:
            prov = conn.execute("SELECT * FROM qa_provenance WHERE id=?", (provenance_id,)).fetchone()
            self.assertIsNotNone(prov, "Private provenance record must exist")
            prov_dict = dict(prov)
            self.assertEqual(prov_dict["case_id"], self.case)
            self.assertEqual(prov_dict["actor_id"], "investigator-1")
            self.assertEqual(prov_dict["retrieval_version"], RETRIEVAL_VERSION)
            self.assertEqual(prov_dict["supported"], 1)

            # Audit log verification: must not leak raw query content
            events = conn.execute(
                "SELECT * FROM audit_events WHERE case_id=? AND action='askCaseQuestion'",
                (self.case,)
            ).fetchall()
            self.assertEqual(len(events), 1)
            event = dict(events[0])
            self.assertEqual(event["action"], "askCaseQuestion")
            self.assertNotIn("203.0.113.7", json.dumps(event))

    async def test_unsupported_qa_returns_honest_fallback_with_zero_citations(self):
        response = await self.client.post(
            f"/api/v1/cases/{self.case}/questions",
            json={"question": "Who committed the crime with D-7?"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        answer = response.json()
        self.validate("CaseAnswer", answer)
        self.assertFalse(answer["supported"])
        self.assertEqual(len(answer["citations"]), 0)
        self.assertIn("Insufficient evidence", answer["answer"])
        provenance_id = answer.get("provenance_id")
        self.assertIsNotNone(provenance_id)

        with self.app.state.database.connect() as conn:
            prov = conn.execute("SELECT * FROM qa_provenance WHERE id=?", (provenance_id,)).fetchone()
            self.assertIsNotNone(prov)
            self.assertEqual(dict(prov)["supported"], 0)

    def test_rag_grounding_evaluation_metrics(self):
        from backend.evaluation import evaluate_rag_grounding
        benchmarks = [
            {"expected_supported": True, "supported": True, "citations": [{"evidence_id": "e1", "source_locator": "line 1"}]},
            {"expected_supported": False, "supported": False, "citations": []},
            {"expected_supported": True, "supported": False, "citations": []},
        ]
        metrics = evaluate_rag_grounding(benchmarks)
        self.assertEqual(metrics["total_evaluations"], 3)
        self.assertEqual(metrics["grounding_rate"], 0.5)
        self.assertEqual(metrics["citation_precision"], 1.0)
        self.assertEqual(metrics["unsupported_rejection_rate"], 1.0)
