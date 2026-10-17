"""Validate planning artifacts; never reports application correctness."""
import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import re

TASK_ID = r"\b[GFPAUI]\d{2}[A-Z]?\b"
CHECKPOINT_ID = r"(?:0|[1-9]\d*)[A-Z]?"
CATALOG_SECTIONS = (
    "Common-base and setup", "M1 — Evidence Foundation", "M2 — Multimodal Processing",
    "M3 — Evidence Fusion and Adaptive Triage", "M4 — Investigator Application",
    "Cross-module integration and evaluation",
)
CATALOG_HEADERS = (
    "ID", "One-task scope", "Depends on", "Contract", "Acceptance for this PR", "Checkpoint",
)


def named_table(text, heading, headers, label):
    """Parse the canonical table without filtering malformed data rows away."""
    lines = text.splitlines()
    starts = [index for index, line in enumerate(lines) if line.strip() == f"## {heading}"]
    if len(starts) != 1:
        raise ValueError(f"Missing/duplicate {label} heading: {heading}")
    start = starts[0] + 1
    end = next((index for index in range(start, len(lines))
                if re.match(r"^#{1,6}\s", lines[index].strip())), len(lines))
    table_lines = [index for index in range(start, end) if "|" in lines[index]]
    if not table_lines:
        raise ValueError(f"Missing {label} table")
    parsed = []
    for index in range(table_lines[0], table_lines[-1] + 1):
        line = lines[index].strip()
        if not line or not line.startswith("|") or not line.endswith("|"):
            raise ValueError(f"Malformed {label} row at line {index + 1}")
        cells = [cell.strip() for cell in line[1:-1].split("|")]
        parsed.append((index + 1, cells))
    if tuple(parsed[0][1]) != tuple(headers):
        raise ValueError(f"Malformed {label} header")
    if (len(parsed) < 2 or len(parsed[1][1]) != len(headers)
            or any(not re.fullmatch(r":?-{3,}:?", cell) for cell in parsed[1][1])):
        raise ValueError(f"Malformed {label} separator")
    for number, cells in parsed[2:]:
        if len(cells) != len(headers) or any(not cell for cell in cells):
            raise ValueError(f"Malformed {label} row at line {number}")
    return parsed[2:]


def parse_catalog(text, strict=False):
    """Read canonical six-column tables, or legacy row-only helper fixtures."""
    rows = {}
    if strict:
        source = [row for heading in CATALOG_SECTIONS
                  for row in named_table(text, heading, CATALOG_HEADERS, "task catalog")]
    else:
        source = [(number, [cell.strip() for cell in line.strip().strip("|").split("|")])
                  for number, line in enumerate(text.splitlines(), 1)]
    for number, cells in source:
        if strict and not re.fullmatch(TASK_ID, cells[0]):
            raise ValueError(f"Malformed task ID {cells[0]} at line {number}")
        if strict and not re.fullmatch(CHECKPOINT_ID, cells[5]):
            raise ValueError(f"Malformed task checkpoint {cells[5]} at line {number}")
        if not cells or not re.fullmatch(TASK_ID, cells[0]):
            continue
        task_id = cells[0]
        if len(cells) not in (4, 5, 6):
            raise ValueError(f"Malformed task row {task_id} at line {number}")
        if task_id in rows:
            raise ValueError(f"Duplicate task ID {task_id}")
        dependencies = set(re.findall(TASK_ID, cells[2])) if len(cells) >= 5 else set()
        rows[task_id] = {"line": number, "cells": cells, "dependencies": dependencies,
                         "checkpoint": cells[5] if len(cells) == 6 else None}
    if not rows:
        raise ValueError("No tasks found")
    return rows


def dependency_closure(rows):
    """Compute dependencies after rejecting missing IDs and cycles."""
    closures, visiting = {}, set()

    def visit(task_id):
        if task_id not in rows:
            raise ValueError(f"Missing dependency {task_id}")
        if task_id in visiting:
            raise ValueError(f"Dependency cycle involving {task_id}")
        if task_id in closures:
            return closures[task_id]
        visiting.add(task_id)
        result = set(rows[task_id]["dependencies"])
        for dependency in rows[task_id]["dependencies"]:
            result.update(visit(dependency))
        visiting.remove(task_id)
        closures[task_id] = result
        return result

    for task_id in rows:
        visit(task_id)
    return closures


def roadmap_ledger(roadmap):
    return named_table(
        roadmap, "Exact checkpoint ledger",
        ("Checkpoint", "Exact task membership", "Exit gate IDs", "Exit evidence", "State"),
        "Roadmap ledger",
    )


def exit_gate_ids(value, label, checkpoint):
    gates = value.split(", ")
    if not gates or any(not re.fullmatch(TASK_ID, gate) for gate in gates):
        raise ValueError(f"{label} requires exact exit gate IDs for {checkpoint}")
    if len(gates) != len(set(gates)):
        raise ValueError(f"Duplicate {label} exit gate for {checkpoint}")
    return set(gates)


def verify_phases(rows, roadmap):
    """Compare exhaustive checkpoint assignments with the task catalog."""
    checkpoints, assigned = {}, {}
    ledger = roadmap_ledger(roadmap)
    for number, cells in ledger:
        if not re.fullmatch(CHECKPOINT_ID, cells[0]):
            raise ValueError(f"Malformed checkpoint ID {cells[0]} at line {number}")
        checkpoint = cells[0]
        if checkpoint in checkpoints:
            raise ValueError(f"Duplicate checkpoint {checkpoint}")
        if cells[4] not in {"Backlog", "In Progress", "Complete", "Blocked"}:
            raise ValueError(f"Invalid checkpoint state {checkpoint}: {cells[4]}")
        tasks = cells[1].split(", ")
        if not tasks or any(not re.fullmatch(TASK_ID, task) for task in tasks):
            raise ValueError(f"Checkpoint {checkpoint} requires exact task IDs, not ranges")
        checkpoints[checkpoint] = tasks
        for task in tasks:
            if task not in rows:
                raise ValueError(f"Unknown checkpoint task {task}")
            if task in assigned:
                raise ValueError(f"Duplicate phase assignment {task}")
            assigned[task] = checkpoint
    if not checkpoints:
        raise ValueError("No phase checkpoints found")
    natural_order = sorted(checkpoints, key=lambda value: (
        int(re.findall(r"\d+", value)[0]), re.sub(r"^\d+", "", value)))
    if list(checkpoints) != natural_order or natural_order[0] != "0":
        raise ValueError("Checkpoint order must start at 0 and progress numerically")
    missing = set(rows) - set(assigned)
    if missing:
        raise ValueError(f"Unassigned phase tasks {sorted(missing)}")
    order = {checkpoint: index for index, checkpoint in enumerate(checkpoints)}
    for task, row in rows.items():
        if row.get("checkpoint") != assigned[task]:
            raise ValueError(f"Checkpoint mismatch for {task}: catalog/roadmap")
        for dependency in row["dependencies"]:
            if dependency not in assigned:
                raise ValueError(f"Missing dependency {dependency}")
            if order[assigned[dependency]] > order[assigned[task]]:
                raise ValueError(f"Later checkpoint prerequisite: {task} requires {dependency}")
    for _, cells in ledger:
        for gate in exit_gate_ids(cells[2], "Roadmap", cells[0]):
            if assigned.get(gate) != cells[0]:
                raise ValueError(f"Roadmap exit gate checkpoint mismatch: {cells[0]}/{gate}")
    return {checkpoint: len(tasks) for checkpoint, tasks in checkpoints.items()}


def verify_runbook(rows, checkpoint_tasks, runbook, roadmap):
    """Require ordered evidence rows with the canonical Roadmap exit gate sets."""
    canonical_gates = {cells[0]: exit_gate_ids(cells[2], "Roadmap", cells[0])
                       for _, cells in roadmap_ledger(roadmap)}
    ledger = named_table(
        runbook, "Checkpoint execution ledger",
        ("Checkpoint", "Exit gate IDs", "Required real proof", "Regressions"), "runbook ledger",
    )
    seen = []
    for number, cells in ledger:
        if not re.fullmatch(CHECKPOINT_ID, cells[0]):
            raise ValueError(f"Malformed runbook checkpoint {cells[0]} at line {number}")
        checkpoint = cells[0]
        if checkpoint not in checkpoint_tasks or checkpoint in seen:
            raise ValueError(f"Unknown/duplicate runbook checkpoint {checkpoint}")
        gates = exit_gate_ids(cells[1], "Runbook", checkpoint)
        for gate in gates:
            if gate not in rows or rows[gate].get("checkpoint") != checkpoint:
                raise ValueError(f"Runbook exit gate checkpoint mismatch: {checkpoint}/{gate}")
        if gates != canonical_gates.get(checkpoint):
            raise ValueError(f"Runbook exit gate set mismatch: {checkpoint}")
        if not cells[2] or not cells[3]:
            raise ValueError(f"Missing runbook exit evidence/regressions for {checkpoint}")
        seen.append(checkpoint)
    if seen != list(checkpoint_tasks):
        raise ValueError("Runbook checkpoint coverage/order does not match roadmap")


FEATURE_CAPABILITIES = frozenset((
    "Case creation/catalog/access",
    "Immutable original intake/hash/download/source metadata",
    "Private provenance/audit foundations",
    "Network records",
    "GPS/spatial records",
    "Messages/device mentions",
    "Documents/reports/text",
    "OCR for scanned document/image text",
    "Image object/person/vehicle detection",
    "CCTV/video observations",
    "Local audio/video speech transcription (approved addition)",
    "Transcript playback/search and audited corrections (approved addition)",
    "Mobile logs",
    "Transactions",
    "Common normalized observations/entities/events",
    "Processing lifecycle/full dispatch/deeper existing processing",
    "Versioned graph storage/projection recovery",
    "Cross-source relationship reasoning",
    "Relevance and graph-connectivity factors",
    "Temporal-proximity factor",
    "Independent corroboration factor/findings",
    "Source quality, extraction confidence/count and uncertainty",
    "Potential conflicts and conflict-aware priority",
    "Evidence gaps and gap-relevant priority",
    "Clusters and cluster prioritization",
    "Anomaly detection and triage feedback",
    "Alternative hypothesis comparison",
    "Explainable initial scores and analysis/history",
    "Adaptive new-upload AND detector/deeper-existing-evidence loop",
    "Faithful findings/triage/model explanations",
    "Full retrieval context and grounded LLM RAG",
    "Case/evidence overview and commands/status",
    "Priority/history/graph/finding/uncertainty/entity-event inspectors",
    "Conflicts/gaps/clusters/anomalies/hypotheses panels",
    "Human review and manual priority override",
    "One accessible evidence-first React dashboard",
    "Synthetic/permitted datasets and actual research evaluation",
    "Full integration and clean reproducibility",
    "Comparative/threat/provenance/limitations report",
))


def verify_feature_checkpoints(rows, checkpoint_tasks, feature_map):
    """Require the complete fixed inventory and its exact derived phase mirror."""
    seen = set()
    ledger = named_table(
        feature_map, "Complete feature ownership and acceptance",
        ("Initial capability", "Accountable module", "Concrete tasks/stage",
         "Evidence needed to claim it works", "Checkpoint coverage"), "feature inventory",
    )
    for _, cells in ledger:
        if cells[0] in seen:
            raise ValueError(f"Duplicate feature capability: {cells[0]}")
        seen.add(cells[0])
        if re.search(r"\b[GFPAUI]\d{2}[A-Z]?\s*[-–—]\s*(?:[GFPAUI]\d{2}[A-Z]?|\d{2}[A-Z]?|[A-Z])\b", cells[2]):
            raise ValueError(f"Feature task references require exact IDs, not ranges: {cells[0]}")
        tasks = set(re.findall(TASK_ID, cells[2]))
        if "all U tasks in the catalog" in cells[2]:
            tasks.update(task for task in rows if task.startswith("U"))
        if not tasks or tasks - set(rows):
            raise ValueError(f"Unknown/missing feature task references: {cells[0]}")
        expected = {rows[task]["checkpoint"] for task in tasks}
        ordered = [checkpoint for checkpoint in checkpoint_tasks if checkpoint in expected]
        if cells[4].split(", ") != ordered:
            raise ValueError(f"Feature checkpoint coverage mismatch: {cells[0]}")
    if seen != FEATURE_CAPABILITIES:
        raise ValueError(f"Feature capability coverage mismatch: missing {sorted(FEATURE_CAPABILITIES - seen)}, "
                         f"unknown {sorted(seen - FEATURE_CAPABILITIES)}")
    return len(seen)


def verify_transcription_handoffs(rows, closures):
    """Keep the approved speech addition connected to real publication gates."""
    checkpoints = {"P16": "3B", "P16B": "3B", "U14": "3C", "U14B": "3C", "U14C": "3C"}
    for task, checkpoint in checkpoints.items():
        if task not in rows or rows[task].get("checkpoint") != checkpoint:
            raise ValueError(f"Transcription checkpoint {task} must be {checkpoint}")
    # Direct edges make these ownership handoffs explicit even if another path exists.
    handoffs = {
        "P16": {"P04", "P14"}, "P16B": {"P16", "P13B"},
        "P05C": {"P16B"}, "U14": {"P16B", "U05B", "U04"},
        "U14B": {"P16", "P16B", "P14C", "F06", "F00"}, "U14C": {"U14", "U14B"},
        "I03B": {"U14C"},
    }
    for task, required in handoffs.items():
        missing = required - rows.get(task, {}).get("dependencies", set())
        if missing:
            raise ValueError(f"Transcription handoff {task} misses {sorted(missing)}")
    for gate in ("I09", "I09B", "I06"):
        missing = set(checkpoints) - closures.get(gate, set())
        if missing:
            raise ValueError(f"Transcription full-scope gate {gate} misses {sorted(missing)}")


def verify_spec(spec):
    """Check local references and critical cross-module contract invariants."""
    methods = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
    operations = {}
    for path, item in spec["paths"].items():
        for method, operation in item.items():
            if method not in methods:
                continue
            name = operation["operationId"]
            if name in operations:
                raise ValueError(f"Duplicate operation {name}")
            operations[name] = operation
            if operation["responses"].get("400") != {"$ref": "#/components/responses/BadRequest"}:
                raise ValueError(f"Missing common 400 response: {name}")
            if operation["responses"].get("401") != {"$ref": "#/components/responses/Unauthorized"}:
                raise ValueError(f"Missing common 401 response: {name}")
            if "{caseId}" in path and operation["responses"].get("404") != {"$ref": "#/components/responses/NotFound"}:
                raise ValueError(f"Missing common 404 response: {name}")
    expected_operations = {
        "listCases", "createCase", "getCase", "listEvidence", "uploadEvidence",
        "getEvidence", "downloadEvidence", "startProcessing", "getProcessingRun",
        "listProcessingRuns", "listObservations", "listEntities", "listEvents",
        "startAnalysis", "getAnalysisRun", "listAnalysisRuns", "getGraph",
        "listFindings", "listTriage", "getTriageHistory", "reviewFinding",
        "listFindingReviews", "setPriorityOverride", "askCaseQuestion", "listAuditEvents",
        "listTranscriptRevisions", "appendTranscriptRevision",
    }
    if set(operations) != expected_operations:
        raise ValueError(f"Expected preserved operations plus transcript revisions; "
                         f"missing {sorted(expected_operations - set(operations))}, "
                         f"unexpected {sorted(set(operations) - expected_operations)}")
    if spec["info"]["version"] != "0.3.0":
        raise ValueError("Expected transcription draft version 0.3.0")

    def references(value):
        if isinstance(value, dict):
            if "$ref" in value:
                ref = value["$ref"]
                if not ref.startswith("#/"):
                    raise ValueError(f"External reference not supported: {ref}")
                target = spec
                try:
                    for part in ref[2:].split("/"):
                        target = target[part.replace("~1", "/").replace("~0", "~")]
                except (KeyError, TypeError) as error:
                    raise ValueError(f"Broken reference {ref}") from error
            for child in value.values():
                references(child)
        elif isinstance(value, list):
            for child in value:
                references(child)

    references(spec)
    schemas = spec["components"]["schemas"]
    if "input_snapshot" not in schemas["AnalysisRun"]["required"]:
        raise ValueError("AnalysisRun must require input_snapshot")
    for field in ("case_id", "evidence_ids", "processing_run_ids", "observation_ids", "sha256"):
        if field not in schemas["AnalysisInputSnapshot"]["required"]:
            raise ValueError(f"Snapshot missing required field {field}")
    for name in ("GraphEdge", "Finding"):
        if "observation_ids" not in schemas[name]["required"]:
            raise ValueError(f"{name} missing observation_ids provenance")
    for name in ("getGraph", "listFindings", "listTriage"):
        if {"$ref": "#/components/parameters/AnalysisRunSelector"} not in operations[name]["parameters"]:
            raise ValueError(f"{name} missing snapshot selector")
    if "requestBody" in operations["startAnalysis"]:
        raise ValueError("Trigger is server-derived; unexpected startAnalysis body")
    if not schemas["CaseAnswer"].get("allOf"):
        raise ValueError("CaseAnswer must enforce supported/unsupported citations")
    return operations


def verify_documents(root):
    """Check repository Markdown local targets and trailing whitespace."""
    count = 0
    for path in sorted(root.rglob("*.md")):
        if any(part in {".git", "node_modules", ".venv"} for part in path.relative_to(root).parts):
            continue
        count += 1
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), 1):
            if line.rstrip() != line:
                raise ValueError(f"Trailing whitespace {path.relative_to(root)}:{number}")
        for target in re.findall(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", text):
            if target.startswith(("https:", "http:", "mailto:", "#")):
                continue
            if not (path.parent / target.split("#", 1)[0]).exists():
                raise ValueError(f"Broken local link {path.relative_to(root)} -> {target}")
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Redocly-bundled OpenAPI JSON")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        spec = json.loads(args.bundle.read_text(encoding="utf-8"))
        operations = verify_spec(spec)
        rows = parse_catalog((root / "docs/TASK_BREAKDOWN.md").read_text(encoding="utf-8"), strict=True)
        closures = dependency_closure(rows)
        schemas = set(spec["components"]["schemas"])
        contract_names = set(operations) | schemas | {"bearerAuth", "specs/openapi.yaml", "docs/INTEGRATION.md"}
        factor_names = set(spec["components"]["schemas"]["TriageFactor"]["properties"]["name"]["enum"])
        finding_names = set(spec["components"]["schemas"]["FindingKind"]["enum"])
        produced = set()
        for name, row in rows.items():
            if len(row["cells"]) < 5:
                continue
            tokens = re.findall(r"`([^`]+)`", row["cells"][3])
            for token in tokens:
                # Slash-separated names may refer to two canonical schemas.
                for part in ([token] if token in contract_names else token.split("/")):
                    if part not in contract_names | factor_names | finding_names:
                        raise ValueError(f"Unknown contract reference {name}: {part}")
            produced.update(set(tokens) & set(operations))
        missing_operations = set(operations) - produced
        if missing_operations:
            raise ValueError(f"Unassigned operations: {sorted(missing_operations)}")
        for command in ("startProcessing", "startAnalysis", "getAnalysisRun"):
            if not any(name.startswith("U") and command in row["cells"][3] for name, row in rows.items() if len(row["cells"]) >= 5):
                raise ValueError(f"Missing UI command/status ticket {command}")
        if "A04" not in closures.get("A05", set()):
            raise ValueError("Analysis completion must depend on scoring A04")
        required_features = {name for name in rows if name.startswith(("F", "P", "A", "U"))}
        uncovered = required_features - closures.get("I09B", set())
        if uncovered:
            raise ValueError(f"Full-scope reproducibility gate misses {sorted(uncovered)}")
        handoffs = {"F08": {"P14"}, "A05": {"P14", "P14C"}, "U10": {"F06"},
                    "I01": {"F08", "F08B", "F09", "P14C", "U07B", "A15", "I00B"}}
        for task, required in handoffs.items():
            missing = required - closures.get(task, set())
            if missing:
                raise ValueError(f"Immutable/audit handoff dependency {task} misses {sorted(missing)}")
        for task in ("U12A", "U12B", "U12C", "U12D", "U12E", "U13B"):
            if "A17" not in closures.get(task, set()):
                raise ValueError(f"Assembled publication dependency {task} requires A17")
        report_missing = set(rows) - (closures.get("I06", set()) | {"I06"})
        if report_missing:
            raise ValueError(f"Final report dependency closure misses {sorted(report_missing)}")
        roadmap = (root / "docs/ROADMAP.md").read_text(encoding="utf-8")
        checkpoint_tasks = verify_phases(rows, roadmap)
        verify_transcription_handoffs(rows, closures)
        verify_runbook(rows, checkpoint_tasks,
                       (root / "docs/INTEGRATION.md").read_text(encoding="utf-8"), roadmap)
        feature_count = verify_feature_checkpoints(
            rows, checkpoint_tasks, (root / "docs/FEATURE_SCOPE.md").read_text(encoding="utf-8"))
        document_count = verify_documents(root)
        proposal = (root / "docs/PROPOSAL.md").read_text(encoding="utf-8")
        sections = [int(value) for value in re.findall(r"^## \*\*(\d+)\\?\.", proposal, re.M)]
        if sections != list(range(1, 41)):
            raise ValueError("Proposal must preserve all 40 sections in order")
        traceability = (root / "docs/PROPOSAL_TRACEABILITY.md").read_text(encoding="utf-8")
        mapped = [int(value) for value in re.findall(r"^\|\s*(\d+)\s*\|", traceability, re.M)]
        if sorted(mapped) != list(range(1, 41)):
            raise ValueError("Traceability must map each proposal section exactly once")
        for task in re.findall(TASK_ID, traceability):
            if task not in rows:
                raise ValueError(f"Unknown traceability ticket {task}")
        fixture_dir = root / "fixtures/synthetic-case"
        headers = {
            "network.csv": ["timestamp", "device_id", "ip_address", "event"],
            "gps.csv": ["timestamp", "device_id", "latitude", "longitude"],
            "messages.csv": ["message_id", "timestamp", "sender", "body"],
        }
        fixtures = {}
        for filename, expected in headers.items():
            with (fixture_dir / filename).open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                if reader.fieldnames != expected:
                    raise ValueError(f"Unexpected fixture header {filename}")
                fixtures[filename] = list(reader)
            if not fixtures[filename]:
                raise ValueError(f"Empty fixture {filename}")
            for row in fixtures[filename]:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError(f"Malformed fixture row {filename}")
                stamp = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
                if stamp.utcoffset() is None:
                    raise ValueError(f"Missing fixture timezone {filename}")
        network_devices = {row["device_id"] for row in fixtures["network.csv"]}
        gps_devices = {row["device_id"] for row in fixtures["gps.csv"]}
        if network_devices != {"D-7", "D-9"} or gps_devices != {"D-8"} or network_devices & gps_devices:
            raise ValueError("Initial tracer must not already cross-link devices")
        mentions = set(re.findall(r"\bD-\d+\b", fixtures["messages.csv"][0]["body"]))
        if mentions != {"D-7", "D-8"}:
            raise ValueError("Later tracer must introduce exactly D-7/D-8 co-mention")
        for row in fixtures["gps.csv"]:
            if not (-90 <= float(row["latitude"]) <= 90 and -180 <= float(row["longitude"]) <= 180):
                raise ValueError("Invalid fixture coordinates")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Coordination validation FAILED: {error}\n")
    print(json.dumps({
        "operations": len(operations), "tasks": len(rows), "markdown_files": document_count,
        "checkpoint_tasks": checkpoint_tasks, "feature_capabilities": feature_count,
        "proposal_sections": len(sections), "traceability_sections": len(mapped),
        "fixture_rows": {name: len(values) for name, values in fixtures.items()},
        "checks": ["local_refs", "common_errors", "task_contract_names", "dependency_DAG",
                   "UI_commands", "scoring_assembly_dependency", "full_scope_gate",
                   "immutable_processing_audit_handoff", "assembled_publication_dependencies",
                   "final_report_all_task_closure", "transcription_handoffs",
                   "exhaustive_phase_membership", "checkpoint_dependency_order", "runbook_checkpoint_gates", "feature_checkpoint_mirror",
                   "markdown_links", "whitespace", "proposal_traceability", "synthetic_fixture"],
        "scope": "planning artifacts only; no application or benchmark verification",
    }, indent=2))


if __name__ == "__main__":
    main()
