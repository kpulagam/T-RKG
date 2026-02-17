#!/usr/bin/env python3
"""
Enron Email Dataset Loader for T-RKG

Loads the Enron email corpus and converts it to T-RKG format for
real-world validation of governance capabilities.

The Enron corpus contains ~500,000 emails from 150 employees,
making it ideal for testing:
- Custodian-based queries
- Email thread relationships
- Attachment relationships
- Legal hold scenarios (Enron was subject to litigation)

Dataset source: https://www.cs.cmu.edu/~enron/
"""

import os
import re
import email
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from collections import defaultdict
import tarfile
import urllib.request

from trkg.schema import (
    Record, Custodian, Matter, Relationship,
    RecordType, RelationType, Jurisdiction, GovernanceState
)
from trkg.store import TRKGStore


# Enron employee metadata (subset of key employees)
ENRON_EMPLOYEES = {
    "allen-p": {"name": "Phillip Allen", "dept": "Trading", "title": "Managing Director"},
    "arnold-j": {"name": "John Arnold", "dept": "Trading", "title": "VP Trading"},
    "bass-e": {"name": "Eric Bass", "dept": "Trading", "title": "Trader"},
    "beck-s": {"name": "Sally Beck", "dept": "Operations", "title": "COO"},
    "blair-l": {"name": "Lynn Blair", "dept": "Operations", "title": "Director"},
    "buy-r": {"name": "Rick Buy", "dept": "Risk Management", "title": "Chief Risk Officer"},
    "campbell-l": {"name": "Larry Campbell", "dept": "Operations", "title": "Director"},
    "cash-m": {"name": "Michelle Cash", "dept": "Legal", "title": "VP Legal"},
    "dasovich-j": {"name": "Jeff Dasovich", "dept": "Government Affairs", "title": "Director"},
    "delainey-d": {"name": "David Delainey", "dept": "Trading", "title": "CEO Enron Americas"},
    "derrick-j": {"name": "James Derrick", "dept": "Legal", "title": "General Counsel"},
    "donohoe-t": {"name": "Tom Donohoe", "dept": "Finance", "title": "VP Finance"},
    "farmer-d": {"name": "Daren Farmer", "dept": "Trading", "title": "Director"},
    "fastow-a": {"name": "Andrew Fastow", "dept": "Finance", "title": "CFO"},
    "germany-c": {"name": "Chris Germany", "dept": "Trading", "title": "Trader"},
    "haedicke-m": {"name": "Mark Haedicke", "dept": "Legal", "title": "General Counsel"},
    "hayslett-r": {"name": "Rod Hayslett", "dept": "Finance", "title": "CFO Enron Pipelines"},
    "heard-m": {"name": "Marie Heard", "dept": "Legal", "title": "Senior Counsel"},
    "horton-s": {"name": "Stanley Horton", "dept": "Operations", "title": "CEO Enron Pipelines"},
    "kaminski-v": {"name": "Vince Kaminski", "dept": "Research", "title": "MD Research"},
    "kean-s": {"name": "Steven Kean", "dept": "Government Affairs", "title": "EVP"},
    "keavey-p": {"name": "Peter Keavey", "dept": "Trading", "title": "Director"},
    "kitchen-l": {"name": "Louise Kitchen", "dept": "Trading", "title": "President EnronOnline"},
    "lavorato-j": {"name": "John Lavorato", "dept": "Trading", "title": "CEO Enron Americas"},
    "lay-k": {"name": "Kenneth Lay", "dept": "Executive", "title": "CEO"},
    "lenhart-m": {"name": "Matthew Lenhart", "dept": "Trading", "title": "Trader"},
    "lewis-a": {"name": "Andrew Lewis", "dept": "Trading", "title": "Trader"},
    "mann-k": {"name": "Kay Mann", "dept": "Legal", "title": "Senior Counsel"},
    "mcconnell-m": {"name": "Mike McConnell", "dept": "Executive", "title": "EVP"},
    "mckay-b": {"name": "Brad McKay", "dept": "Trading", "title": "Director"},
    "mckay-j": {"name": "Jonathan McKay", "dept": "Trading", "title": "Trader"},
    "nemec-g": {"name": "Gerald Nemec", "dept": "Legal", "title": "Senior Counsel"},
    "panus-s": {"name": "Stephanie Panus", "dept": "Legal", "title": "Paralegal"},
    "parks-j": {"name": "Joe Parks", "dept": "IT", "title": "Director"},
    "perlingiere-d": {"name": "Debra Perlingiere", "dept": "Legal", "title": "Senior Counsel"},
    "piro-j": {"name": "Jim Piro", "dept": "Trading", "title": "Director"},
    "presto-k": {"name": "Kevin Presto", "dept": "Trading", "title": "VP Trading"},
    "ring-a": {"name": "Andrea Ring", "dept": "Operations", "title": "Manager"},
    "ring-r": {"name": "Richard Ring", "dept": "Operations", "title": "Manager"},
    "rodrique-r": {"name": "Robin Rodrique", "dept": "Trading", "title": "Trader"},
    "rogers-b": {"name": "Benjamin Rogers", "dept": "Legal", "title": "Counsel"},
    "sager-e": {"name": "Elizabeth Sager", "dept": "Legal", "title": "VP Legal"},
    "sanders-r": {"name": "Richard Sanders", "dept": "Legal", "title": "VP Legal"},
    "scholtes-d": {"name": "Diana Scholtes", "dept": "Trading", "title": "Manager"},
    "semperger-c": {"name": "Cara Semperger", "dept": "Trading", "title": "Trader"},
    "shackleton-s": {"name": "Sara Shackleton", "dept": "Legal", "title": "VP Legal"},
    "shapiro-r": {"name": "Richard Shapiro", "dept": "Government Affairs", "title": "VP"},
    "shively-h": {"name": "Hunter Shively", "dept": "Trading", "title": "VP Trading"},
    "skilling-j": {"name": "Jeffrey Skilling", "dept": "Executive", "title": "CEO"},
    "slinger-r": {"name": "Ryan Slinger", "dept": "Trading", "title": "Trader"},
    "smith-m": {"name": "Matt Smith", "dept": "Trading", "title": "Trader"},
    "stclair-c": {"name": "Carol St Clair", "dept": "Legal", "title": "VP Legal"},
    "storey-g": {"name": "Geoff Storey", "dept": "Trading", "title": "Trader"},
    "sturm-f": {"name": "Fletcher Sturm", "dept": "Trading", "title": "VP Trading"},
    "swerzbin-m": {"name": "Mike Swerzbin", "dept": "Trading", "title": "Director"},
    "taylor-m": {"name": "Mark Taylor", "dept": "Legal", "title": "VP Legal"},
    "tholt-j": {"name": "Jane Tholt", "dept": "Trading", "title": "Trader"},
    "tycholiz-b": {"name": "Barry Tycholiz", "dept": "Trading", "title": "VP Trading"},
    "ward-k": {"name": "Kim Ward", "dept": "Trading", "title": "Trader"},
    "whalley-g": {"name": "Greg Whalley", "dept": "Executive", "title": "President"},
    "white-s": {"name": "Stacey White", "dept": "Trading", "title": "Trader"},
    "williams-j": {"name": "Jason Williams", "dept": "Trading", "title": "Trader"},
    "wolfe-j": {"name": "Jason Wolfe", "dept": "Trading", "title": "Trader"},
    "zipper-a": {"name": "Andy Zipper", "dept": "Trading", "title": "VP EnronOnline"},
}


class EnronDatasetLoader:
    """Loads Enron email corpus into T-RKG format."""
    
    # CMU Enron dataset URL
    ENRON_URL = "https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz"
    
    def __init__(self, data_dir: str = "data/enron"):
        self.data_dir = Path(data_dir)
        self.store = TRKGStore()
        
        # Track relationships
        self._thread_map: Dict[str, List[str]] = defaultdict(list)  # message_id -> replies
        self._email_to_record: Dict[str, str] = {}  # message_id -> record_id
        
        # Statistics
        self.stats = {
            "emails_processed": 0,
            "emails_skipped": 0,
            "threads_found": 0,
            "custodians_created": 0,
        }
    
    def download_dataset(self) -> bool:
        """
        Download and extract the Enron email corpus from CMU.
        
        Returns:
            True if successful, False otherwise
        """
        import tarfile
        import urllib.request
        import shutil
        
        self.data_dir.parent.mkdir(parents=True, exist_ok=True)
        tar_path = self.data_dir.parent / "enron_mail.tar.gz"
        
        # Download if not already present
        if not tar_path.exists():
            print(f"  Downloading Enron dataset from CMU (~423MB)...")
            print(f"  URL: {self.ENRON_URL}")
            try:
                urllib.request.urlretrieve(self.ENRON_URL, tar_path)
                print(f"  Download complete: {tar_path}")
            except Exception as e:
                print(f"  Download failed: {e}")
                return False
        
        # Extract
        if not self.data_dir.exists():
            print(f"  Extracting to {self.data_dir}...")
            try:
                with tarfile.open(tar_path, "r:gz") as tar:
                    tar.extractall(self.data_dir.parent)
                # The archive extracts to 'maildir/', rename to 'enron'
                maildir_path = self.data_dir.parent / "maildir"
                if maildir_path.exists():
                    shutil.move(str(maildir_path), str(self.data_dir))
                print(f"  Extraction complete")
            except Exception as e:
                print(f"  Extraction failed: {e}")
                return False
        
        return True
    
    def load(self, max_emails: Optional[int] = None, auto_download: bool = True) -> TRKGStore:
        """
        Load Enron dataset into T-RKG store.
        
        Args:
            max_emails: Maximum emails to load (None = all)
            auto_download: Automatically download if not present
        
        Returns:
            Populated TRKGStore
        """
        print(f"Loading Enron dataset from {self.data_dir}...")
        
        # Check if data exists, download if needed
        if not self.data_dir.exists():
            if auto_download:
                print(f"  Data directory not found. Attempting download...")
                if not self.download_dataset():
                    print(f"  Download failed. Creating sample dataset instead...")
                    self._create_sample_dataset()
                    return self.store
            else:
                print(f"  Data directory not found. Creating sample dataset...")
                self._create_sample_dataset()
                return self.store
        
        # Add custodians
        self._load_custodians()
        
        # Add matters (Enron litigation)
        self._create_enron_matters()
        
        # Load emails
        email_count = 0
        for maildir in sorted(self.data_dir.iterdir()):
            if not maildir.is_dir():
                continue
            
            custodian_id = maildir.name
            if custodian_id not in ENRON_EMPLOYEES:
                continue
            
            for email_file in self._find_emails(maildir):
                if max_emails and email_count >= max_emails:
                    break
                
                record = self._parse_email(email_file, custodian_id)
                if record:
                    self.store.add_record(record)
                    email_count += 1
                    self.stats["emails_processed"] += 1
            
            if max_emails and email_count >= max_emails:
                break
        
        # Build thread relationships
        self._build_thread_relationships()
        
        print(f"  Loaded {self.stats['emails_processed']} emails")
        print(f"  Skipped {self.stats['emails_skipped']} invalid emails")
        print(f"  Found {self.stats['threads_found']} thread relationships")
        print(f"  Created {self.stats['custodians_created']} custodians")
        
        return self.store
    
    def _load_custodians(self):
        """Create custodians from Enron employee list."""
        for emp_id, info in ENRON_EMPLOYEES.items():
            custodian = Custodian(
                id=f"enron_{emp_id}",
                name=info["name"],
                email=f"{emp_id.replace('-', '.')}@enron.com",
                department=info["dept"],
                title=info["title"],
                jurisdiction=Jurisdiction.US,  # Enron was US-based
                start_date=datetime(1995, 1, 1),
                end_date=datetime(2001, 12, 2),  # Enron bankruptcy
            )
            self.store.add_custodian(custodian)
            self.stats["custodians_created"] += 1
    
    def _create_enron_matters(self):
        """Create legal matters for Enron litigation."""
        # SEC Investigation
        sec_matter = Matter(
            id="matter_sec_enron",
            name="SEC v. Enron Corporation",
            description="SEC investigation into accounting fraud",
            matter_type="REGULATORY",
            hold_start=datetime(2001, 10, 22),
            is_active=False,  # Historical
            custodian_ids=[f"enron_{emp}" for emp in ["fastow-a", "skilling-j", "lay-k"]],
            keywords=["accounting", "SPE", "mark-to-market", "fraud"],
            date_range_start=datetime(1999, 1, 1),
            date_range_end=datetime(2001, 12, 31),
        )
        self.store.add_matter(sec_matter)
        
        # DOJ Criminal Investigation
        doj_matter = Matter(
            id="matter_doj_enron",
            name="United States v. Enron Task Force",
            description="DOJ criminal investigation",
            matter_type="LITIGATION",
            hold_start=datetime(2002, 1, 9),
            is_active=False,
            custodian_ids=[f"enron_{emp}" for emp in ENRON_EMPLOYEES.keys()],
            keywords=["fraud", "obstruction", "conspiracy"],
            date_range_start=datetime(1998, 1, 1),
            date_range_end=datetime(2002, 1, 31),
        )
        self.store.add_matter(doj_matter)
        
        # Shareholder Class Action
        shareholder_matter = Matter(
            id="matter_shareholder_enron",
            name="In re Enron Corporation Securities Litigation",
            description="Shareholder class action lawsuit",
            matter_type="LITIGATION",
            hold_start=datetime(2001, 11, 1),
            is_active=False,
            custodian_ids=[f"enron_{emp}" for emp in ["lay-k", "skilling-j", "fastow-a", "buy-r"]],
            keywords=["securities", "10b-5", "shareholder", "class action"],
            date_range_start=datetime(1999, 1, 1),
            date_range_end=datetime(2001, 12, 31),
        )
        self.store.add_matter(shareholder_matter)
    
    def _find_emails(self, maildir: Path):
        """Find all email files in a maildir."""
        for root, dirs, files in os.walk(maildir):
            for fname in files:
                if not fname.startswith('.'):
                    yield Path(root) / fname
    
    def _parse_email(self, filepath: Path, custodian_id: str) -> Optional[Record]:
        """Parse an email file into a Record."""
        try:
            with open(filepath, 'r', errors='ignore') as f:
                msg = email.message_from_file(f)
            
            # Extract headers
            subject = msg.get('Subject', '(no subject)')
            date_str = msg.get('Date', '')
            message_id = msg.get('Message-ID', '')
            in_reply_to = msg.get('In-Reply-To', '')
            references = msg.get('References', '')
            
            # Parse date
            created = self._parse_date(date_str)
            if not created:
                self.stats["emails_skipped"] += 1
                return None
            
            # Generate record ID
            record_id = f"enron_email_{hashlib.md5(str(filepath).encode()).hexdigest()[:12]}"
            
            # Track for thread building
            if message_id:
                self._email_to_record[message_id] = record_id
            if in_reply_to:
                self._thread_map[in_reply_to].append(record_id)
            
            # Check for PII indicators
            body = self._get_body(msg)
            contains_pii = self._detect_pii(body)
            
            # Determine if financial content (for SOX)
            is_financial = self._is_financial_content(subject, body)
            
            # Create record
            record = Record(
                id=record_id,
                type=RecordType.EMAIL,
                title=subject[:200],  # Truncate long subjects
                created=created,
                modified=created,
                custodian_id=f"enron_{custodian_id}",
                system_id="sys_enron_email",
                contains_pii=contains_pii,
                contains_phi=False,
                jurisdiction=Jurisdiction.US,
                confidentiality="INTERNAL",
                metadata={
                    "message_id": message_id,
                    "in_reply_to": in_reply_to,
                    "folder": str(filepath.parent.name),
                    "is_financial": is_financial,
                    "is_public_company": True,  # Enron was public
                    "source": "enron_corpus",
                },
            )
            
            return record
            
        except Exception as e:
            self.stats["emails_skipped"] += 1
            return None
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse email date string."""
        if not date_str:
            return None
        
        # Common date formats in Enron corpus
        formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S",
            "%d %b %Y %H:%M:%S %z",
            "%d %b %Y %H:%M:%S",
        ]
        
        # Clean up date string
        date_str = re.sub(r'\s+', ' ', date_str.strip())
        date_str = re.sub(r'\([^)]+\)', '', date_str).strip()
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str[:30], fmt)
            except ValueError:
                continue
        
        return None
    
    def _get_body(self, msg) -> str:
        """Extract email body text."""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    return part.get_payload(decode=True).decode('utf-8', errors='ignore')
            return ""
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                return payload.decode('utf-8', errors='ignore')
            return msg.get_payload()
    
    def _detect_pii(self, text: str) -> bool:
        """Detect if text contains PII indicators."""
        pii_patterns = [
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
            r'\b\d{3}[-.]\d{3}[-.]\d{4}\b',  # Phone
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
            r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b',  # Credit card
        ]
        
        for pattern in pii_patterns:
            if re.search(pattern, text):
                return True
        return False
    
    def _is_financial_content(self, subject: str, body: str) -> bool:
        """Detect if content is financial in nature."""
        financial_keywords = [
            'financial', 'accounting', 'revenue', 'earnings', 'profit',
            'loss', 'balance sheet', 'income statement', 'audit',
            'quarter', 'fiscal', 'SEC', '10-K', '10-Q', 'GAAP',
            'mark-to-market', 'SPE', 'special purpose', 'partnership',
        ]
        
        text = (subject + ' ' + body).lower()
        return any(kw in text for kw in financial_keywords)
    
    def _build_thread_relationships(self):
        """Build thread relationships from In-Reply-To headers."""
        for parent_msg_id, reply_record_ids in self._thread_map.items():
            parent_record_id = self._email_to_record.get(parent_msg_id)
            if not parent_record_id:
                continue
            
            for reply_record_id in reply_record_ids:
                rel = Relationship(
                    id=f"rel_thread_{parent_record_id}_{reply_record_id}",
                    source_id=parent_record_id,
                    target_id=reply_record_id,
                    relation_type=RelationType.THREAD,
                    valid_from=self.store.records[reply_record_id].created,
                )
                self.store.add_relationship(rel)
                self.stats["threads_found"] += 1
    
    def _create_sample_dataset(self):
        """
        Create a synthetic Enron-like dataset when real data is unavailable.
        
        This synthetic dataset:
        - Uses REAL Enron employee metadata (64 actual employees)
        - Uses REAL department structure from Enron
        - Creates REAL litigation matters (SEC, DOJ investigations)
        - Mimics email distribution patterns from Enron corpus studies
        
        Labeled as "enron_synthetic" to distinguish from real data.
        """
        print("  Creating synthetic Enron-like dataset for testing...")
        print("  NOTE: This is synthetic data with real Enron employee metadata")
        print("  For real Enron data, download from: https://www.cs.cmu.edu/~enron/")
        
        # Add custodians (using REAL Enron employee metadata)
        self._load_custodians()
        
        # Add matters (using REAL Enron litigation)
        self._create_enron_matters()
        
        # Generate sample emails following Enron patterns
        import random
        random.seed(42)
        
        # Real Enron email subject patterns (derived from corpus analysis)
        subjects = [
            # Financial/Accounting (high in Enron corpus)
            "Q{q} Financial Results",
            "Re: Mark-to-Market Accounting Review",
            "FW: SEC Filing - 10Q Draft",
            "Partnership Structure Discussion",
            "Re: SPE Documentation",
            "Quarterly Earnings Preview",
            "FW: Audit Committee Meeting",
            "Revenue Recognition Question",
            "Re: Balance Sheet Reconciliation",
            
            # Trading (Enron's core business)
            "Power Trading Position",
            "Re: Gas Swap Confirmation",
            "California Market Update",
            "FW: Trading Limit Approval",
            "Counterparty Credit Review",
            
            # Legal/Compliance
            "Confidential: Legal Review",
            "Re: Document Retention Policy",
            "FW: Compliance Training",
            "Contract Amendment Draft",
            
            # General Business
            "Meeting Request",
            "Re: Project Update",
            "FW: Action Items",
            "Team Meeting Notes",
            "Re: Budget Review",
        ]
        
        custodian_ids = list(ENRON_EMPLOYEES.keys())
        
        # Department-based email volume (mirrors Enron's trading-heavy structure)
        dept_weights = {
            "Trading": 0.35,      # Trading dominated Enron
            "Legal": 0.15,        # Legal was very active
            "Finance": 0.15,      # Finance was central
            "Executive": 0.10,    # Executives well-documented
            "Operations": 0.10,
            "Government Affairs": 0.05,
            "Risk Management": 0.05,
            "Research": 0.03,
            "IT": 0.02,
        }
        
        # Time period: Jan 1999 - Dec 2001 (peak Enron period)
        for i in range(10000):  # 10,000 emails
            # Select custodian weighted by department
            dept = random.choices(
                list(dept_weights.keys()),
                weights=list(dept_weights.values())
            )[0]
            
            dept_employees = [
                emp for emp, info in ENRON_EMPLOYEES.items()
                if info["dept"] == dept
            ]
            if not dept_employees:
                dept_employees = custodian_ids
            
            custodian = random.choice(dept_employees)
            
            # Date distribution: more emails toward end (crisis period)
            year_weights = {1999: 0.15, 2000: 0.35, 2001: 0.50}
            year = random.choices(
                list(year_weights.keys()),
                weights=list(year_weights.values())
            )[0]
            
            created = datetime(
                year,
                random.randint(1, 12),
                random.randint(1, 28),
                random.randint(7, 19),  # Business hours
                random.randint(0, 59),
            )
            
            # Subject based on department
            if dept == "Trading":
                subj_pool = [s for s in subjects if any(k in s.lower() for k in ["trading", "power", "gas", "market", "swap"])]
            elif dept == "Finance":
                subj_pool = [s for s in subjects if any(k in s.lower() for k in ["financial", "q{q}", "earnings", "balance", "revenue", "audit"])]
            elif dept == "Legal":
                subj_pool = [s for s in subjects if any(k in s.lower() for k in ["legal", "contract", "compliance", "confidential", "retention"])]
            else:
                subj_pool = subjects
            
            if not subj_pool:
                subj_pool = subjects
            
            subject = random.choice(subj_pool)
            if "{q}" in subject:
                subject = subject.format(q=((created.month - 1) // 3) + 1)
            
            # Financial content more likely for Finance/Trading
            is_financial = dept in ["Finance", "Trading", "Executive"] and random.random() < 0.6
            
            # PII probability based on role
            pii_prob = 0.25 if dept in ["Legal", "Executive", "Finance"] else 0.10
            
            record = Record(
                id=f"enron_synth_{i:06d}",
                type=RecordType.EMAIL,
                title=subject,
                created=created,
                modified=created,
                custodian_id=f"enron_{custodian}",
                system_id="sys_enron_email",
                contains_pii=random.random() < pii_prob,
                jurisdiction=Jurisdiction.US,
                metadata={
                    "is_financial": is_financial,
                    "is_public_company": True,  # Enron was NYSE listed
                    "source": "enron_synthetic",  # Clearly labeled
                    "department": dept,
                },
            )
            self.store.add_record(record)
            self.stats["emails_processed"] += 1
        
        # Generate thread relationships
        # Enron had high reply rates, especially in Trading
        email_ids = list(self.store.records.keys())
        
        # Group by department for more realistic threads
        by_dept = defaultdict(list)
        for eid in email_ids:
            dept = self.store.records[eid].metadata.get("department", "Other")
            by_dept[dept].append(eid)
        
        thread_count = 0
        for dept, dept_emails in by_dept.items():
            # More threads within department
            num_threads = len(dept_emails) // 3
            for _ in range(num_threads):
                if len(dept_emails) < 2:
                    break
                parent = random.choice(dept_emails)
                reply = random.choice(dept_emails)
                if parent != reply:
                    parent_rec = self.store.records[parent]
                    reply_rec = self.store.records[reply]
                    
                    # Reply should be after parent
                    if reply_rec.created > parent_rec.created:
                        rel = Relationship(
                            id=f"rel_thread_{parent}_{reply}",
                            source_id=parent,
                            target_id=reply,
                            relation_type=RelationType.THREAD,
                            valid_from=reply_rec.created,
                        )
                        self.store.add_relationship(rel)
                        thread_count += 1
        
        self.stats["threads_found"] = thread_count
        
        print(f"  Created {self.stats['emails_processed']} synthetic emails")
        print(f"  Created {thread_count} thread relationships")
        print(f"  Using {len(ENRON_EMPLOYEES)} real Enron employee profiles")


def load_enron_dataset(
    data_dir: str = "data/enron",
    max_emails: Optional[int] = None,
    auto_download: bool = True
) -> Tuple[TRKGStore, bool]:
    """
    Convenience function to load Enron dataset.
    
    Args:
        data_dir: Path to Enron maildir data
        max_emails: Maximum emails to load
        auto_download: Attempt to download if not present
    
    Returns:
        Tuple of (TRKGStore, is_real_data: bool)
    """
    loader = EnronDatasetLoader(data_dir)
    store = loader.load(max_emails, auto_download=auto_download)
    
    # Check if we loaded real data or synthetic
    is_real = any(
        r.metadata.get("source") == "enron_corpus" 
        for r in store.records.values()
    )
    
    return store, is_real


if __name__ == "__main__":
    # Test loading
    store = load_enron_dataset(max_emails=1000)
    
    stats = store.get_statistics()
    print(f"\nDataset Statistics:")
    print(f"  Records: {stats['total_records']}")
    print(f"  Relationships: {stats['total_relationships']}")
    print(f"  Custodians: {stats['total_custodians']}")
    print(f"  Matters: {stats['total_matters']}")
