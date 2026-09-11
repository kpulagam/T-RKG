# T-RKG

[![DOI](https://img.shields.io/badge/DOI-10.1109%2FACCESS.2026.3729794-blue)](https://doi.org/10.1109/ACCESS.2026.3729794)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)

Knowledge-based system for cross-system regulatory conflict detection in enterprise records governance. See `EXPERIMENTS_SUMMARY.md` for the experiment status (E1–E6) and `experiments/results/*_RESULTS.md` for paper-ready writeups.

## Publication

This work is published in *IEEE Access*:

> K. Pulagam and S. Sakalam, "T-RKG: A Knowledge-Based System for Cross-System Regulatory Conflict Detection in Enterprise Records Governance," in *IEEE Access*, vol. 14, pp. 138420-138439, 2026, doi: [10.1109/ACCESS.2026.3729794](https://doi.org/10.1109/ACCESS.2026.3729794).

Open access under a [CC BY 4.0 license](https://creativecommons.org/licenses/by/4.0/). Read it on [IEEE Xplore](https://ieeexplore.ieee.org/document/11675805).

If you use this code, ontology, or methodology, please cite:

```bibtex
@article{pulagam2026trkg,
  author  = {Pulagam, Kishore and Sakalam, Sai},
  journal = {IEEE Access},
  title   = {{T-RKG}: A Knowledge-Based System for Cross-System Regulatory Conflict Detection in Enterprise Records Governance},
  year    = {2026},
  volume  = {14},
  pages   = {138420-138439},
  doi     = {10.1109/ACCESS.2026.3729794}
}
```

## Reproducing E1 (LLM applicability baseline)

E1 calls a real model (`claude-opus-4-7`) and **requires an `ANTHROPIC_API_KEY`** plus a re-run; it is not reproducible from committed data alone. It replays from the local on-disk cache (`experiments/cache/llm/`, untracked) if present, so a re-run costs nothing when the cache is intact; with the cache absent it re-spends on the API, and with neither key nor cache it reports `status="BLOCKED"` rather than fabricating metrics.

```bash
export ANTHROPIC_API_KEY=sk-...
python experiments/e1_llm_baseline.py
```
