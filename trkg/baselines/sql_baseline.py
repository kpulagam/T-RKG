"""
SQLite Baseline: Relational database approach.

Records in a table, relationships in a junction table.
Hold propagation via recursive CTE. Queries via SQL.

This is a REAL baseline with actual SQLite operations.
"""

import sqlite3
import time
from datetime import datetime
from typing import List, Set, Dict, Optional, Callable
from trkg.schema import Record, Relationship, RelationType, RecordType, Jurisdiction


class SQLiteStore:
    """
    Baseline store using SQLite relational database.

    Represents a traditional RDBMS approach to records governance.
    """

    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS records (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                title TEXT,
                created TEXT NOT NULL,
                modified TEXT NOT NULL,
                custodian_id TEXT,
                system_id TEXT,
                jurisdiction TEXT,
                contains_pii INTEGER DEFAULT 0,
                contains_phi INTEGER DEFAULT 0,
                confidentiality TEXT DEFAULT 'INTERNAL',
                governance_state TEXT DEFAULT 'ACTIVE',
                is_public_company INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS relationships (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                valid_from TEXT NOT NULL,
                valid_to TEXT,
                FOREIGN KEY (source_id) REFERENCES records(id),
                FOREIGN KEY (target_id) REFERENCES records(id)
            );

            CREATE INDEX IF NOT EXISTS idx_records_type ON records(type);
            CREATE INDEX IF NOT EXISTS idx_records_custodian ON records(custodian_id);
            CREATE INDEX IF NOT EXISTS idx_records_jurisdiction ON records(jurisdiction);
            CREATE INDEX IF NOT EXISTS idx_rel_source ON relationships(source_id);
            CREATE INDEX IF NOT EXISTS idx_rel_target ON relationships(target_id);
            CREATE INDEX IF NOT EXISTS idx_rel_type ON relationships(relation_type);
        """)
        self.conn.commit()

    def add_record(self, record: Record) -> None:
        is_public = 0
        if record.metadata.get("is_public_company"):
            is_public = 1
        elif isinstance(record.metadata.get("company"), dict):
            is_public = 1 if record.metadata["company"].get("is_public") else 0

        self.conn.execute(
            """INSERT OR REPLACE INTO records
               (id, type, title, created, modified, custodian_id, system_id,
                jurisdiction, contains_pii, contains_phi, confidentiality,
                governance_state, is_public_company)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (record.id, record.type.value, record.title,
             record.created.isoformat(), record.modified.isoformat(),
             record.custodian_id, record.system_id,
             record.jurisdiction.value,
             1 if record.contains_pii else 0,
             1 if record.contains_phi else 0,
             record.confidentiality,
             record.governance_state.value,
             is_public)
        )

    def add_relationship(self, rel: Relationship) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO relationships
               (id, source_id, target_id, relation_type, valid_from, valid_to)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (rel.id, rel.source_id, rel.target_id,
             rel.relation_type.value, rel.valid_from.isoformat(),
             rel.valid_to.isoformat() if rel.valid_to else None)
        )

    def commit(self):
        self.conn.commit()

    def select_records_by_type(self, record_type: RecordType) -> List[str]:
        """SQL query by type."""
        cursor = self.conn.execute(
            "SELECT id FROM records WHERE type = ?",
            (record_type.value,)
        )
        return [row[0] for row in cursor.fetchall()]

    def query_at_time(self, query_time: datetime) -> List[str]:
        """SQL temporal query."""
        cursor = self.conn.execute(
            "SELECT id FROM records WHERE created <= ?",
            (query_time.isoformat(),)
        )
        return [row[0] for row in cursor.fetchall()]

    def propagate_hold(
        self,
        seed_record_ids: List[str],
        relation_types: List[RelationType],
        max_depth: int = 5,
        as_of: Optional[datetime] = None
    ) -> Set[str]:
        """
        Hold propagation using recursive CTE.

        This is the standard SQL approach to graph traversal.
        """
        as_of = as_of or datetime.now()
        as_of_str = as_of.isoformat()
        rel_type_list = ",".join(f"'{rt.value}'" for rt in relation_types)

        # Build seed list as a VALUES clause
        if not seed_record_ids:
            return set()

        seed_values = ",".join(f"('{sid}')" for sid in seed_record_ids)

        # Recursive CTE for graph traversal
        # max_depth is enforced by the depth counter
        query = f"""
            WITH RECURSIVE hold_propagation(record_id, depth) AS (
                -- Base case: seed records
                SELECT column1 as record_id, 0 as depth
                FROM (VALUES {seed_values})

                UNION

                -- Recursive case: follow relationships
                SELECT
                    CASE
                        WHEN r.source_id = hp.record_id THEN r.target_id
                        ELSE r.source_id
                    END as record_id,
                    hp.depth + 1 as depth
                FROM hold_propagation hp
                JOIN relationships r ON (
                    r.source_id = hp.record_id OR r.target_id = hp.record_id
                )
                WHERE hp.depth < {max_depth}
                  AND r.relation_type IN ({rel_type_list})
                  AND r.valid_from <= '{as_of_str}'
                  AND (r.valid_to IS NULL OR r.valid_to > '{as_of_str}')
            )
            SELECT DISTINCT record_id FROM hold_propagation
        """

        try:
            cursor = self.conn.execute(query)
            return {row[0] for row in cursor.fetchall()}
        except sqlite3.OperationalError:
            # Fallback: iterative approach if CTE fails
            return self._propagate_iterative(
                seed_record_ids, relation_types, max_depth, as_of_str, rel_type_list
            )

    def _propagate_iterative(
        self, seeds, relation_types, max_depth, as_of_str, rel_type_list
    ) -> Set[str]:
        """Fallback iterative propagation using individual SQL queries per hop."""
        visited: Set[str] = set()
        frontier: Set[str] = set(seeds)
        depth = 0

        while frontier and depth < max_depth:
            next_frontier: Set[str] = set()
            for rid in frontier:
                if rid in visited:
                    continue
                visited.add(rid)

                cursor = self.conn.execute(
                    f"""SELECT source_id, target_id FROM relationships
                        WHERE (source_id = ? OR target_id = ?)
                          AND relation_type IN ({rel_type_list})
                          AND valid_from <= ?
                          AND (valid_to IS NULL OR valid_to > ?)""",
                    (rid, rid, as_of_str, as_of_str)
                )
                for src, tgt in cursor.fetchall():
                    neighbor = tgt if src == rid else src
                    if neighbor not in visited:
                        next_frontier.add(neighbor)

            frontier = next_frontier
            depth += 1

        return visited

    def close(self):
        self.conn.close()

    @staticmethod
    def from_trkg_store(store) -> 'SQLiteStore':
        """Convert a TRKGStore to SQLiteStore for fair comparison."""
        sql_store = SQLiteStore()
        for record in store.records.values():
            sql_store.add_record(record)
        for rel in store.relationships.values():
            sql_store.add_relationship(rel)
        sql_store.commit()
        return sql_store
