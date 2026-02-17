"""
T-RKG Schema: Core Data Model

Defines the entity types, relationship types, and governance states
for enterprise records management with formal ontological grounding.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List, Any, Set


# =============================================================================
# ENUMERATIONS (Mapped to OWL individuals)
# =============================================================================

class RecordType(Enum):
    """Categories of records in enterprise systems."""
    EMAIL = "EMAIL"
    DOCUMENT = "DOCUMENT"
    CHAT = "CHAT"
    ATTACHMENT = "ATTACHMENT"
    SPREADSHEET = "SPREADSHEET"
    PRESENTATION = "PRESENTATION"
    CONTRACT = "CONTRACT"
    INVOICE = "INVOICE"
    MEDICAL = "MEDICAL"
    FINANCIAL = "FINANCIAL"
    TAX = "TAX"
    AUDIT = "AUDIT"
    WORKPAPER = "WORKPAPER"
    LOG = "LOG"
    TICKET = "TICKET"
    OTHER = "OTHER"


class RelationType(Enum):
    """Relationship types between records (OWL: RecordRelationship subclasses)."""
    ATTACHMENT = "ATTACHMENT"      # Email -> Attached file
    THREAD = "THREAD"              # Message -> Reply/Forward
    DERIVATION = "DERIVATION"      # Source -> Derived document
    REFERENCE = "REFERENCE"        # Document -> Referenced document
    CONTAINER = "CONTAINER"        # Folder -> Contained record
    VERSION = "VERSION"            # Document -> Previous version
    DUPLICATE = "DUPLICATE"        # Record -> Duplicate record


class GovernanceState(Enum):
    """Current governance status of a record (OWL: GovernanceState individuals)."""
    ACTIVE = "ACTIVE"
    RETENTION_REQUIRED = "RETENTION_REQUIRED"
    HOLD = "HOLD"
    ELIGIBLE_FOR_DELETION = "ELIGIBLE_FOR_DELETION"
    MUST_DELETE = "MUST_DELETE"
    DELETED = "DELETED"
    ARCHIVED = "ARCHIVED"


class Jurisdiction(Enum):
    """Legal jurisdictions for compliance (OWL: Jurisdiction individuals)."""
    US = "US"
    US_CA = "US_CA"
    US_NY = "US_NY"
    EU = "EU"
    EU_DE = "EU_DE"
    EU_ES = "EU_ES"
    EU_FR = "EU_FR"
    UK = "UK"
    CA = "CA"
    GLOBAL = "GLOBAL"


class Regulation(Enum):
    """Regulatory frameworks (OWL: Regulation individuals)."""
    HIPAA = "HIPAA"
    SOX = "SOX"
    SEC = "SEC"
    FINRA = "FINRA"
    GDPR = "GDPR"
    CPRA = "CPRA"
    PIPEDA = "PIPEDA"
    PCI_DSS = "PCI_DSS"
    IRS = "IRS"
    HGB = "HGB"
    INTERNAL = "INTERNAL"


# =============================================================================
# CORE ENTITIES
# =============================================================================

@dataclass
class Record:
    """
    A record in the knowledge graph (OWL: Record class).
    
    Records are the primary entities representing documents, emails,
    chat messages, and other information objects subject to governance.
    """
    id: str
    type: RecordType
    title: str
    
    # Temporal attributes (OWL: validFrom, validTo, transactionTime)
    created: datetime
    modified: datetime
    accessed: Optional[datetime] = None
    
    # Ownership and location
    custodian_id: str = ""
    system_id: str = ""
    container_id: Optional[str] = None
    
    # Content attributes
    content_hash: str = ""
    size_bytes: int = 0
    mime_type: str = ""
    
    # Classification (OWL: containsPII, containsPHI)
    contains_pii: bool = False
    contains_phi: bool = False
    confidentiality: str = "INTERNAL"
    
    # Jurisdiction (OWL: locatedIn)
    jurisdiction: Jurisdiction = Jurisdiction.US
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: Set[str] = field(default_factory=set)
    
    # Governance state (computed, OWL: hasGovernanceState)
    governance_state: GovernanceState = GovernanceState.ACTIVE
    retention_deadline: Optional[datetime] = None
    hold_matters: List[str] = field(default_factory=list)
    deletion_eligible_date: Optional[datetime] = None
    
    # Audit
    created_in_graph: datetime = field(default_factory=datetime.now)
    last_evaluated: Optional[datetime] = None


@dataclass
class Custodian:
    """A person or entity responsible for records (OWL: Custodian class)."""
    id: str
    name: str
    email: str
    department: str = ""
    title: str = ""
    manager_id: Optional[str] = None
    location: str = ""
    jurisdiction: Jurisdiction = Jurisdiction.US
    is_active: bool = True
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Matter:
    """A legal matter triggering holds (OWL: Matter class)."""
    id: str
    name: str
    description: str = ""
    matter_type: str = "LITIGATION"
    created: datetime = field(default_factory=datetime.now)
    hold_start: Optional[datetime] = None
    hold_end: Optional[datetime] = None
    is_active: bool = True
    custodian_ids: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None
    case_number: str = ""
    counsel: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class System:
    """A source system containing records (OWL: System class)."""
    id: str
    name: str
    system_type: str
    vendor: str = ""
    connection_string: str = ""
    last_sync: Optional[datetime] = None
    default_jurisdiction: Jurisdiction = Jurisdiction.US
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# RELATIONSHIPS
# =============================================================================

@dataclass
class Relationship:
    """
    A temporal relationship between two records.
    
    OWL: RecordRelationship class with subclasses for each type.
    Relationships enable hold propagation based on ontology semantics.
    """
    id: str
    source_id: str
    target_id: str
    relation_type: RelationType
    
    # Bitemporal (OWL: validFrom, validTo, transactionTime)
    valid_from: datetime
    valid_to: Optional[datetime] = None
    transaction_time: datetime = field(default_factory=datetime.now)
    
    # Metadata
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_current(self) -> bool:
        now = datetime.now()
        valid_from = self.valid_from
        valid_to = self.valid_to
        # Handle timezone-aware datetimes
        if hasattr(valid_from, 'tzinfo') and valid_from.tzinfo is not None:
            valid_from = valid_from.replace(tzinfo=None)
        if valid_to and hasattr(valid_to, 'tzinfo') and valid_to.tzinfo is not None:
            valid_to = valid_to.replace(tzinfo=None)
        return valid_from <= now and (valid_to is None or valid_to > now)


@dataclass 
class CustodianAssignment:
    """Temporal assignment of a custodian to a record."""
    id: str
    record_id: str
    custodian_id: str
    valid_from: datetime
    valid_to: Optional[datetime] = None
    assignment_type: str = "OWNER"
    transaction_time: datetime = field(default_factory=datetime.now)


@dataclass
class HoldAssignment:
    """Assignment of a record to a legal hold (OWL: underHoldFor)."""
    id: str
    record_id: str
    matter_id: str
    assignment_type: str = "DIRECT"
    propagation_path: List[str] = field(default_factory=list)
    propagation_relation: Optional[RelationType] = None
    assigned_at: datetime = field(default_factory=datetime.now)
    released_at: Optional[datetime] = None
    assigned_by: str = ""
    release_reason: str = ""


# =============================================================================
# GOVERNANCE
# =============================================================================

@dataclass
class GovernanceDecision:
    """Result of evaluating governance rules for a record."""
    record_id: str
    evaluated_at: datetime
    final_state: GovernanceState
    applicable_retention_rules: List[str] = field(default_factory=list)
    applicable_hold_rules: List[str] = field(default_factory=list)
    applicable_deletion_rules: List[str] = field(default_factory=list)
    retention_deadline: Optional[datetime] = None
    earliest_deletion_date: Optional[datetime] = None
    active_holds: List[str] = field(default_factory=list)
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    explanation: List[str] = field(default_factory=list)
    winning_retention_rule: Optional[str] = None
    winning_deletion_rule: Optional[str] = None


@dataclass
class AuditEvent:
    """Audit log entry for governance actions."""
    id: str
    timestamp: datetime
    event_type: str
    record_id: Optional[str] = None
    matter_id: Optional[str] = None
    rule_id: Optional[str] = None
    actor: str = "SYSTEM"
    before_state: Optional[GovernanceState] = None
    after_state: Optional[GovernanceState] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetentionRule:
    """Compiled retention rule (OWL: derived from Regulation properties)."""
    id: str
    name: str
    selector_expr: str
    duration_days: int
    trigger: str
    regulation: Optional[Regulation] = None
    jurisdiction: Optional[Jurisdiction] = None
    priority: int = 0
    source_text: str = ""
    citation: str = ""


@dataclass
class HoldRule:
    """Compiled hold rule."""
    id: str
    matter_id: str
    selector_expr: str
    propagate_via: List[RelationType] = field(default_factory=list)
    propagation_depth: int = -1
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None
    is_active: bool = True
    source_text: str = ""


@dataclass
class DeletionRule:
    """Compiled deletion rule."""
    id: str
    name: str
    rule_type: str
    selector_expr: str
    condition_expr: str = ""
    unless_expr: str = ""
    regulation: Optional[Regulation] = None
    jurisdiction: Optional[Jurisdiction] = None
    priority: int = 0
    source_text: str = ""
    citation: str = ""
