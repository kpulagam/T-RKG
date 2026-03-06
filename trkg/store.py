"""
T-RKG Store: Graph Storage and Query Engine

Implements the temporal records knowledge graph using NetworkX
with support for bitemporal queries and governance operations.
"""

import networkx as nx
from datetime import datetime
from typing import Optional, List, Dict, Set, Any, Callable, Tuple
from collections import defaultdict

from trkg.schema import (
    Record, Custodian, Matter, System, Relationship, CustodianAssignment,
    HoldAssignment, RecordType, RelationType, GovernanceState, Jurisdiction,
    GovernanceDecision, AuditEvent
)


class TRKGStore:
    """
    Temporal Records Knowledge Graph Store.

    Provides storage, querying, and governance operations over
    a temporal graph of enterprise records.
    """

    def __init__(self):
        self.graph = nx.DiGraph()

        # Entity indices
        self.records: Dict[str, Record] = {}
        self.custodians: Dict[str, Custodian] = {}
        self.matters: Dict[str, Matter] = {}
        self.systems: Dict[str, System] = {}

        # Relationship storage
        self.relationships: Dict[str, Relationship] = {}
        self.custodian_assignments: Dict[str, CustodianAssignment] = {}
        self.hold_assignments: Dict[str, HoldAssignment] = {}

        # Indices for efficient queries
        self._records_by_type: Dict[RecordType, Set[str]] = defaultdict(set)
        self._records_by_custodian: Dict[str, Set[str]] = defaultdict(set)
        self._records_by_matter: Dict[str, Set[str]] = defaultdict(set)
        self._records_by_jurisdiction: Dict[Jurisdiction, Set[str]] = defaultdict(set)

        # Audit log
        self.audit_log: List[AuditEvent] = []

        self.stats = {
            "records_added": 0,
            "relationships_added": 0,
            "holds_applied": 0,
            "evaluations_performed": 0
        }

    # =========================================================================
    # ENTITY OPERATIONS
    # =========================================================================

    def add_record(self, record: Record) -> None:
        self.records[record.id] = record
        self.graph.add_node(record.id, entity_type="record", data=record)
        self._records_by_type[record.type].add(record.id)
        if record.custodian_id:
            self._records_by_custodian[record.custodian_id].add(record.id)
        self._records_by_jurisdiction[record.jurisdiction].add(record.id)
        self.stats["records_added"] += 1

    def add_custodian(self, custodian: Custodian) -> None:
        self.custodians[custodian.id] = custodian
        self.graph.add_node(custodian.id, entity_type="custodian", data=custodian)

    def add_matter(self, matter: Matter) -> None:
        self.matters[matter.id] = matter
        self.graph.add_node(matter.id, entity_type="matter", data=matter)

    def add_system(self, system: System) -> None:
        self.systems[system.id] = system
        self.graph.add_node(system.id, entity_type="system", data=system)

    def get_record(self, record_id: str) -> Optional[Record]:
        return self.records.get(record_id)

    def get_records(self, record_ids: List[str]) -> List[Record]:
        return [self.records[rid] for rid in record_ids if rid in self.records]

    # =========================================================================
    # RELATIONSHIP OPERATIONS
    # =========================================================================

    def add_relationship(self, rel: Relationship) -> None:
        self.relationships[rel.id] = rel
        self.graph.add_edge(
            rel.source_id,
            rel.target_id,
            relationship_id=rel.id,
            relation_type=rel.relation_type,
            valid_from=rel.valid_from,
            valid_to=rel.valid_to
        )
        self.stats["relationships_added"] += 1

    def get_related_records(
        self,
        record_id: str,
        relation_types: Optional[List[RelationType]] = None,
        direction: str = "both",
        as_of: Optional[datetime] = None
    ) -> List[Tuple[str, RelationType]]:
        as_of = as_of or datetime.now()
        results = []

        if direction in ("outgoing", "both"):
            for _, target, data in self.graph.out_edges(record_id, data=True):
                rel_id = data.get("relationship_id")
                if rel_id and rel_id in self.relationships:
                    rel = self.relationships[rel_id]
                    if rel.valid_from <= as_of and (rel.valid_to is None or rel.valid_to > as_of):
                        if relation_types is None or rel.relation_type in relation_types:
                            results.append((target, rel.relation_type))

        if direction in ("incoming", "both"):
            for source, _, data in self.graph.in_edges(record_id, data=True):
                rel_id = data.get("relationship_id")
                if rel_id and rel_id in self.relationships:
                    rel = self.relationships[rel_id]
                    if rel.valid_from <= as_of and (rel.valid_to is None or rel.valid_to > as_of):
                        if relation_types is None or rel.relation_type in relation_types:
                            results.append((source, rel.relation_type))

        return results

    # =========================================================================
    # GRAPH TRAVERSAL (hold propagation)
    # =========================================================================

    def propagate_hold(
        self,
        seed_record_ids: List[str],
        relation_types: List[RelationType],
        max_depth: int = -1,
        as_of: Optional[datetime] = None
    ) -> Set[str]:
        as_of = as_of or datetime.now()
        visited: Set[str] = set()
        frontier: Set[str] = set(seed_record_ids)
        current_depth = 0

        while frontier and (max_depth == -1 or current_depth < max_depth):
            next_frontier: Set[str] = set()
            for record_id in frontier:
                if record_id in visited:
                    continue
                visited.add(record_id)
                related = self.get_related_records(
                    record_id,
                    relation_types=relation_types,
                    direction="both",
                    as_of=as_of
                )
                for related_id, _ in related:
                    if related_id not in visited:
                        next_frontier.add(related_id)
            frontier = next_frontier
            current_depth += 1

        return visited

    def propagate_hold_with_paths(
        self,
        seed_record_ids: List[str],
        relation_types: List[RelationType],
        max_depth: int = -1,
        as_of: Optional[datetime] = None
    ) -> Dict[str, List[Tuple[str, RelationType]]]:
        """Propagate hold and return paths for each reached record."""
        as_of = as_of or datetime.now()
        # Maps record_id -> path of (record_id, relation_type) from seed
        paths: Dict[str, List[Tuple[str, RelationType]]] = {}
        for sid in seed_record_ids:
            if sid in self.records:
                paths[sid] = []

        frontier = set(seed_record_ids) & set(self.records.keys())
        visited: Set[str] = set()
        current_depth = 0
        depth_counts: Dict[int, int] = {0: len(frontier)}

        while frontier and (max_depth == -1 or current_depth < max_depth):
            next_frontier: Set[str] = set()
            for record_id in frontier:
                if record_id in visited:
                    continue
                visited.add(record_id)
                related = self.get_related_records(
                    record_id, relation_types=relation_types,
                    direction="both", as_of=as_of
                )
                for related_id, rel_type in related:
                    if related_id not in visited and related_id not in paths:
                        paths[related_id] = paths.get(record_id, []) + [(record_id, rel_type)]
                        next_frontier.add(related_id)

            frontier = next_frontier
            current_depth += 1
            if next_frontier:
                depth_counts[current_depth] = len(next_frontier)

        return paths

    # =========================================================================
    # SELECTOR QUERIES
    # =========================================================================

    def select_records(
        self,
        predicate: Callable[[Record], bool],
        record_type: Optional[RecordType] = None,
        custodian_id: Optional[str] = None,
        jurisdiction: Optional[Jurisdiction] = None,
    ) -> List[Record]:
        if record_type:
            candidate_ids = self._records_by_type.get(record_type, set())
        elif custodian_id:
            candidate_ids = self._records_by_custodian.get(custodian_id, set())
        elif jurisdiction:
            candidate_ids = self._records_by_jurisdiction.get(jurisdiction, set())
        else:
            candidate_ids = set(self.records.keys())

        if record_type and custodian_id:
            candidate_ids = candidate_ids & self._records_by_custodian.get(custodian_id, set())
        if jurisdiction and (record_type or custodian_id):
            candidate_ids = candidate_ids & self._records_by_jurisdiction.get(jurisdiction, set())

        results = []
        for rid in candidate_ids:
            record = self.records.get(rid)
            if record and predicate(record):
                results.append(record)
        return results

    # =========================================================================
    # HOLD MANAGEMENT
    # =========================================================================

    def apply_hold(
        self,
        matter_id: str,
        record_ids: List[str],
        assignment_type: str = "DIRECT",
        propagation_path: Optional[List[str]] = None
    ) -> List[HoldAssignment]:
        assignments = []
        for record_id in record_ids:
            record = self.records.get(record_id)
            if not record:
                continue
            existing = [
                ha for ha in self.hold_assignments.values()
                if ha.record_id == record_id
                and ha.matter_id == matter_id
                and ha.released_at is None
            ]
            if existing:
                continue
            assignment = HoldAssignment(
                id=f"ha_{matter_id}_{record_id}_{datetime.now().timestamp()}",
                record_id=record_id,
                matter_id=matter_id,
                assignment_type=assignment_type,
                propagation_path=propagation_path or []
            )
            self.hold_assignments[assignment.id] = assignment
            self._records_by_matter[matter_id].add(record_id)
            record.governance_state = GovernanceState.HOLD
            if matter_id not in record.hold_matters:
                record.hold_matters.append(matter_id)
            assignments.append(assignment)
            self._log_event("HOLD_APPLIED", record_id=record_id, matter_id=matter_id)

        self.stats["holds_applied"] += len(assignments)
        return assignments

    def release_hold(
        self,
        matter_id: str,
        record_ids: Optional[List[str]] = None,
        reason: str = ""
    ) -> int:
        released_count = 0
        for ha in self.hold_assignments.values():
            if ha.matter_id != matter_id or ha.released_at is not None:
                continue
            if record_ids and ha.record_id not in record_ids:
                continue
            ha.released_at = datetime.now()
            ha.release_reason = reason
            record = self.records.get(ha.record_id)
            if record:
                record.hold_matters = [m for m in record.hold_matters if m != matter_id]
                if not record.hold_matters:
                    record.governance_state = GovernanceState.ACTIVE
            self._records_by_matter[matter_id].discard(ha.record_id)
            self._log_event("HOLD_RELEASED", record_id=ha.record_id, matter_id=matter_id)
            released_count += 1
        return released_count

    def get_records_on_hold(self, matter_id: str) -> List[Record]:
        record_ids = self._records_by_matter.get(matter_id, set())
        return [self.records[rid] for rid in record_ids if rid in self.records]

    # =========================================================================
    # TEMPORAL QUERIES
    # =========================================================================

    def query_at_time(
        self,
        query_time: datetime,
        predicate: Optional[Callable[[Record], bool]] = None
    ) -> List[Record]:
        results = []
        for record in self.records.values():
            if record.created > query_time:
                continue
            if predicate is None or predicate(record):
                results.append(record)
        return results

    def get_hold_history(self, record_id: str) -> List[HoldAssignment]:
        return [
            ha for ha in self.hold_assignments.values()
            if ha.record_id == record_id
        ]

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "total_records": len(self.records),
            "total_relationships": len(self.relationships),
            "total_custodians": len(self.custodians),
            "total_matters": len(self.matters),
            "active_holds": sum(
                1 for ha in self.hold_assignments.values()
                if ha.released_at is None
            ),
            "records_by_type": {
                rt.value: len(ids) for rt, ids in self._records_by_type.items()
            },
            "records_by_jurisdiction": {
                j.value: len(ids) for j, ids in self._records_by_jurisdiction.items()
            },
            "records_by_state": self._count_by_state(),
            "graph_density": nx.density(self.graph) if self.graph.number_of_nodes() > 0 else 0,
            "operations": self.stats
        }

    def _count_by_state(self) -> Dict[str, int]:
        counts = defaultdict(int)
        for record in self.records.values():
            counts[record.governance_state.value] += 1
        return dict(counts)

    # =========================================================================
    # AUDIT LOGGING
    # =========================================================================

    def _log_event(
        self,
        event_type: str,
        record_id: Optional[str] = None,
        matter_id: Optional[str] = None,
        rule_id: Optional[str] = None,
        details: Optional[Dict] = None
    ) -> None:
        event = AuditEvent(
            id=f"evt_{datetime.now().timestamp()}",
            timestamp=datetime.now(),
            event_type=event_type,
            record_id=record_id,
            matter_id=matter_id,
            rule_id=rule_id,
            details=details or {}
        )
        self.audit_log.append(event)
