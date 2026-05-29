"""LLM applicability baseline (E1).

Task: given a record's attributes, predict which regulations govern it — the
same applicability decision T-RKG's ontology makes in
ConflictDetector.infer_applicable_regulations. This baseline asks an LLM to do
it instead, so the paper can quantify how a strong general model compares to the
structured ontology on a precise, checkable classification.

Design notes:
  * Every model response is cached to disk, keyed by sha256(model + prompt), so
    a run is fully reproducible and never re-bills for a record already seen.
  * The Anthropic client is INJECTED (constructor arg). It is created lazily and
    only when an API key is present. With no client and no cached response,
    classify() raises LLMUnavailable rather than guessing — the experiment is
    reported BLOCKED, never fabricated.
  * The regulation universe is exactly the nine profiled regulations (the same
    set the ontology can assign); PCI_DSS and INTERNAL have no profile and are
    excluded from both prediction and ground truth.
"""

import os
import json
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Callable

from trkg.schema import Record


# The nine regulations the ontology can assign (those with a RegulationProfile).
REGULATION_CODES: List[str] = [
    "GDPR", "SOX", "HIPAA", "SEC", "FINRA", "CPRA", "PIPEDA", "IRS", "HGB",
]

# Concise, faithful scope summaries given to the model so this is a fair test of
# applying known rules, not recalling them from memory. Kept in lockstep with
# trkg.conflict.build_regulation_profiles.
REGULATION_SCOPES: Dict[str, str] = {
    "GDPR": "EU personal data (any record type) that contains PII. Jurisdictions EU, EU_DE, EU_ES, EU_FR.",
    "SOX": "Public-company financial records (FINANCIAL, AUDIT, WORKPAPER, INVOICE) where is_public_company is true. Any jurisdiction.",
    "HIPAA": "US protected health information (records with PHI). Jurisdictions US, US_CA, US_NY.",
    "SEC": "US financial records (FINANCIAL, INVOICE). Jurisdictions US, US_CA, US_NY.",
    "FINRA": "Public-company US communications/financial records (CHAT, EMAIL, FINANCIAL) where is_public_company is true. Jurisdictions US, US_CA, US_NY.",
    "CPRA": "California personal data (any type) containing PII. Jurisdiction US_CA.",
    "PIPEDA": "Canadian personal data (any type) containing PII. Jurisdiction CA.",
    "IRS": "US tax/financial records (FINANCIAL, TAX). Jurisdictions US, US_CA, US_NY.",
    "HGB": "German commercial records (FINANCIAL, AUDIT, CONTRACT, INVOICE). Jurisdiction EU_DE.",
}

DEFAULT_MODEL = "claude-opus-4-7"


class LLMUnavailable(RuntimeError):
    """Raised when a classification is needed but neither a cached response nor a
    usable client (API key) is available. Signals a BLOCKED experiment."""


def record_features(record: Record) -> Dict[str, object]:
    """The attribute view shown to the model — the same fields applies_to reads."""
    return {
        "record_type": record.type.value,
        "jurisdiction": record.jurisdiction.value,
        "additional_jurisdictions": [j.value for j in
                                     getattr(record, "additional_jurisdictions", []) or []],
        "contains_pii": bool(record.contains_pii),
        "contains_phi": bool(record.contains_phi),
        "is_public_company": bool(record.metadata.get("is_public_company", False)),
    }


SYSTEM_PROMPT = (
    "You are a records-governance compliance classifier. Given a record's "
    "attributes, decide which of the listed regulations govern it by applying "
    "the provided scope rules exactly. Respond with ONLY a JSON array of the "
    "applicable regulation codes (a subset of the provided list), e.g. "
    '["GDPR","SOX"]. If none apply, respond with []. No prose.'
)


def build_prompt(record: Record) -> str:
    scopes = "\n".join(f"- {code}: {REGULATION_SCOPES[code]}" for code in REGULATION_CODES)
    feats = record_features(record)
    return (
        "Regulations and their scope:\n"
        f"{scopes}\n\n"
        "Record attributes:\n"
        f"{json.dumps(feats, indent=2, sort_keys=True)}\n\n"
        f"Which of these codes apply? {REGULATION_CODES}\n"
        "Return ONLY the JSON array."
    )


def parse_response(text: str) -> Set[str]:
    """Extract a JSON array of codes from the model text; keep only valid codes."""
    valid = set(REGULATION_CODES)
    m = re.search(r"\[.*?\]", text, re.DOTALL)
    if not m:
        return set()
    try:
        arr = json.loads(m.group(0))
    except json.JSONDecodeError:
        return set()
    return {str(x).strip().upper() for x in arr if str(x).strip().upper() in valid}


class DiskCache:
    """sha256(model+prompt) -> response text, one JSON file per entry."""

    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _key(self, model: str, prompt: str) -> str:
        return hashlib.sha256(f"{model}\n{prompt}".encode("utf-8")).hexdigest()

    def _path(self, model: str, prompt: str) -> str:
        return os.path.join(self.cache_dir, self._key(model, prompt) + ".json")

    def get(self, model: str, prompt: str) -> Optional[str]:
        path = self._path(model, prompt)
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)["response_text"]
        return None

    def put(self, model: str, prompt: str, response_text: str) -> None:
        with open(self._path(model, prompt), "w") as f:
            json.dump({
                "model": model,
                "prompt_sha": self._key(model, prompt),
                "response_text": response_text,
                "created_utc": datetime.now(timezone.utc).isoformat(),
            }, f, indent=2)


def make_anthropic_client():
    """Create a real Anthropic client iff an API key is present; else None."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    import anthropic
    return anthropic.Anthropic()


@dataclass
class LLMBaselineStats:
    model: str
    n_classified: int = 0
    cache_hits: int = 0
    api_calls: int = 0
    blocked: bool = False
    engine: Dict[str, str] = field(default_factory=dict)


class LLMApplicabilityBaseline:
    """Predicts the applicable-regulation set for a record via an LLM.

    client: an object exposing the Anthropic messages API
            (client.messages.create(...)). Inject a mock in tests. If None and a
            response is not cached, classify() raises LLMUnavailable.
    """

    def __init__(self, model: str = DEFAULT_MODEL, cache_dir: Optional[str] = None,
                 client=None, max_tokens: int = 128):
        self.model = model
        self.cache = DiskCache(cache_dir or _default_cache_dir())
        self.client = client
        self.max_tokens = max_tokens
        self.stats = LLMBaselineStats(model=model)

    def _call_model(self, prompt: str) -> str:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        # Anthropic SDK: resp.content is a list of blocks with .text.
        return "".join(getattr(b, "text", "") for b in resp.content)

    def classify(self, record: Record) -> Set[str]:
        prompt = build_prompt(record)
        cached = self.cache.get(self.model, prompt)
        if cached is not None:
            self.stats.cache_hits += 1
            self.stats.n_classified += 1
            return parse_response(cached)
        if self.client is None:
            raise LLMUnavailable(
                "No cached response and no API client (ANTHROPIC_API_KEY unset). "
                "E1 is BLOCKED — build/cache responses before scoring.")
        text = self._call_model(prompt)
        self.cache.put(self.model, prompt, text)
        self.stats.api_calls += 1
        self.stats.n_classified += 1
        return parse_response(text)


def _default_cache_dir() -> str:
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(here, "experiments", "cache", "llm")
