"""
Synthetic Data Generator for T-RKG Experiments

Generates realistic enterprise records, relationships, and governance scenarios.
"""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass

from trkg.schema import (
    Record, Custodian, Matter, System, Relationship,
    RecordType, RelationType, GovernanceState, Jurisdiction
)
from trkg.store import TRKGStore


@dataclass
class GeneratorConfig:
    num_emails: int = 4000
    num_documents: int = 3000
    num_chats: int = 1500
    num_tickets: int = 500
    num_contracts: int = 500
    num_financial: int = 500
    attachment_ratio: float = 0.15
    thread_ratio: float = 0.30
    derivation_ratio: float = 0.05
    reference_ratio: float = 0.08
    num_custodians: int = 100
    num_departments: int = 10
    num_matters: int = 5
    start_date: datetime = datetime(2020, 1, 1)
    end_date: datetime = datetime(2024, 12, 31)
    pii_probability: float = 0.15
    phi_probability: float = 0.05
    jurisdiction_weights: Dict[Jurisdiction, float] = None

    def __post_init__(self):
        if self.jurisdiction_weights is None:
            self.jurisdiction_weights = {
                Jurisdiction.US: 0.60,
                Jurisdiction.US_CA: 0.10,
                Jurisdiction.EU: 0.15,
                Jurisdiction.EU_DE: 0.05,
                Jurisdiction.UK: 0.05,
                Jurisdiction.CA: 0.05
            }


DEPARTMENTS = [
    "Engineering", "Sales", "Marketing", "Finance", "Legal",
    "HR", "Operations", "Product", "Customer Success", "Executive"
]
PROJECTS = [
    "Phoenix", "Atlas", "Titan", "Mercury", "Apollo",
    "Artemis", "Voyager", "Pioneer", "Horizon", "Nexus"
]
TOPICS = [
    "quarterly review", "budget planning", "product launch",
    "customer feedback", "security audit", "compliance review",
    "team meeting", "project update", "performance review",
    "training session", "vendor contract", "partnership discussion"
]
FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer",
    "Michael", "Linda", "William", "Elizabeth", "David", "Barbara",
    "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah",
    "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa"
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
    "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez",
    "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore"
]


class SyntheticDataGenerator:
    def __init__(self, config: Optional[GeneratorConfig] = None, seed: int = 42):
        self.config = config or GeneratorConfig()
        random.seed(seed)
        self.store = TRKGStore()
        self._custodian_ids: List[str] = []
        self._record_ids_by_type: Dict[RecordType, List[str]] = {}
        self._email_ids: List[str] = []
        self._document_ids: List[str] = []

    def generate(self) -> TRKGStore:
        self._generate_systems()
        self._generate_custodians()
        self._generate_records()
        self._generate_relationships()
        self._generate_matters()
        return self.store

    def _generate_systems(self):
        systems = [
            ("sys_email", "Exchange Online", "EMAIL", "Microsoft"),
            ("sys_dms", "SharePoint", "DMS", "Microsoft"),
            ("sys_chat", "Slack", "CHAT", "Slack"),
            ("sys_crm", "Salesforce", "CRM", "Salesforce"),
            ("sys_erp", "SAP", "ERP", "SAP"),
        ]
        for sys_id, name, sys_type, vendor in systems:
            self.store.add_system(System(id=sys_id, name=name, system_type=sys_type, vendor=vendor))

    def _generate_custodians(self):
        for i in range(self.config.num_custodians):
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            dept = random.choice(DEPARTMENTS)
            custodian = Custodian(
                id=f"emp_{i:04d}",
                name=f"{first} {last}",
                email=f"{first.lower()}.{last.lower()}@acme.com",
                department=dept,
                title=self._random_title(dept),
                jurisdiction=self._random_jurisdiction(),
                start_date=self._random_date(datetime(2015, 1, 1), datetime(2023, 1, 1))
            )
            self.store.add_custodian(custodian)
            self._custodian_ids.append(custodian.id)

    def _random_title(self, department: str) -> str:
        levels = ["Associate", "Senior", "Lead", "Principal", "Director", "VP"]
        roles = {
            "Engineering": ["Software Engineer", "Data Engineer", "DevOps Engineer"],
            "Sales": ["Account Executive", "Sales Rep", "Business Development"],
            "Marketing": ["Marketing Manager", "Content Strategist", "Growth Manager"],
            "Finance": ["Financial Analyst", "Accountant", "Controller"],
            "Legal": ["Counsel", "Paralegal", "Compliance Officer"],
            "HR": ["HR Business Partner", "Recruiter", "HR Manager"],
            "Operations": ["Operations Manager", "Project Manager", "Analyst"],
            "Product": ["Product Manager", "Product Owner", "UX Designer"],
            "Customer Success": ["Customer Success Manager", "Support Engineer"],
            "Executive": ["CEO", "CFO", "CTO", "COO", "General Manager"]
        }
        if department == "Executive":
            return random.choice(roles[department])
        level = random.choice(levels[:4])
        role = random.choice(roles.get(department, ["Specialist"]))
        return f"{level} {role}"

    def _generate_records(self):
        self._generate_emails()
        self._generate_documents()
        self._generate_chats()
        self._generate_tickets()
        self._generate_contracts()
        self._generate_financial_records()

    def _generate_emails(self):
        for i in range(self.config.num_emails):
            created = self._random_date()
            custodian = random.choice(self._custodian_ids)
            project = random.choice(PROJECTS) if random.random() < 0.3 else None
            topic = random.choice(TOPICS)
            record = Record(
                id=f"email_{i:06d}",
                type=RecordType.EMAIL,
                title=f"Re: {topic.title()}" if random.random() < 0.4 else topic.title(),
                created=created,
                modified=created + timedelta(minutes=random.randint(0, 60)),
                custodian_id=custodian,
                system_id="sys_email",
                contains_pii=random.random() < self.config.pii_probability,
                contains_phi=random.random() < self.config.phi_probability,
                jurisdiction=self._get_custodian_jurisdiction(custodian),
                metadata={
                    "subject": topic,
                    "has_attachments": random.random() < 0.2,
                    "thread_id": f"thread_{i // 5}" if random.random() < 0.5 else None
                },
                tags=set([project] if project else [])
            )
            self.store.add_record(record)
            self._email_ids.append(record.id)
            self._record_ids_by_type.setdefault(RecordType.EMAIL, []).append(record.id)

    def _generate_documents(self):
        doc_types = [
            ("Report", ".docx"), ("Presentation", ".pptx"),
            ("Spreadsheet", ".xlsx"), ("PDF", ".pdf"),
            ("Memo", ".docx"), ("Proposal", ".docx")
        ]
        for i in range(self.config.num_documents):
            created = self._random_date()
            custodian = random.choice(self._custodian_ids)
            doc_type, ext = random.choice(doc_types)
            project = random.choice(PROJECTS) if random.random() < 0.4 else None
            record = Record(
                id=f"doc_{i:06d}",
                type=RecordType.DOCUMENT,
                title=f"{project + ' ' if project else ''}{doc_type} - {created.strftime('%Y%m%d')}{ext}",
                created=created,
                modified=created + timedelta(days=random.randint(0, 30)),
                custodian_id=custodian,
                system_id="sys_dms",
                contains_pii=random.random() < self.config.pii_probability,
                jurisdiction=self._get_custodian_jurisdiction(custodian),
                mime_type=self._mime_for_ext(ext),
                metadata={"version": random.randint(1, 5), "project": project},
                tags=set([project] if project else [])
            )
            self.store.add_record(record)
            self._document_ids.append(record.id)
            self._record_ids_by_type.setdefault(RecordType.DOCUMENT, []).append(record.id)

    def _generate_chats(self):
        channels = ["#general", "#engineering", "#sales", "#random", "#project-phoenix", "#project-atlas"]
        for i in range(self.config.num_chats):
            created = self._random_date()
            custodian = random.choice(self._custodian_ids)
            record = Record(
                id=f"chat_{i:06d}",
                type=RecordType.CHAT,
                title=f"Message in {random.choice(channels)}",
                created=created, modified=created,
                custodian_id=custodian, system_id="sys_chat",
                contains_pii=random.random() < 0.05,
                jurisdiction=self._get_custodian_jurisdiction(custodian),
                metadata={"channel": random.choice(channels), "has_mentions": random.random() < 0.3}
            )
            self.store.add_record(record)
            self._record_ids_by_type.setdefault(RecordType.CHAT, []).append(record.id)

    def _generate_tickets(self):
        for i in range(self.config.num_tickets):
            created = self._random_date()
            custodian = random.choice(self._custodian_ids)
            record = Record(
                id=f"ticket_{i:05d}",
                type=RecordType.TICKET,
                title=f"TICKET-{i:05d}: Support Request",
                created=created,
                modified=created + timedelta(days=random.randint(0, 14)),
                custodian_id=custodian, system_id="sys_crm",
                contains_pii=random.random() < 0.4,
                contains_phi=random.random() < self.config.phi_probability,
                jurisdiction=self._get_custodian_jurisdiction(custodian),
                metadata={"status": random.choice(["open", "closed", "pending"]),
                          "priority": random.choice(["low", "medium", "high", "critical"])}
            )
            self.store.add_record(record)
            self._record_ids_by_type.setdefault(RecordType.TICKET, []).append(record.id)

    def _generate_contracts(self):
        legal_sales_exec = [c for c in self._custodian_ids
                            if self.store.custodians[c].department in ["Legal", "Sales", "Executive"]]
        if not legal_sales_exec:
            legal_sales_exec = self._custodian_ids
        for i in range(self.config.num_contracts):
            created = self._random_date()
            custodian = random.choice(legal_sales_exec)
            record = Record(
                id=f"contract_{i:05d}",
                type=RecordType.CONTRACT,
                title=f"Contract - Vendor {i:03d}",
                created=created,
                modified=created + timedelta(days=random.randint(0, 7)),
                custodian_id=custodian, system_id="sys_dms",
                contains_pii=True, confidentiality="CONFIDENTIAL",
                jurisdiction=self._get_custodian_jurisdiction(custodian),
                metadata={"contract_type": random.choice(["NDA", "MSA", "SOW", "License", "Employment"]),
                          "value": random.randint(10000, 10000000),
                          "term_years": random.randint(1, 5)}
            )
            self.store.add_record(record)
            self._record_ids_by_type.setdefault(RecordType.CONTRACT, []).append(record.id)

    def _generate_financial_records(self):
        fin_types = [
            (RecordType.FINANCIAL, "Financial Statement"),
            (RecordType.AUDIT, "Audit Workpaper"),
            (RecordType.TAX, "Tax Document"),
            (RecordType.INVOICE, "Invoice")
        ]
        finance_custodians = [c for c in self._custodian_ids
                              if self.store.custodians[c].department == "Finance"]
        if not finance_custodians:
            finance_custodians = self._custodian_ids
        for i in range(self.config.num_financial):
            created = self._random_date()
            custodian = random.choice(finance_custodians)
            rec_type, title_prefix = random.choice(fin_types)
            record = Record(
                id=f"fin_{i:05d}",
                type=rec_type,
                title=f"{title_prefix} - Q{(created.month-1)//3 + 1} {created.year}",
                created=created,
                modified=created + timedelta(days=random.randint(0, 14)),
                custodian_id=custodian, system_id="sys_erp",
                contains_pii=random.random() < 0.3,
                confidentiality="RESTRICTED",
                jurisdiction=self._get_custodian_jurisdiction(custodian),
                metadata={
                    "fiscal_year": created.year,
                    "quarter": (created.month - 1) // 3 + 1,
                    "is_public_company": True
                }
            )
            self.store.add_record(record)
            self._record_ids_by_type.setdefault(rec_type, []).append(record.id)

    # =========================================================================
    # RELATIONSHIPS
    # =========================================================================

    def _generate_relationships(self):
        self._generate_attachments()
        self._generate_threads()
        self._generate_derivations()
        self._generate_references()

    def _generate_attachments(self):
        num_attachments = int(len(self._email_ids) * self.config.attachment_ratio)
        emails = random.sample(self._email_ids, min(num_attachments, len(self._email_ids)))
        for email_id in emails:
            num_docs = random.randint(1, 3)
            if self._document_ids:
                attachments = random.sample(self._document_ids, min(num_docs, len(self._document_ids)))
                email = self.store.records[email_id]
                for doc_id in attachments:
                    rel = Relationship(
                        id=f"rel_{email_id}_{doc_id}",
                        source_id=email_id, target_id=doc_id,
                        relation_type=RelationType.ATTACHMENT,
                        valid_from=email.created
                    )
                    self.store.add_relationship(rel)

    def _generate_threads(self):
        threads: Dict[str, List[str]] = {}
        for email_id in self._email_ids:
            email = self.store.records[email_id]
            thread_id = email.metadata.get("thread_id")
            if thread_id:
                threads.setdefault(thread_id, []).append(email_id)
        for thread_id, email_ids in threads.items():
            if len(email_ids) < 2:
                continue
            email_ids.sort(key=lambda eid: self.store.records[eid].created)
            for i in range(1, len(email_ids)):
                rel = Relationship(
                    id=f"rel_thread_{email_ids[i-1]}_{email_ids[i]}",
                    source_id=email_ids[i-1], target_id=email_ids[i],
                    relation_type=RelationType.THREAD,
                    valid_from=self.store.records[email_ids[i]].created
                )
                self.store.add_relationship(rel)

    def _generate_derivations(self):
        num = int(len(self._document_ids) * self.config.derivation_ratio)
        if len(self._document_ids) < 2:
            return
        for _ in range(num):
            source, derived = random.sample(self._document_ids, 2)
            if self.store.records[derived].created > self.store.records[source].created:
                rel = Relationship(
                    id=f"rel_deriv_{source}_{derived}",
                    source_id=source, target_id=derived,
                    relation_type=RelationType.DERIVATION,
                    valid_from=self.store.records[derived].created
                )
                self.store.add_relationship(rel)

    def _generate_references(self):
        all_docs = self._document_ids + self._record_ids_by_type.get(RecordType.CONTRACT, [])
        num = int(len(all_docs) * self.config.reference_ratio)
        if len(all_docs) < 2:
            return
        for _ in range(num):
            source, target = random.sample(all_docs, 2)
            rel = Relationship(
                id=f"rel_ref_{source}_{target}",
                source_id=source, target_id=target,
                relation_type=RelationType.REFERENCE,
                valid_from=self.store.records[source].created
            )
            self.store.add_relationship(rel)

    # =========================================================================
    # MATTERS
    # =========================================================================

    def _generate_matters(self):
        templates = [
            ("Smith v. Acme Corp", "LITIGATION", ["Product", "Engineering"]),
            ("SEC Investigation 2024", "REGULATORY", ["Finance", "Executive"]),
            ("Internal Audit Q3", "AUDIT", ["Finance", "Operations"]),
            ("Patent Dispute #445", "LITIGATION", ["Product", "Engineering"]),
            ("GDPR Subject Request", "REGULATORY", ["Customer Success", "Marketing"]),
        ]
        for i, (name, mtype, scope) in enumerate(templates[:self.config.num_matters]):
            cust_ids = [c.id for c in self.store.custodians.values() if c.department in scope][:20]
            matter = Matter(
                id=f"matter_{i:03d}", name=name, matter_type=mtype,
                custodian_ids=cust_ids, keywords=scope,
                hold_start=self._random_date(datetime(2024, 1, 1), datetime(2024, 6, 30)),
                is_active=True
            )
            self.store.add_matter(matter)

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _random_date(self, start=None, end=None) -> datetime:
        start = start or self.config.start_date
        end = end or self.config.end_date
        delta = end - start
        return start + timedelta(days=random.randint(0, max(1, delta.days)),
                                 seconds=random.randint(0, 86400))

    def _random_jurisdiction(self) -> Jurisdiction:
        jurisdictions = list(self.config.jurisdiction_weights.keys())
        weights = list(self.config.jurisdiction_weights.values())
        return random.choices(jurisdictions, weights=weights, k=1)[0]

    def _get_custodian_jurisdiction(self, custodian_id: str) -> Jurisdiction:
        c = self.store.custodians.get(custodian_id)
        return c.jurisdiction if c else Jurisdiction.US

    def _mime_for_ext(self, ext: str) -> str:
        return {
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".pdf": "application/pdf"
        }.get(ext, "application/octet-stream")


def generate_test_dataset(num_records: int = 10000, seed: int = 42) -> TRKGStore:
    scale = num_records / 10000
    config = GeneratorConfig(
        num_emails=int(4000 * scale), num_documents=int(3000 * scale),
        num_chats=int(1500 * scale), num_tickets=int(500 * scale),
        num_contracts=int(500 * scale), num_financial=int(500 * scale),
        num_custodians=max(20, int(100 * scale)), num_matters=5
    )
    return SyntheticDataGenerator(config, seed).generate()


def generate_minimal_dataset(seed: int = 42) -> TRKGStore:
    config = GeneratorConfig(
        num_emails=100, num_documents=50, num_chats=30,
        num_tickets=10, num_contracts=10, num_financial=20,
        num_custodians=10, num_matters=2
    )
    return SyntheticDataGenerator(config, seed).generate()
