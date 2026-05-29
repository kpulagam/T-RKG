"""Tests for E1, the LLM applicability baseline.

No network: a mock client returns canned text so the cache, parser, scoring
harness, and BLOCKED path are all verified deterministically. Confirms the
honesty contract — with no client and no cache, classification raises rather
than guessing, and the driver reports BLOCKED without fabricating metrics.
"""

import os
import tempfile
import unittest
from datetime import datetime

from trkg.schema import Record, RecordType, Jurisdiction
from trkg.baselines.llm_baseline import (
    LLMApplicabilityBaseline, LLMUnavailable, DiskCache,
    build_prompt, parse_response, record_features, REGULATION_CODES,
)
from experiments import e1_llm_baseline as e1


def _rec(rid="r1", **kw):
    base = dict(id=rid, type=RecordType.EMAIL, title=rid,
                created=datetime(2021, 1, 1), modified=datetime(2021, 1, 2))
    base.update(kw)
    return Record(**base)


class _Block:
    def __init__(self, text): self.text = text


class _Resp:
    def __init__(self, text): self.content = [_Block(text)]


class _MockMessages:
    def __init__(self, text): self._text = text; self.calls = 0
    def create(self, **kw): self.calls += 1; return _Resp(self._text)


class _MockClient:
    def __init__(self, text): self.messages = _MockMessages(text)


class TestPromptAndParse(unittest.TestCase):
    def test_prompt_contains_features_and_codes(self):
        rec = _rec(jurisdiction=Jurisdiction.EU, contains_pii=True)
        p = build_prompt(rec)
        self.assertIn("EU", p)
        self.assertIn("GDPR", p)
        self.assertIn("contains_pii", p)

    def test_parse_plain_array(self):
        self.assertEqual(parse_response('["GDPR","SOX"]'), {"GDPR", "SOX"})

    def test_parse_with_prose_and_fence(self):
        txt = "Here you go:\n```json\n[\"CPRA\", \"PIPEDA\"]\n```\nDone."
        self.assertEqual(parse_response(txt), {"CPRA", "PIPEDA"})

    def test_parse_drops_invalid_codes(self):
        self.assertEqual(parse_response('["GDPR","NOPE","sox"]'), {"GDPR", "SOX"})

    def test_parse_empty(self):
        self.assertEqual(parse_response("[]"), set())
        self.assertEqual(parse_response("no array here"), set())

    def test_features_include_multijurisdiction(self):
        rec = _rec(jurisdiction=Jurisdiction.EU,
                   additional_jurisdictions=[Jurisdiction.US_CA])
        feats = record_features(rec)
        self.assertEqual(feats["additional_jurisdictions"], ["US_CA"])


class TestCacheAndClassify(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_cache_roundtrip(self):
        c = DiskCache(self.tmp)
        self.assertIsNone(c.get("m", "p"))
        c.put("m", "p", '["GDPR"]')
        self.assertEqual(c.get("m", "p"), '["GDPR"]')

    def test_classify_uses_client_then_caches(self):
        client = _MockClient('["GDPR"]')
        b = LLMApplicabilityBaseline(model="m", cache_dir=self.tmp, client=client)
        rec = _rec(jurisdiction=Jurisdiction.EU, contains_pii=True)
        self.assertEqual(b.classify(rec), {"GDPR"})
        self.assertEqual(client.messages.calls, 1)
        self.assertEqual(b.stats.api_calls, 1)
        # Second call is served from cache: no new API call.
        self.assertEqual(b.classify(rec), {"GDPR"})
        self.assertEqual(client.messages.calls, 1)
        self.assertEqual(b.stats.cache_hits, 1)

    def test_no_client_no_cache_raises(self):
        b = LLMApplicabilityBaseline(model="m", cache_dir=self.tmp, client=None)
        with self.assertRaises(LLMUnavailable):
            b.classify(_rec())

    def test_no_client_with_cache_works(self):
        # Pre-seed the cache, then a client-less baseline can still classify.
        seed_b = LLMApplicabilityBaseline(model="m", cache_dir=self.tmp,
                                          client=_MockClient('["CPRA"]'))
        rec = _rec(jurisdiction=Jurisdiction.US_CA, contains_pii=True)
        seed_b.classify(rec)
        b = LLMApplicabilityBaseline(model="m", cache_dir=self.tmp, client=None)
        self.assertEqual(b.classify(rec), {"CPRA"})


class TestE1Driver(unittest.TestCase):
    def test_blocked_when_no_key_and_no_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            b = LLMApplicabilityBaseline(model="m", cache_dir=tmp, client=None)
            out = e1.run(seeds=[42], num_records=400, sample_per_seed=5,
                         baseline=b, regimes=("clean",))
        self.assertEqual(out["status"], "BLOCKED")
        self.assertNotIn("regimes", out)  # no fabricated metrics
        self.assertIn("blocked_reason", out)

    def test_complete_with_mock_client(self):
        # A mock that always returns GDPR yields a well-defined, checkable score.
        with tempfile.TemporaryDirectory() as tmp:
            b = LLMApplicabilityBaseline(model="m", cache_dir=tmp,
                                         client=_MockClient('["GDPR"]'))
            out = e1.run(seeds=[42], num_records=400, sample_per_seed=20,
                         baseline=b, regimes=("clean",))
        self.assertEqual(out["status"], "COMPLETE")
        clean = out["regimes"]["clean"]
        for view in ("composed", "siloed"):
            for k in ("precision", "recall", "f1"):
                self.assertIn(k, clean[view]["micro"])
            self.assertIn("macro_f1", clean[view])
            self.assertIn("GDPR", clean[view]["per_regulation_f1"])
            self.assertIn("cross_domain_recall", clean[view])
        gap = clean["composed_minus_siloed_f1"]
        for k in ("observed_mean_delta", "p_value", "cohens_d"):
            self.assertIn(k, gap)
        self.assertIn("ontology_siloed_cross_domain_recall", clean)
        self.assertGreater(out["api_calls"], 0)

    def test_siloed_leak_gate_and_ontology_invariant(self):
        # The ontology-on-siloed cross-domain recall must be ~0 by construction:
        # the partition masks the PII trigger from every non-CRM record. This is
        # the validity invariant; a non-zero value means the partition leaked.
        with tempfile.TemporaryDirectory() as tmp:
            b = LLMApplicabilityBaseline(model="m", cache_dir=tmp,
                                         client=_MockClient('["GDPR"]'))
            out = e1.run(seeds=[42], num_records=2000, sample_per_seed=120,
                         baseline=b, regimes=("clean",))
        osr = out["regimes"]["clean"]["ontology_siloed_cross_domain_recall"]
        self.assertEqual(osr["mean"], 0.0)


if __name__ == "__main__":
    unittest.main()
