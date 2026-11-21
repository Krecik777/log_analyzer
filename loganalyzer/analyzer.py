"""Analiza plików logów: sekwencyjnie, wątkami lub procesami (zadanie CPU-bound)."""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Iterable

from .decorators import measure_time
from .models import LogStats
from .pipeline import parse_entries, read_lines

MODES = ("sequential", "threads", "processes")


def analyze_file(path: str) -> LogStats:
    """Analizuje jeden plik logu (funkcja najwyższego poziomu, by dała się serializować)."""
    stats = LogStats()
    stats.add_all(parse_entries(read_lines(path), stats))
    return stats


@measure_time
def analyze_files(paths: Iterable[str], mode: str = "processes",
                  workers: int | None = None) -> LogStats:
    """Analizuje wiele plików i scala wyniki cząstkowe w jeden obiekt `LogStats`."""
    files = [str(p) for p in paths]
    if not files:
        raise ValueError("brak plików do analizy")
    if mode not in MODES:
        raise ValueError(f"nieznany tryb: {mode!r} (dozwolone: {', '.join(MODES)})")
    if mode == "sequential":
        parts = [analyze_file(p) for p in files]
    else:
        executor = ProcessPoolExecutor if mode == "processes" else ThreadPoolExecutor
        with executor(max_workers=workers) as pool:
            parts = list(pool.map(analyze_file, files))
    total = LogStats()
    for part in parts:
        total.merge(part)
    return total
