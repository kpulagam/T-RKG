"""Multi-seed timing and mean/std formatting helpers, plus a paired
permutation test used for paired across-system comparisons in §VII."""

import time
import statistics
from typing import List, Dict, Any, Callable, Optional, Sequence, Tuple
from dataclasses import dataclass, field


def paired_permutation_test(
    a: Sequence[float],
    b: Sequence[float],
    n_resamples: int = 10000,
    seed: int = 0,
) -> Tuple[float, float]:
    """Two-sided paired permutation test on per-pair differences a[i] - b[i].

    Returns (observed_mean_difference, two-sided_p). With n paired samples
    there are 2^n possible sign assignments; for n in (10..14) we enumerate
    exactly, otherwise sample n_resamples sign-flips. The p is the share of
    resampled mean-differences whose absolute value meets or exceeds the
    observed absolute mean difference.
    """
    import math
    import random as _r
    if len(a) != len(b):
        raise ValueError("a and b must be the same length")
    diffs = [ai - bi for ai, bi in zip(a, b)]
    n = len(diffs)
    if n == 0:
        return 0.0, 1.0
    observed = sum(diffs) / n
    # Boundary tolerance: the per-mask statistic is accumulated in a different
    # float order than `observed`, so the identity/all-flip permutations (which
    # MUST count) can fall ~1e-16 below |observed| and be wrongly excluded,
    # yielding an impossible p=0. A two-sided permutation p can never be 0; its
    # floor is 2/2**n. Comparing against |observed| - tol restores that floor.
    tol = 1e-9 * max(1.0, abs(observed))
    threshold = abs(observed) - tol
    rng = _r.Random(seed)
    if n <= 14:
        total = 0
        hits = 0
        for mask in range(1 << n):
            s = 0.0
            for i in range(n):
                s += diffs[i] if (mask >> i) & 1 else -diffs[i]
            if abs(s / n) >= threshold:
                hits += 1
            total += 1
        return observed, hits / total
    hits = 0
    for _ in range(n_resamples):
        s = 0.0
        for d in diffs:
            s += d if rng.random() < 0.5 else -d
        if abs(s / n) >= threshold:
            hits += 1
    return observed, hits / n_resamples


def cohens_d_paired(a: Sequence[float], b: Sequence[float]) -> float:
    """Cohen's d for paired samples: mean(a-b) / stdev(a-b).

    Returns 0.0 when the paired differences have no spread (e.g. a constant
    gap) but a non-zero mean is conventionally reported as a very large effect;
    callers should read it together with the permutation-test p-value. A NaN
    guard returns float('inf') when every difference is identical and non-zero.
    """
    if len(a) != len(b):
        raise ValueError("a and b must be the same length")
    diffs = [ai - bi for ai, bi in zip(a, b)]
    n = len(diffs)
    if n == 0:
        return 0.0
    mean = sum(diffs) / n
    if n < 2:
        return 0.0
    var = sum((d - mean) ** 2 for d in diffs) / (n - 1)
    sd = var ** 0.5
    if sd == 0:
        return 0.0 if mean == 0 else float("inf")
    return mean / sd


@dataclass
class TimedResult:
    elapsed_ms: float
    value: Any = None


@dataclass
class MultiRunResult:
    values: List[Any] = field(default_factory=list)
    times_ms: List[float] = field(default_factory=list)

    @property
    def mean_time(self) -> float:
        return statistics.mean(self.times_ms) if self.times_ms else 0.0

    @property
    def std_time(self) -> float:
        return statistics.stdev(self.times_ms) if len(self.times_ms) > 1 else 0.0

    @property
    def median_time(self) -> float:
        return statistics.median(self.times_ms) if self.times_ms else 0.0

    @property
    def p95_time(self) -> float:
        if not self.times_ms:
            return 0.0
        sorted_t = sorted(self.times_ms)
        idx = int(0.95 * len(sorted_t))
        return sorted_t[min(idx, len(sorted_t) - 1)]

    def format_time(self, unit: str = "ms") -> str:
        return f"{self.mean_time:.1f} ± {self.std_time:.1f} {unit}"


def time_execution(func: Callable, *args, **kwargs) -> TimedResult:
    start = time.perf_counter()
    result = func(*args, **kwargs)
    elapsed = (time.perf_counter() - start) * 1000
    return TimedResult(elapsed_ms=elapsed, value=result)


def mean_std(values: List[float]) -> str:
    if not values:
        return "N/A"
    m = statistics.mean(values)
    s = statistics.stdev(values) if len(values) > 1 else 0.0
    if m >= 100:
        return f"{m:.0f} ± {s:.0f}"
    elif m >= 1:
        return f"{m:.1f} ± {s:.1f}"
    else:
        return f"{m:.2f} ± {s:.2f}"


def mean_std_int(values: List[int]) -> str:
    if not values:
        return "N/A"
    m = statistics.mean(values)
    s = statistics.stdev(values) if len(values) > 1 else 0.0
    return f"{m:.0f} ± {s:.0f}"


SEEDS = [42, 123, 456, 789, 1024, 2026, 31415, 65537, 1729, 2718]


def print_table(headers: List[str], rows: List[List[str]], title: str = ""):
    if title:
        print(f"\n{title}")
        print("=" * len(title))

    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(str(cell)))

    header_line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    separator = "-+-".join("-" * widths[i] for i in range(len(headers)))
    print(f"  {header_line}")
    print(f"  {separator}")

    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            if i < len(widths):
                cells.append(str(cell).ljust(widths[i]))
        print(f"  {' | '.join(cells)}")
    print()
