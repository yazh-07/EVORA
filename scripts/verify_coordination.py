"""Validate planning artifacts; never reports application correctness."""
import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import re

TASK_ID = r"\b[GFPAUI]\d{2}[A-Z]?\b"


def parse_catalog(text):
    """Read setup and bounded task rows from the Markdown catalog."""
    rows = {}
    for number, line in enumerate(text.splitlines(), 1):
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or not re.fullmatch(TASK_ID, cells[0]):
            continue
        task_id = cells[0]
        if len(cells) not in (4, 5):
            raise ValueError(f"Malformed task row {task_id} at line {number}")
        if task_id in rows:
            raise ValueError(f"Duplicate task ID {task_id}")
        dependencies = set(re.findall(TASK_ID, cells[2])) if len(cells) == 5 else set()
        rows[task_id] = {"line": number, "cells": cells, "dependencies": dependencies}
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
    if len(operations) != 25:
        raise ValueError(f"Expected preserved 25 operationIds, got {len(operations)}")

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
        rows = parse_catalog((root / "docs/TASK_BREAKDOWN.md").read_text(encoding="utf-8"))
        closures = dependency_closure(rows)
        schemas = set(spec["components"]["schemas"])
        contract_names = set(operations) | schemas | {"bearerAuth", "specs/openapi.yaml", "docs/INTEGRATION.md"}
        factor_names = set(spec["components"]["schemas"]["TriageFactor"]["properties"]["name"]["enum"])
        finding_names = set(spec["components"]["schemas"]["FindingKind"]["enum"])
        produced = set()
        for name, row in rows.items():
            if len(row["cells"]) != 5:
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
            if not any(name.startswith("U") and command in row["cells"][3] for name, row in rows.items() if len(row["cells"]) == 5):
                raise ValueError(f"Missing UI command/status ticket {command}")
        if "A04" not in closures.get("A05", set()):
            raise ValueError("Analysis completion must depend on scoring A04")
        required_features = {name for name in rows if name.startswith(("F", "P", "A", "U"))}
        uncovered = required_features - closures.get("I09B", set())
        if uncovered:
            raise ValueError(f"Full-scope reproducibility gate misses {sorted(uncovered)}")
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
        "proposal_sections": len(sections), "traceability_sections": len(mapped),
        "fixture_rows": {name: len(values) for name, values in fixtures.items()},
        "checks": ["local_refs", "common_errors", "task_contract_names", "dependency_DAG",
                   "UI_commands", "scoring_assembly_dependency", "full_scope_gate",
                   "markdown_links", "whitespace", "proposal_traceability", "synthetic_fixture"],
        "scope": "planning artifacts only; no application or benchmark verification",
    }, indent=2))


if __name__ == "__main__":
    main()
