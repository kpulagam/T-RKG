"""
T-RKG Store: Graph Storage and Query Engine

Implements the temporal records knowledge graph using NetworkX
with support for bitemporal queries and governance operations.
"""

import networkx as nx
from datetime import datetime
from typing import Optional, List, Dict, Set, Any, Callable, Tuple
from collections import defaultdict
import json

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
        # Primary graph storage
        self.graph = nx.DiGraph()
        
        # Entity indices for fast lookup
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
        
        # Statistics
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
        """Add a record to the graph."""
        self.records[record.id] = record
        self.graph.add_node(record.id, entity_type="record", data=record)
        
        # Update indices
        self._records_by_type[record.type].add(record.id)
        if record.custodian_id:
            self._records_by_custodian[record.custodian_id].add(record.id)
        self._records_by_jurisdiction[record.jurisdiction].add(record.id)
        
        self.stats["records_added"] += 1
    
    def add_custodian(self, custodian: Custodian) -> None:
        """Add a custodian to the graph."""
        self.custodians[custodian.id] = custodian
        self.graph.add_node(custodian.id, entity_type="custodian", data=custodian)
    
    def add_matter(self, matter: Matter) -> None:
        """Add a legal matter to the graph."""
        self.matters[matter.id] = matter
        self.graph.add_node(matter.id, entity_type="matter", data=matter)
    
    def add_system(self, system: System) -> None:
        """Add a source system to the graph."""
        self.systems[system.id] = system
        self.graph.add_node(system.id, entity_type="system", data=system)
    
    def get_record(self, record_id: str) -> Optional[Record]:
        """Get a record by ID."""
        return self.records.get(record_id)
    
    def get_records(self, record_ids: List[str]) -> List[Record]:
        """Get multiple records by ID."""
        return [self.records[rid] for rid in record_ids if rid in self.records]
    
    # =========================================================================
    # RELATIONSHIP OPERATIONS
    # =========================================================================
    
    def add_relationship(self, rel: Relationship) -> None:
        """Add a temporal relationship between records."""
        self.relationships[rel.id] = rel
        
        # Add edge to graph
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
        direction: str = "both",  # "outgoing", "incoming", "both"
        as_of: Optional[datetime] = None
    ) -> List[Tuple[str, RelationType]]:
        """
        Get records related to the given record.
        
        Args:
            record_id: Source record ID
            relation_types: Filter by relationship types (None = all)
            direction: Edge direction to follow
            as_of: Point in time for temporal query (None = current)
        
        Returns:
            List of (record_id, relation_type) tuples
        """
        as_of = as_of or datetime.now()
        results = []
        
        if direction in ("outgoing", "both"):
            for _, target, data in self.graph.out_edges(record_id, data=True):
                rel_id = data.get("relationship_id")
                if rel_id and rel_id in self.relationships:
                    rel = self.relationships[rel_id]
                    # Check temporal validity
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
    # GRAPH TRAVERSAL (for hold propagation)
    # =========================================================================
    
    def propagate_hold(
        self,
        seed_record_ids: List[str],
        relation_types: List[RelationType],
        max_depth: int = -1,
        as_of: Optional[datetime] = None
    ) -> Set[str]:
        """
        Propagate a hold from seed records through specified relationships.
        
        This is the core algorithm for legal hold propagation.
        
        Args:
            seed_record_ids: Initial records under hold
            relation_types: Relationship types to traverse
            max_depth: Maximum traversal depth (-1 = unlimited)
            as_of: Point in time for temporal query
        
        Returns:
            Set of all record IDs that should be under hold
        """
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
                
                # Get related records through specified relationship types
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
    
    # =========================================================================
    # SELECTOR QUERIES (for DRGL execution)
    # =========================================================================
    
    def select_records(
        self,
        predicate: Callable[[Record], bool],
        record_type: Optional[RecordType] = None,
        custodian_id: Optional[str] = None,
        jurisdiction: Optional[Jurisdiction] = None,
        as_of: Optional[datetime] = None
    ) -> List[Record]:
        """
        Select records matching a predicate.
        
        Uses indices for efficient filtering before applying predicate.
        
        Args:
            predicate: Function that takes a Record and returns bool
            record_type: Optional filter by type (uses index)
            custodian_id: Optional filter by custodian (uses index)
            jurisdiction: Optional filter by jurisdiction (uses index)
            as_of: Point in time for temporal query
        
        Returns:
            List of matching records
        """
        # Start with most selective index
        if record_type:
            candidate_ids = self._records_by_type.get(record_type, set())
        elif custodian_id:
            candidate_ids = self._records_by_custodian.get(custodian_id, set())
        elif jurisdiction:
            candidate_ids = self._records_by_jurisdiction.get(jurisdiction, set())
        else:
            candidate_ids = set(self.records.keys())
        
        # Apply additional index filters
        if record_type and custodian_id:
            candidate_ids = candidate_ids & self._records_by_custodian.get(custodian_id, set())
        if jurisdiction and (record_type or custodian_id):
            candidate_ids = candidate_ids & self._records_by_jurisdiction.get(jurisdiction, set())
        
        # Apply predicate
        results = []
        for rid in candidate_ids:
            record = self.records.get(rid)
            if record and predicate(record):
                results.append(record)
        
        return results
    
    def query_by_attributes(
        self,
        conditions: Dict[str, Any],
        as_of: Optional[datetime] = None
    ) -> List[Record]:
        """
        Query records by attribute conditions.
        
        Args:
            conditions: Dict of attribute -> value or (operator, value)
                e.g., {"type": RecordType.EMAIL, "contains_pii": True}
                e.g., {"created": (">=", datetime(2024,1,1))}
        
        Returns:
            List of matching records
        """
        def matches(record: Record) -> bool:
            for attr, condition in conditions.items():
                value = getattr(record, attr, None)
                
                # Handle nested attributes (e.g., "metadata.project")
                if "." in attr:
                    parts = attr.split(".")
                    value = record
                    for part in parts:
                        if isinstance(value, dict):
                            value = value.get(part)
                        else:
                            value = getattr(value, part, None)
                        if value is None:
                            break
                
                # Handle operators
                if isinstance(condition, tuple):
                    op, target = condition
                    if op == "==" and value != target:
                        return False
                    elif op == "!=" and value == target:
                        return False
                    elif op == ">" and not (value > target):
                        return False
                    elif op == ">=" and not (value >= target):
                        return False
                    elif op == "<" and not (value < target):
                        return False
                    elif op == "<=" and not (value <= target):
                        return False
                    elif op == "in" and value not in target:
                        return False
                    elif op == "contains" and target not in str(value):
                        return False
                else:
                    # Direct equality
                    if value != condition:
                        return False
            
            return True
        
        return self.select_records(matches)
    
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
        """Apply a legal hold to records."""
        assignments = []
        
        for record_id in record_ids:
            record = self.records.get(record_id)
            if not record:
                continue
            
            # Check if already on hold for this matter
            existing = [
                ha for ha in self.hold_assignments.values()
                if ha.record_id == record_id 
                and ha.matter_id == matter_id
                and ha.released_at is None
            ]
            if existing:
                continue
            
            # Create assignment
            assignment = HoldAssignment(
                id=f"ha_{matter_id}_{record_id}_{datetime.now().timestamp()}",
                record_id=record_id,
                matter_id=matter_id,
                assignment_type=assignment_type,
                propagation_path=propagation_path or []
            )
            
            self.hold_assignments[assignment.id] = assignment
            self._records_by_matter[matter_id].add(record_id)
            
            # Update record state
            record.governance_state = GovernanceState.HOLD
            if matter_id not in record.hold_matters:
                record.hold_matters.append(matter_id)
            
            assignments.append(assignment)
            
            # Audit
            self._log_event("HOLD_APPLIED", record_id=record_id, matter_id=matter_id)
        
        self.stats["holds_applied"] += len(assignments)
        return assignments
    
    def release_hold(
        self,
        matter_id: str,
        record_ids: Optional[List[str]] = None,
        reason: str = ""
    ) -> int:
        """Release holds for a matter, optionally limited to specific records."""
        released_count = 0
        
        for ha in self.hold_assignments.values():
            if ha.matter_id != matter_id:
                continue
            if ha.released_at is not None:
                continue
            if record_ids and ha.record_id not in record_ids:
                continue
            
            # Release the hold
            ha.released_at = datetime.now()
            ha.release_reason = reason
            
            # Update record state
            record = self.records.get(ha.record_id)
            if record:
                record.hold_matters = [m for m in record.hold_matters if m != matter_id]
                if not record.hold_matters:
                    record.governance_state = GovernanceState.ACTIVE
            
            # Remove from index
            self._records_by_matter[matter_id].discard(ha.record_id)
            
            self._log_event("HOLD_RELEASED", record_id=ha.record_id, matter_id=matter_id)
            released_count += 1
        
        return released_count
    
    def get_records_on_hold(self, matter_id: str) -> List[Record]:
        """Get all records currently on hold for a matter."""
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
        """
        Query the graph state at a specific point in time.
        
        This is a simplified temporal query - full implementation would
        need transaction-time versioning of all entities.
        """
        results = []
        
        for record in self.records.values():
            # Record must exist at query time
            if record.created > query_time:
                continue
            
            # Check if deleted before query time
            if record.governance_state == GovernanceState.DELETED:
                # Would need deletion timestamp
                pass
            
            if predicate is None or predicate(record):
                results.append(record)
        
        return results
    
    def get_hold_history(self, record_id: str) -> List[HoldAssignment]:
        """Get the complete hold history for a record."""
        return [
            ha for ha in self.hold_assignments.values()
            if ha.record_id == record_id
        ]
    
    # =========================================================================
    # STATISTICS AND ANALYTICS
    # =========================================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get graph statistics."""
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
        """Count records by governance state."""
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
        """Log an audit event."""
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
    
    # =========================================================================
    # SERIALIZATION
    # =========================================================================
    
    def export_to_dict(self) -> Dict[str, Any]:
        """Export graph to dictionary for serialization."""
        return {
            "records": [self._record_to_dict(r) for r in self.records.values()],
            "custodians": [self._custodian_to_dict(c) for c in self.custodians.values()],
            "matters": [self._matter_to_dict(m) for m in self.matters.values()],
            "relationships": [self._relationship_to_dict(r) for r in self.relationships.values()],
            "hold_assignments": [self._hold_assignment_to_dict(ha) for ha in self.hold_assignments.values()],
            "statistics": self.get_statistics()
        }
    
    def _record_to_dict(self, r: Record) -> Dict:
        return {
            "id": r.id,
            "type": r.type.value,
            "title": r.title,
            "created": r.created.isoformat(),
            "modified": r.modified.isoformat(),
            "custodian_id": r.custodian_id,
            "system_id": r.system_id,
            "contains_pii": r.contains_pii,
            "jurisdiction": r.jurisdiction.value,
            "governance_state": r.governance_state.value,
            "hold_matters": r.hold_matters,
            "metadata": r.metadata,
            "tags": list(r.tags)
        }
    
    def _custodian_to_dict(self, c: Custodian) -> Dict:
        return {
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "department": c.department,
            "jurisdiction": c.jurisdiction.value
        }
    
    def _matter_to_dict(self, m: Matter) -> Dict:
        return {
            "id": m.id,
            "name": m.name,
            "matter_type": m.matter_type,
            "is_active": m.is_active,
            "custodian_ids": m.custodian_ids,
            "keywords": m.keywords
        }
    
    def _relationship_to_dict(self, r: Relationship) -> Dict:
        return {
            "id": r.id,
            "source_id": r.source_id,
            "target_id": r.target_id,
            "relation_type": r.relation_type.value,
            "valid_from": r.valid_from.isoformat(),
            "valid_to": r.valid_to.isoformat() if r.valid_to else None
        }
    
    def _hold_assignment_to_dict(self, ha: HoldAssignment) -> Dict:
        return {
            "id": ha.id,
            "record_id": ha.record_id,
            "matter_id": ha.matter_id,
            "assignment_type": ha.assignment_type,
            "propagation_path": ha.propagation_path,
            "assigned_at": ha.assigned_at.isoformat(),
            "released_at": ha.released_at.isoformat() if ha.released_at else None
        }
