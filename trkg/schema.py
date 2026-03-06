"""
T-RKG Schema: Temporal Records Knowledge Graph

Defines the core entity types, relationship types, and governance states
for enterprise records management.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List, Any, Set


# =============================================================================
# ENUMERATIONS
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
    """Relationship types between records."""
    ATTACHMENT = "ATTACHMENT"      # Email -> Attached file
    THREAD = "THREAD"              # Message -> Reply/Forward
    DERIVATION = "DERIVATION"      # Source -> Derived document
    REFERENCE = "REFERENCE"        # Document -> Referenced document
    CONTAINER = "CONTAINER"        # Folder -> Contained record
    VERSION = "VERSION"            # Document -> Previous version
    DUPLICATE = "DUPLICATE"        # Record -> Duplicate record


class GovernanceState(Enum):
    """Current governance status of a record."""
    ACTIVE = "ACTIVE"
    RETENTION_REQUIRED = "RETENTION_REQUIRED"
    HOLD = "HOLD"
    ELIGIBLE_FOR_DELETION = "ELIGIBLE_FOR_DELETION"
    MUST_DELETE = "MUST_DELETE"
    DELETED = "DELETED"
    ARCHIVED = "ARCHIVED"


class Jurisdiction(Enum):
    """Legal jurisdictions for compliance."""
    US = "US"
    US_CA = "US_CA"  # California
    US_NY = "US_NY"  # New York
    EU = "EU"
    EU_DE = "EU_DE"  # Germany
    EU_ES = "EU_ES"  # Spain
    EU_FR = "EU_FR"  # France
    UK = "UK"
    CA = "CA"        # Canada
    GLOBAL = "GLOBAL"


class Regulation(Enum):
    """Regulatory frameworks."""
    HIPAA = "HIPAA"
    SOX = "SOX"
    SEC = "SEC"
    FINRA = "FINRA"
    GDPR = "GDPR"
    CPRA = "CPRA"
    PIPEDA = "PIPEDA"
    PCI_DSS = "PCI_DSS"
    IRS = "IRS"
    HGB = "HGB"  # German Commercial Code
    INTERNAL = "INTERNAL"


class ConflictType(Enum):
    """Types of regulatory conflicts."""
    RETENTION_DELETION = "RETENTION_DELETION"  # Must retain vs. must delete
    JURISDICTION = "JURISDICTION"              # Conflicting jurisdiction requirements
    HOLD_DELETION = "HOLD_DELETION"            # Active hold vs. deletion requirement
    PRIORITY = "PRIORITY"                      # Multiple retention periods disagree


class ConflictSeverity(Enum):
    """Severity levels for regulatory conflicts."""
    CRITICAL = "CRITICAL"   # Immediate legal risk (e.g., GDPR vs active hold)
    HIGH = "HIGH"           # Regulatory non-compliance risk
    MEDIUM = "MEDIUM"       # Potential compliance issue
    LOW = "LOW"             # Administrative priority conflict


# =============================================================================
# CORE ENTITIES
# =============================================================================

@dataclass
class Record:
    """
    A record in the knowledge graph.
    """
    id: str
    type: RecordType
    title: str

    # Temporal attributes
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

    # Classification
    contains_pii: bool = False
    contains_phi: bool = False  # Protected Health Information
    confidentiality: str = "INTERNAL"

    # Jurisdiction
    jurisdiction: Jurisdiction = Jurisdiction.US

    # Metadata (flexible key-value)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: Set[str] = field(default_factory=set)

    # Governance state (computed)
    governance_state: GovernanceState = GovernanceState.ACTIVE
    retention_deadline: Optional[datetime] = None
    hold_matters: List[str] = field(default_factory=list)
    deletion_eligible_date: Optional[datetime] = None

    # Audit
    created_in_graph: datetime = field(default_factory=datetime.now)
    last_evaluated: Optional[datetime] = None


@dataclass
class Custodian:
    """A person or entity responsible for records."""
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
    """A legal matter triggering holds."""
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
    """A source system containing records."""
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
    """A temporal relationship between two records."""
    id: str
    source_id: str
    target_id: str
    relation_type: RelationType
    valid_from: datetime
    valid_to: Optional[datetime] = None
    transaction_time: datetime = field(default_factory=datetime.now)
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_current(self) -> bool:
        now = datetime.now()
        return self.valid_from <= now and (self.valid_to is None or self.valid_to > now)


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
    """Assignment of a record to a legal hold."""
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
# GOVERNANCE RULES
# =============================================================================

@dataclass
class RetentionRule:
    """Compiled retention rule."""
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


# =============================================================================
# CONFLICT
# =============================================================================

@dataclass
class RegulatoryConflict:
    """
    A detected conflict between two regulations for a specific record.
    """
    id: str
    record_id: str
    regulation_a: Regulation
    regulation_b: Regulation
    conflict_type: ConflictType
    severity: ConflictSeverity

    # Details
    requirement_a: str = ""  # e.g., "RETAIN 7 years"
    requirement_b: str = ""  # e.g., "DELETE on request"

    # Resolution
    resolution_guidance: str = ""
    winning_regulation: Optional[Regulation] = None

    # Audit
    detected_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# GOVERNANCE EVALUATION RESULT
# =============================================================================

@dataclass
class GovernanceDecision:
    """Result of evaluating governance rules for a record."""
    record_id: str
    evaluated_at: datetime
    final_state: GovernanceState
    applicable_regulations: List[Regulation] = field(default_factory=list)
    applicable_retention_rules: List[str] = field(default_factory=list)
    applicable_hold_rules: List[str] = field(default_factory=list)
    applicable_deletion_rules: List[str] = field(default_factory=list)
    retention_deadline: Optional[datetime] = None
    earliest_deletion_date: Optional[datetime] = None
    active_holds: List[str] = field(default_factory=list)
    conflicts: List[RegulatoryConflict] = field(default_factory=list)
    explanation: List[str] = field(default_factory=list)
    winning_retention_rule: Optional[str] = None
    winning_deletion_rule: Optional[str] = None


# =============================================================================
# AUDIT LOG
# =============================================================================

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
