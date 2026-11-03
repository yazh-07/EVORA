"""G01D private graph connection/schema harness; no analysis publication or scoring.

Projection schema v1: Node nodes and Edge relationships retain source IDs within
case/run partitions. A01B owns validated writes/rebuilds; A05 owns SQL publication.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
import math
import os
from urllib.parse import urlsplit

from neo4j import Driver, GraphDatabase, Query, Session
from neo4j.exceptions import DriverError, Neo4jError


class GraphDatabaseError(RuntimeError):
    """Safe internal graph failure; never carries credentials or driver messages."""


class Neo4jUnavailableError(GraphDatabaseError):
    """Connection, authentication or configured-database access failed closed."""


@dataclass(frozen=True, kw_only=True)
class Neo4jConfig:
    """Backend-only configuration. Load explicitly; imports never open sockets."""

    password: str = field(repr=False)
    uri: str = field(default="bolt://127.0.0.1:7687", repr=False)
    user: str = "neo4j"
    database: str = "neo4j"
    connection_timeout: float = 1.0

    def __post_init__(self) -> None:
        # No credentials, query parameters or paths in the URI. Values are never
        # included in errors, including urllib's validation diagnostics.
        valid_uri = False
        if isinstance(self.uri, str) and not any(c.isspace() for c in self.uri):
            try:
                parsed = urlsplit(self.uri)
                valid_uri = (
                    parsed.scheme in {"bolt", "bolt+s", "bolt+ssc", "neo4j", "neo4j+s", "neo4j+ssc"}
                    and bool(parsed.hostname)
                    and parsed.username is None and parsed.password is None
                    and not parsed.path and not parsed.query and not parsed.fragment
                    and (parsed.port is None or 0 < parsed.port <= 65535)
                )
            except ValueError:
                pass
        if not valid_uri:
            raise GraphDatabaseError("Invalid Neo4j URI configuration.") from None
        for name in ("user", "database", "password"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or "\x00" in value:
                raise GraphDatabaseError("Neo4j credentials and database are required.")
        if (isinstance(self.connection_timeout, bool)
                or not isinstance(self.connection_timeout, (int, float))
                or not 0 < self.connection_timeout <= 2.0
                or not math.isfinite(self.connection_timeout)):
            raise GraphDatabaseError("Neo4j timeout must be finite and in (0, 2] seconds.")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Neo4jConfig":
        env = os.environ if environ is None else environ
        try:
            timeout = float(env.get("NEO4J_CONNECTION_TIMEOUT", "1.0"))
        except (TypeError, ValueError):
            raise GraphDatabaseError("Invalid Neo4j timeout configuration.") from None
        return cls(
            uri=env.get("NEO4J_URI", "bolt://127.0.0.1:7687"),
            user=env.get("NEO4J_USER", "neo4j"),
            password=env.get("NEO4J_PASSWORD", ""),
            database=env.get("NEO4J_DATABASE", "neo4j"),
            connection_timeout=timeout,
        )


# Static DDL has no input values to parameterize. Labels, relationship types and
# property names are internal schema, never interpolated from callers or evidence.
SCHEMA_VERSION = "evora-graph/1"
SCHEMA_STATEMENTS = (
    "CREATE CONSTRAINT evora_node_identity_v1 IF NOT EXISTS "
    "FOR (n:Node) REQUIRE (n.case_id, n.analysis_run_id, n.id) IS UNIQUE",
    "CREATE CONSTRAINT evora_edge_identity_v1 IF NOT EXISTS "
    "FOR ()-[e:Edge]-() REQUIRE (e.case_id, e.analysis_run_id, e.id) IS UNIQUE",
    "CREATE INDEX evora_node_partition_v1 IF NOT EXISTS "
    "FOR (n:Node) ON (n.case_id, n.analysis_run_id)",
    "CREATE INDEX evora_node_source_v1 IF NOT EXISTS "
    "FOR (n:Node) ON (n.case_id, n.id)",
    "CREATE INDEX evora_edge_partition_v1 IF NOT EXISTS "
    "FOR ()-[e:Edge]-() ON (e.case_id, e.analysis_run_id)",
    "CREATE INDEX evora_edge_source_v1 IF NOT EXISTS "
    "FOR ()-[e:Edge]-() ON (e.case_id, e.id)",
)

_CONNECTION_ERRORS = (DriverError, Neo4jError, OSError)


class Neo4jGraphDatabase:
    """One explicitly owned driver. Use/close serially in the backend lifecycle.

    Acquisition bounds include Bolt handshake/authentication in driver 6.4.1.
    Transaction timeouts require a responsive server; they are not OS deadlines
    for arbitrary DNS resolution or a server that stalls after acquisition.
    """

    def __init__(self, config: Neo4jConfig | None = None) -> None:
        self.config = Neo4jConfig.from_env() if config is None else config
        self._driver: Driver | None = None

    def get_driver(self) -> Driver:
        """Lazily create/reuse a driver; creation alone is not connectivity proof."""
        if self._driver is None:
            try:
                self._driver = GraphDatabase.driver(
                    self.config.uri,
                    auth=(self.config.user, self.config.password),
                    database=self.config.database,
                    connection_timeout=self.config.connection_timeout,
                    connection_acquisition_timeout=self.config.connection_timeout,
                    connection_write_timeout=self.config.connection_timeout,
                    max_transaction_retry_time=0.0,
                    disable_auto_commit_retries=True,
                    telemetry_disabled=True,
                )
            except _CONNECTION_ERRORS:
                raise Neo4jUnavailableError("Graph database is unavailable.") from None
        return self._driver

    def close(self) -> None:
        """Release the owned driver; repeated close is harmless, reuse is lazy."""
        driver, self._driver = self._driver, None
        if driver is not None:
            try:
                driver.close()
            except _CONNECTION_ERRORS:
                raise GraphDatabaseError("Graph database cleanup failed.") from None

    def verify_connectivity(self) -> bool:
        """Verify transport/auth and access to the configured database, or raise."""
        try:
            # A real query checks the configured database as well as Bolt/auth;
            # driver.verify_connectivity's database keyword is a preview API.
            with self.get_driver().session(database=self.config.database) as session:
                session.run(Query("RETURN 1 AS connected", timeout=self.config.connection_timeout)).consume()
        except _CONNECTION_ERRORS:
            raise Neo4jUnavailableError("Graph database is unavailable.") from None
        return True

    def setup_schema(self, session: Session) -> None:
        """Create v1 constraints/indexes using a caller-owned configured session.

        DDL auto-commits individually. A failure is never setup success; safely
        rerun all statements after recovery. This does not publish any graph.
        """
        try:
            for statement in SCHEMA_STATEMENTS:
                session.run(Query(statement, timeout=self.config.connection_timeout)).consume()
        except (DriverError, OSError):
            raise Neo4jUnavailableError("Graph database is unavailable.") from None
        except Neo4jError:
            raise GraphDatabaseError("Graph schema setup failed.") from None
