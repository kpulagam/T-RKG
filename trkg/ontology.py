"""
T-RKG Ontology Module - Python wrapper for OWL ontology.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from trkg.schema import Regulation, Jurisdiction


class RecordsGovernanceOntology:
    """Python interface to the T-RKG Records Governance Ontology."""
    
    ONTOLOGY_URI = "http://purl.org/trkg/ontology"
    
    def __init__(self, owl_path: Optional[str] = None):
        self.owl_path = owl_path or self._get_default_owl_path()
        
        self.regulations: Dict[str, Dict[str, Any]] = {}
        self.jurisdictions: Dict[str, Dict[str, Any]] = {}
        self.relationship_types: Dict[str, Dict[str, Any]] = {}
        self.governance_states: Dict[str, Dict[str, Any]] = {}
        self.conflict_types: Dict[str, Dict[str, Any]] = {}
        
        self.regulation_jurisdictions: Dict[str, List[str]] = {}
        self.jurisdiction_hierarchy: Dict[str, Optional[str]] = {}
        
        self._load_builtin_definitions()
    
    def _get_default_owl_path(self) -> str:
        module_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(module_dir, "..", "ontology", "records_governance.owl")
    
    def _load_builtin_definitions(self):
        self.regulations = {
            "SOX": {"label": "Sarbanes-Oxley Act", "retention_days": 2555, "grants_deletion_right": False, "jurisdictions": ["US", "US_CA", "US_NY"]},
            "GDPR": {"label": "GDPR", "retention_days": None, "grants_deletion_right": True, "jurisdictions": ["EU", "EU_DE", "EU_FR", "UK"]},
            "HIPAA": {"label": "HIPAA", "retention_days": 2190, "grants_deletion_right": False, "jurisdictions": ["US", "US_CA", "US_NY"]},
            "SEC": {"label": "SEC Rules", "retention_days": 2190, "grants_deletion_right": False, "jurisdictions": ["US", "US_CA", "US_NY"]},
            "HGB": {"label": "German Commercial Code", "retention_days": 3650, "grants_deletion_right": False, "jurisdictions": ["EU_DE"]},
            "CPRA": {"label": "CPRA", "retention_days": None, "grants_deletion_right": True, "jurisdictions": ["US_CA"]},
            "PIPEDA": {"label": "PIPEDA", "retention_days": None, "grants_deletion_right": True, "jurisdictions": ["CA"]},
            "IRS": {"label": "IRS Requirements", "retention_days": 2555, "grants_deletion_right": False, "jurisdictions": ["US", "US_CA", "US_NY"]},
        }
        
        self.jurisdictions = {
            "US": {"label": "United States", "parent": None},
            "US_CA": {"label": "California", "parent": "US"},
            "US_NY": {"label": "New York", "parent": "US"},
            "EU": {"label": "European Union", "parent": None},
            "EU_DE": {"label": "Germany", "parent": "EU"},
            "EU_FR": {"label": "France", "parent": "EU"},
            "UK": {"label": "United Kingdom", "parent": None},
            "CA": {"label": "Canada", "parent": None},
        }
        
        self.relationship_types = {
            "ATTACHMENT": {"label": "Attachment", "propagates_hold": True},
            "THREAD": {"label": "Thread", "propagates_hold": True},
            "DERIVATION": {"label": "Derivation", "propagates_hold": True},
            "REFERENCE": {"label": "Reference", "propagates_hold": False},
        }
        
        self.governance_states = {
            "ACTIVE": {"label": "Active"},
            "HOLD": {"label": "Hold"},
            "RETENTION_REQUIRED": {"label": "Retention Required"},
            "ELIGIBLE_FOR_DELETION": {"label": "Eligible for Deletion"},
            "MUST_DELETE": {"label": "Must Delete"},
            "DELETED": {"label": "Deleted"},
        }
        
        for reg_name, reg_info in self.regulations.items():
            self.regulation_jurisdictions[reg_name] = reg_info.get("jurisdictions", [])
        
        for j_name, j_info in self.jurisdictions.items():
            self.jurisdiction_hierarchy[j_name] = j_info.get("parent")
    
    def get_regulations_for_jurisdiction(self, jurisdiction: str) -> List[str]:
        applicable = []
        for reg_name, reg_info in self.regulations.items():
            if jurisdiction in reg_info.get("jurisdictions", []):
                applicable.append(reg_name)
        return applicable
    
    def get_retention_requirement(self, regulation: str) -> Optional[int]:
        if regulation in self.regulations:
            return self.regulations[regulation].get("retention_days")
        return None
    
    def grants_deletion_right(self, regulation: str) -> bool:
        if regulation in self.regulations:
            return self.regulations[regulation].get("grants_deletion_right", False)
        return False
    
    def propagates_hold(self, relationship_type: str) -> bool:
        if relationship_type in self.relationship_types:
            return self.relationship_types[relationship_type].get("propagates_hold", False)
        return False
    
    def get_parent_jurisdiction(self, jurisdiction: str) -> Optional[str]:
        return self.jurisdiction_hierarchy.get(jurisdiction)
    
    def get_all_parent_jurisdictions(self, jurisdiction: str) -> List[str]:
        parents = []
        current = jurisdiction
        while current:
            parent = self.get_parent_jurisdiction(current)
            if parent:
                parents.append(parent)
            current = parent
        return parents
    
    def get_statistics(self) -> Dict[str, Any]:
        return {
            "num_regulations": len(self.regulations),
            "num_jurisdictions": len(self.jurisdictions),
            "num_relationship_types": len(self.relationship_types),
            "num_governance_states": len(self.governance_states),
            "regulations_with_retention": sum(1 for r in self.regulations.values() if r.get("retention_days")),
            "regulations_with_deletion_right": sum(1 for r in self.regulations.values() if r.get("grants_deletion_right")),
        }
    
    def export_to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.ONTOLOGY_URI,
            "regulations": self.regulations,
            "jurisdictions": self.jurisdictions,
            "relationship_types": self.relationship_types,
            "governance_states": self.governance_states,
            "statistics": self.get_statistics()
        }


def load_ontology(owl_path: Optional[str] = None) -> RecordsGovernanceOntology:
    return RecordsGovernanceOntology(owl_path)


def get_ontology_statistics() -> Dict[str, Any]:
    return load_ontology().get_statistics()
