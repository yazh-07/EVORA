"""A01B authoritative SQL outputs and recoverable evora-graph/1 projection.

The caller owns authorization and acceptance of a frozen run. SQLiteDatabase
and G01D Neo4jGraphDatabase own connections. No routes or implicit identities.
"""
from datetime import datetime, timezone
import hashlib
import json
import math

from backend.errors import AccessError
from backend.graph_db import GraphDatabaseError
from backend.graph_nodes import _uuid, build_graph_nodes
from backend.triage.aggregation import sort_triage_results


class ProjectionError(GraphDatabaseError):
    """Sanitized failure, safe for callers; no driver/source diagnostics."""


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def initialize_graph_projection(db):
    """Initialize storage only. Never reset or publish interrupted runs.

    A05 must insert authenticated acceptance metadata before invoking projection;
    it can extend analysis_runs with trigger/algorithm/request fingerprint fields.
    """
    with db.connect() as connection:
        connection.executescript("""
          BEGIN IMMEDIATE;
          CREATE TABLE IF NOT EXISTS analysis_runs (
            id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
            actor_id TEXT NOT NULL, key_digest TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('queued','running','completed','failed')),
            input_snapshot_json TEXT NOT NULL, error TEXT,
            created_at TEXT NOT NULL, finished_at TEXT,
            UNIQUE(actor_id,case_id,key_digest),
            CHECK((status IN ('queued','running') AND finished_at IS NULL AND error IS NULL)
              OR (status='completed' AND finished_at IS NOT NULL AND error IS NULL)
              OR (status='failed' AND finished_at IS NOT NULL AND length(error)>0 AND error IS NOT NULL)));
          CREATE TABLE IF NOT EXISTS analysis_outputs (
            run_id TEXT PRIMARY KEY REFERENCES analysis_runs(id), case_id TEXT NOT NULL,
            graph_json TEXT NOT NULL, findings_json TEXT NOT NULL, triage_json TEXT NOT NULL);
          CREATE TRIGGER IF NOT EXISTS analysis_run_frozen BEFORE UPDATE OF
            id,case_id,actor_id,key_digest,input_snapshot_json,created_at ON analysis_runs
            BEGIN SELECT RAISE(ABORT,'Frozen analysis acceptance'); END;
          CREATE TRIGGER IF NOT EXISTS analysis_run_terminal BEFORE UPDATE ON analysis_runs
            WHEN OLD.status IN ('completed','failed')
            BEGIN SELECT RAISE(ABORT,'Immutable terminal analysis run'); END;
          CREATE TRIGGER IF NOT EXISTS analysis_run_transition BEFORE UPDATE OF status ON analysis_runs
            WHEN NOT ((OLD.status='queued' AND NEW.status IN ('running','failed'))
              OR (OLD.status='running' AND NEW.status IN ('completed','failed')))
            BEGIN SELECT RAISE(ABORT,'Invalid analysis transition'); END;
          CREATE TRIGGER IF NOT EXISTS analysis_run_no_delete BEFORE DELETE ON analysis_runs
            BEGIN SELECT RAISE(ABORT,'Immutable analysis history'); END;
          CREATE TRIGGER IF NOT EXISTS analysis_run_no_replace BEFORE INSERT ON analysis_runs
            WHEN EXISTS(SELECT 1 FROM analysis_runs WHERE id=NEW.id OR rowid=NEW.rowid
              OR (actor_id=NEW.actor_id AND case_id=NEW.case_id AND key_digest=NEW.key_digest))
            BEGIN SELECT RAISE(ABORT,'Immutable analysis history'); END;
          CREATE TRIGGER IF NOT EXISTS analysis_output_context BEFORE INSERT ON analysis_outputs
            WHEN NOT EXISTS(SELECT 1 FROM analysis_runs WHERE id=NEW.run_id
              AND case_id=NEW.case_id AND status='running')
            BEGIN SELECT RAISE(ABORT,'Invalid analysis output context'); END;
          CREATE TRIGGER IF NOT EXISTS analysis_output_no_update BEFORE UPDATE ON analysis_outputs
            BEGIN SELECT RAISE(ABORT,'Immutable analysis output'); END;
          CREATE TRIGGER IF NOT EXISTS analysis_output_no_delete BEFORE DELETE ON analysis_outputs
            BEGIN SELECT RAISE(ABORT,'Immutable analysis output'); END;
          CREATE TRIGGER IF NOT EXISTS analysis_output_no_replace BEFORE INSERT ON analysis_outputs
            WHEN EXISTS(SELECT 1 FROM analysis_outputs WHERE run_id=NEW.run_id OR rowid=NEW.rowid)
            BEGIN SELECT RAISE(ABORT,'Immutable analysis output'); END;
          CREATE TRIGGER IF NOT EXISTS analysis_completion_output BEFORE UPDATE OF status ON analysis_runs
            WHEN NEW.status='completed' AND NOT EXISTS(SELECT 1 FROM analysis_outputs
              WHERE run_id=NEW.id AND case_id=NEW.case_id)
            BEGIN SELECT RAISE(ABORT,'Missing analysis output'); END;
          COMMIT;
        """)


def _run(connection, case_id, run_id):
    _uuid(case_id, "case_id")
    _uuid(run_id, "analysis_run_id")
    row = connection.execute("SELECT * FROM analysis_runs WHERE id=? AND case_id=?",
                             (run_id, case_id)).fetchone()
    if row is None:
        raise AccessError(404, "NOT_FOUND", "Resource not found.")
    return row


def _stored(connection, run):
    row = connection.execute("SELECT * FROM analysis_outputs WHERE run_id=? AND case_id=?",
                             (run["id"], run["case_id"])).fetchone()
    if row is None:
        raise ValueError("Missing authoritative analysis output")
    return tuple(row[key] for key in ("graph_json", "findings_json", "triage_json"))


def _refs(record, field, allowed, *, nonempty=True):
    values = record.get(field)
    if (not isinstance(values, list) or (nonempty and not values)
            or any(_uuid(value, field) not in allowed for value in values)
            or len(set(values)) != len(values)):
        raise ValueError("Invalid analysis source references")
    return set(values)


def _validate(connection, run, graph, findings, triage):
    """Join frozen sources to real completed SQL records, not caller allowlists."""
    case, run_id = run["case_id"], run["id"]
    snapshot = json.loads(run["input_snapshot_json"])
    fields = {"case_id", "evidence_ids", "processing_run_ids", "observation_ids"}
    if set(snapshot) != fields | {"sha256"} or snapshot["case_id"] != case:
        raise ValueError("Invalid frozen analysis snapshot")
    for field in fields - {"case_id"}:
        values = snapshot[field]
        if not isinstance(values, list) or values != sorted(set(values)):
            raise ValueError("Invalid frozen analysis membership")
        for value in values:
            _uuid(value, field)
    manifest = {key: snapshot[key] for key in fields}
    # CONTRACTS canonicalization uses json.dumps' default ASCII escaping.
    digest = hashlib.sha256(json.dumps(manifest, sort_keys=True,
        separators=(",", ":")).encode("utf-8")).hexdigest()
    if digest != snapshot["sha256"]:
        raise ValueError("Invalid frozen analysis digest")
    evidence = []
    for eid in snapshot["evidence_ids"]:
        row = connection.execute("SELECT * FROM evidence WHERE id=? AND case_id=?", (eid, case)).fetchone()
        if row is None:
            raise ValueError("Invalid frozen evidence source")
        evidence.append(dict(row))
    observations, entities, events, selected_evidence = {}, [], [], set()
    for pid in snapshot["processing_run_ids"]:
        row = connection.execute("SELECT o.* FROM processing_outputs o JOIN processing_runs r ON r.id=o.run_id "
            "AND r.case_id=o.case_id AND r.evidence_id=o.evidence_id "
            "WHERE r.id=? AND r.case_id=? AND r.status='completed'", (pid, case)).fetchone()
        if (row is None or row["evidence_id"] not in snapshot["evidence_ids"]
                or row["evidence_id"] in selected_evidence):
            raise ValueError("Invalid frozen processing source")
        selected_evidence.add(row["evidence_id"])
        for observation in json.loads(row["observations_json"]):
            oid = observation["id"]
            if (observation["case_id"] != case or observation["processing_run_id"] != pid
                    or observation["evidence_id"] != row["evidence_id"] or oid in observations
                    or not observation["source_locator"].strip()):
                raise ValueError("Invalid frozen observation source")
            observations[oid] = observation
        entities.extend(json.loads(row["entities_json"]))
        events.extend(json.loads(row["events_json"]))
    if set(observations) != set(snapshot["observation_ids"]):
        raise ValueError("Analysis observations differ from frozen snapshot")
    source_nodes = {node.id: node.to_wire() for node in build_graph_nodes(case, evidence, entities, events)}
    if (not isinstance(graph, dict) or set(graph) != {"case_id", "analysis_run_id", "nodes", "edges"}
            or graph["case_id"] != case or graph["analysis_run_id"] != run_id
            or not isinstance(graph["nodes"], list) or not isinstance(graph["edges"], list)
            or not isinstance(findings, list) or not isinstance(triage, list)):
        raise ValueError("Invalid analysis output context")
    nodes = {}
    for node in graph["nodes"]:
        if node != source_nodes.get(node.get("id")) or node["id"] in nodes:
            raise ValueError("Graph node differs from frozen source")
        nodes[node["id"]] = node
    evidence_ids = set(snapshot["evidence_ids"])

    def sourced(record):
        if record.get("case_id") != case:
            raise ValueError("Foreign analysis output")
        _uuid(record.get("id"), "id")
        sources = _refs(record, "evidence_ids", evidence_ids)
        cited = _refs(record, "observation_ids", observations)
        if sources != {observations[oid]["evidence_id"] for oid in cited}:
            raise ValueError("Analysis citations do not match evidence sources")
        confidence = record.get("confidence")
        if (isinstance(confidence, bool) or not isinstance(confidence, (int, float))
                or not math.isfinite(confidence) or not 0 <= confidence <= 1):
            raise ValueError("Invalid analysis confidence")

    seen = set()
    for edge in graph["edges"]:
        sourced(edge)
        if (set(edge) != {"id", "case_id", "from_id", "to_id", "kind", "confidence",
                          "evidence_ids", "observation_ids"}
                or not isinstance(edge["kind"], str) or not edge["kind"].strip()
                or edge["id"] in seen or edge["from_id"] not in nodes or edge["to_id"] not in nodes):
            raise ValueError("Invalid graph edge or endpoints")
        seen.add(edge["id"])
    seen = set()
    entity_ids = {entity["id"] for entity in entities}
    for finding in findings:
        sourced(finding)
        if finding.get("analysis_run_id") != run_id or finding["id"] in seen:
            raise ValueError("Invalid finding run or duplicate ID")
        seen.add(finding["id"])
        for field, allowed in (("entity_ids", entity_ids), ("contradicting_evidence_ids", evidence_ids)):
            if field in finding:
                _refs(finding, field, allowed, nonempty=False)
    sort_triage_results(triage, evidence_ids)  # Includes duplicate evidence/run/score controls.
    seen = set()
    observed = {item["evidence_id"] for item in observations.values()}
    for result in triage:
        if (result["case_id"] != case or result["analysis_run_id"] != run_id
                or result["evidence_id"] not in observed or result["id"] in seen):
            raise ValueError("Invalid triage source or run")
        seen.add(_uuid(result["id"], "triage.id"))
        for factor in result["factors"]:
            _refs(factor, "evidence_ids", evidence_ids, nonempty=False)


_DELETE_EDGES = "MATCH ()-[r:Edge {case_id:$case_id, analysis_run_id:$run_id}]->() DELETE r"
_DELETE_NODES = "MATCH (n:Node {case_id:$case_id, analysis_run_id:$run_id}) DELETE n"
_WRITE_NODE = """UNWIND $nodes AS node
 MERGE (n:Node {case_id:$case_id, analysis_run_id:$run_id, id:node.id})
 SET n.kind=node.kind, n.label=node.label, n.evidence_ids=node.evidence_ids"""
_WRITE_EDGE = """UNWIND $edges AS edge
 MATCH (a:Node {case_id:$case_id, analysis_run_id:$run_id, id:edge.from_id}),
 (b:Node {case_id:$case_id, analysis_run_id:$run_id, id:edge.to_id})
 MERGE (a)-[r:Edge {case_id:$case_id, analysis_run_id:$run_id, id:edge.id}]->(b)
 SET r.kind=edge.kind, r.confidence=edge.confidence, r.evidence_ids=edge.evidence_ids,
 r.observation_ids=edge.observation_ids"""
_COUNT_NODES = "MATCH (n:Node {case_id:$case_id, analysis_run_id:$run_id}) RETURN count(n) AS count"
_COUNT_EDGES = "MATCH ()-[r:Edge {case_id:$case_id, analysis_run_id:$run_id}]->() RETURN count(r) AS count"
_READ_NODES = """MATCH (n:Node {case_id:$case_id, analysis_run_id:$run_id})
 RETURN n{.id,.case_id,.kind,.label,.evidence_ids} AS node"""
_READ_EDGES = """MATCH (a)-[r:Edge {case_id:$case_id, analysis_run_id:$run_id}]->(b)
 RETURN r{.id,.case_id,.kind,.confidence,.evidence_ids,.observation_ids} AS edge,
 a.id AS from_id, b.id AS to_id, a.case_id AS from_case, b.case_id AS to_case,
 a.analysis_run_id AS from_run, b.analysis_run_id AS to_run,
 labels(a) AS from_labels, labels(b) AS to_labels"""


def _verify(tx, graph):
    params = dict(case_id=graph["case_id"], run_id=graph["analysis_run_id"])
    for query, items in ((_COUNT_NODES, graph["nodes"]), (_COUNT_EDGES, graph["edges"])):
        if tx.run(query, **params).single(strict=True)["count"] != len(items):
            raise ProjectionError("Graph projection verification failed.")
    nodes = [row["node"] for row in tx.run(_READ_NODES, **params).data()]
    edges = []
    for row in tx.run(_READ_EDGES, **params).data():
        if (row["from_case"] != params["case_id"] or row["to_case"] != params["case_id"]
                or row["from_run"] != params["run_id"] or row["to_run"] != params["run_id"]
                or "Node" not in row["from_labels"] or "Node" not in row["to_labels"]):
            raise ProjectionError("Graph projection verification failed.")
        edges.append(row["edge"] | dict(from_id=row["from_id"], to_id=row["to_id"]))
    for actual, expected in ((nodes, graph["nodes"]), (edges, graph["edges"])):
        if sorted(actual, key=_json) != sorted(expected, key=_json):
            raise ProjectionError("Graph projection verification failed.")


def _project(neo4j_db, graph, *, rewrite):
    """One Neo4j transaction, independent of SQL commit. All queries parameterized."""
    try:
        with neo4j_db.get_driver().session(database=neo4j_db.config.database) as session:
            if rewrite:
                neo4j_db.setup_schema(session)
            with session.begin_transaction(timeout=neo4j_db.config.connection_timeout) as tx:
                params = dict(case_id=graph["case_id"], run_id=graph["analysis_run_id"])
                if rewrite:
                    # Replace only this partition, atomically removing stale data.
                    # DELETE (not DETACH) refuses to damage foreign relationships.
                    tx.run(_DELETE_EDGES, **params).consume()
                    tx.run(_DELETE_NODES, **params).consume()
                    tx.run(_WRITE_NODE, **params, nodes=graph["nodes"]).consume()
                    tx.run(_WRITE_EDGE, **params, edges=graph["edges"]).consume()
                _verify(tx, graph)
                tx.commit()
    except Exception:
        raise ProjectionError("Graph projection unavailable or incoherent.") from None


def project_analysis_run(db, neo4j_db, *, case_id: str, analysis_run_id: str,
                         graph: dict, findings: list[dict], triage: list[dict]) -> None:
    """Commit SQL candidate -> write/verify Neo4j -> publish SQL completion.

    Repeat running/completed calls require identical immutable output. Failed
    resources stay terminal; A05 same-key replay must never execute them again.
    A crash (including after graph commit) leaves running output hidden; a worker
    may resume this function using its original SQL outputs. No resnapshot here.
    """
    serialized = tuple(_json(value) for value in (graph, findings, triage))
    # Detach from caller-owned mutable containers before verification/persistence.
    graph, findings, triage = map(json.loads, serialized)
    with db.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        run = _run(connection, case_id, analysis_run_id)
        if run["status"] == "failed":
            raise ValueError("Failed analysis runs remain terminal")
        _validate(connection, run, graph, findings, triage)
        existing = connection.execute("SELECT 1 FROM analysis_outputs WHERE run_id=?", (analysis_run_id,)).fetchone()
        if existing:
            if _stored(connection, run) != serialized:
                raise ValueError("Immutable analysis output differs")
        else:
            if run["status"] != "queued":
                raise ValueError("Missing persisted analysis output")
            connection.execute("UPDATE analysis_runs SET status='running' WHERE id=?", (analysis_run_id,))
            connection.execute("INSERT INTO analysis_outputs VALUES (?,?,?,?,?)",
                               (analysis_run_id, case_id, *serialized))
    try:
        # SQLite write lock serializes project/rebuild/read helpers across workers.
        # This is a local worker lock, NOT a transaction shared with Neo4j.
        with db.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            run = _run(connection, case_id, analysis_run_id)
            if run["status"] not in {"running", "completed"}:
                raise ValueError("Analysis run is no longer projectable")
            _project(neo4j_db, graph, rewrite=run["status"] == "running")
            if run["status"] == "running":
                connection.execute("UPDATE analysis_runs SET status='completed',finished_at=? WHERE id=?",
                                   (_now(), analysis_run_id))
    except Exception:
        try:
            with db.connect() as connection:
                connection.execute("UPDATE analysis_runs SET status='failed',finished_at=?,error=? "
                    "WHERE id=? AND case_id=? AND status='running'",
                    (_now(), "GRAPH_PROJECTION_FAILED", analysis_run_id, case_id))
        except Exception:
            # A failed SQL failure-accounting write leaves running output hidden;
            # the original immutable output remains available for restart recovery.
            raise ProjectionError("Graph projection failed; SQL recovery is required.") from None
        raise ProjectionError("Graph projection failed.") from None


def rebuild_graph_partition(db, neo4j_db, *, case_id: str, analysis_run_id: str) -> bool:
    """Restore exactly the immutable SQL version; never change run publication.

    False means Neo4j could not be restored. Missing/foreign resources raise the
    same 404. Failed/running partitions can be repaired but remain hidden.
    """
    with db.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        run = _run(connection, case_id, analysis_run_id)
        graph, findings, triage = map(json.loads, _stored(connection, run))
        _validate(connection, run, graph, findings, triage)
        try:
            _project(neo4j_db, graph, rewrite=True)
        except ProjectionError:
            return False
    return True


def get_projected_graph(db, neo4j_db, *, case_id: str, analysis_run_id: str) -> dict:
    """Read SQL's completed version only, refusing unavailable/corrupt Neo4j.

    Caller must apply F00 case access. A05B owns selector defaults/HTTP wiring;
    there is no silent fallback to another run or a stale graph.
    """
    with db.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        run = _run(connection, case_id, analysis_run_id)
        if run["status"] != "completed":
            raise AccessError(404, "NOT_FOUND", "Resource not found.")
        graph, findings, triage = map(json.loads, _stored(connection, run))
        _validate(connection, run, graph, findings, triage)
        _project(neo4j_db, graph, rewrite=False)
        return graph
