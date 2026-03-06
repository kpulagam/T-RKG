"""
Statistical utilities for T-RKG experiments.

Provides multi-seed execution, mean/std reporting, and formatting.
"""

import time
import statistics
from typing import List, Dict, Any, Callable, Optional
from dataclasses import dataclass, field


@dataclass
class TimedResult:
    """Result of a single timed execution."""
    elapsed_ms: float
    value: Any = None


@dataclass
class MultiRunResult:
    """Aggregated result across multiple random seeds."""
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
    """Time a function call and return result + elapsed time in ms."""
    start = time.perf_counter()
    result = func(*args, **kwargs)
    elapsed = (time.perf_counter() - start) * 1000
    return TimedResult(elapsed_ms=elapsed, value=result)


def mean_std(values: List[float]) -> str:
    """Format mean ± std for a list of floats."""
    if not values:
        return "N/A"
    m = statistics.mean(values)
    s = statistics.stdev(values) if len(values) > 1 else 0.0
    # Auto-format based on magnitude
    if m >= 100:
        return f"{m:.0f} ± {s:.0f}"
    elif m >= 1:
        return f"{m:.1f} ± {s:.1f}"
    else:
        return f"{m:.2f} ± {s:.2f}"


def mean_std_int(values: List[int]) -> str:
    """Format mean ± std for integer values."""
    if not values:
        return "N/A"
    m = statistics.mean(values)
    s = statistics.stdev(values) if len(values) > 1 else 0.0
    return f"{m:.0f} ± {s:.0f}"


SEEDS = [42, 123, 456, 789, 1024]


def print_table(headers: List[str], rows: List[List[str]], title: str = ""):
    """Print a formatted ASCII table."""
    if title:
        print(f"\n{title}")
        print("=" * len(title))

    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(str(cell)))

    # Header
    header_line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    separator = "-+-".join("-" * widths[i] for i in range(len(headers)))
    print(f"  {header_line}")
    print(f"  {separator}")

    # Rows
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            if i < len(widths):
                cells.append(str(cell).ljust(widths[i]))
        print(f"  {' | '.join(cells)}")
    print()
