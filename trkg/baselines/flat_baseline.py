"""
Flat List Baseline: No graph, no indices.

Represents the simplest possible approach — records and relationships
stored as plain Python lists. Every query is a full linear scan.
Every propagation hop scans the entire relationship list.

This is a REAL baseline, not simulated. Timings are actual wall-clock.
"""

import time
from datetime import datetime
from typing import List, Set, Dict, Optional, Callable, Tuple

from trkg.schema import (
    Record, Relationship, RelationType, RecordType, Jurisdiction
)


class FlatListStore:
    """
    Baseline store using flat Python lists.

    No indices, no graph structure. All operations are linear scans.
    This represents a naive approach without any knowledge representation.
    """

    def __init__(self):
        self.records: List[Record] = []
        self.relationships: List[Relationship] = []

    def add_record(self, record: Record) -> None:
        self.records.append(record)

    def add_relationship(self, rel: Relationship) -> None:
        self.relationships.append(rel)

    def select_records(
        self,
        predicate: Callable[[Record], bool]
    ) -> List[Record]:
        """Linear scan over all records."""
        return [r for r in self.records if predicate(r)]

    def query_at_time(
        self,
        query_time: datetime,
        predicate: Optional[Callable[[Record], bool]] = None
    ) -> List[Record]:
        """Linear scan with temporal filter."""
        results = []
        for r in self.records:
            if r.created > query_time:
                continue
            if predicate is None or predicate(r):
                results.append(r)
        return results

    def propagate_hold(
        self,
        seed_record_ids: List[str],
        relation_types: List[RelationType],
        max_depth: int = -1,
        as_of: Optional[datetime] = None
    ) -> Set[str]:
        """
        BFS hold propagation over flat relationship list.

        Each hop requires a FULL SCAN of the relationship list
        to find connected records — no graph adjacency structure.
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

                # FULL SCAN of all relationships each time
                for rel in self.relationships:
                    if rel.relation_type not in relation_types:
                        continue
                    if not (rel.valid_from <= as_of and
                            (rel.valid_to is None or rel.valid_to > as_of)):
                        continue

                    if rel.source_id == record_id and rel.target_id not in visited:
                        next_frontier.add(rel.target_id)
                    elif rel.target_id == record_id and rel.source_id not in visited:
                        next_frontier.add(rel.source_id)

            frontier = next_frontier
            current_depth += 1

        return visited

    @staticmethod
    def from_trkg_store(store) -> 'FlatListStore':
        """Convert a TRKGStore to a FlatListStore for fair comparison."""
        flat = FlatListStore()
        for record in store.records.values():
            flat.add_record(record)
        for rel in store.relationships.values():
            flat.add_relationship(rel)
        return flat
