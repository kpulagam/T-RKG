# T-RKG

Knowledge-based system for cross-system regulatory conflict detection in enterprise records governance. See `EXPERIMENTS_SUMMARY.md` for the experiment status (E1–E6) and `experiments/results/*_RESULTS.md` for paper-ready writeups.

## Reproducing E1 (LLM applicability baseline)

E1 calls a real model (`claude-opus-4-7`) and **requires an `ANTHROPIC_API_KEY`** plus a re-run; it is not reproducible from committed data alone. It replays from the local on-disk cache (`experiments/cache/llm/`, untracked) if present, so a re-run costs nothing when the cache is intact; with the cache absent it re-spends on the API, and with neither key nor cache it reports `status="BLOCKED"` rather than fabricating metrics.

```bash
export ANTHROPIC_API_KEY=sk-...
python experiments/e1_llm_baseline.py
```
