"""Pomiar wpływu GIL: sekwencyjnie vs wątki vs procesy dla zadań CPU-bound, I/O-bound i hashlib."""
from __future__ import annotations

import hashlib
import os
import sys
import sysconfig
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Callable, Sequence

from loganalyzer.analyzer import analyze_file
from loganalyzer.generate import write_logs
from loganalyzer.geo import GeoDatabase

MODES = ("sekwencyjnie", "wątki", "procesy")
LATENCY = 0.05


def io_task(ip: str) -> str:
    """Zadanie I/O-bound: zapytanie do symulowanego zdalnego API."""
    return GeoDatabase(latency=LATENCY, flaky=False).lookup(ip)


def hash_task(block: bytes) -> str:
    """Zadanie w C zwalniające GIL: SHA-256 dużego bloku."""
    return hashlib.sha256(block).hexdigest()


def _run(mode: str, func: Callable, items: Sequence, workers: int) -> None:
    if mode == "sekwencyjnie":
        for item in items:
            func(item)
        return
    executor = ThreadPoolExecutor if mode == "wątki" else ProcessPoolExecutor
    with executor(max_workers=workers) as pool:
        list(pool.map(func, items))


def _best(mode: str, func: Callable, items: Sequence, workers: int, repeats: int) -> float:
    times = []
    for _ in range(repeats):
        start = time.perf_counter()
        _run(mode, func, items, workers)
        times.append(time.perf_counter() - start)
    return min(times)


def run_benchmark(files: int | None = None, lines: int = 100_000, workers: int | None = None,
                  repeats: int = 2) -> list[tuple[str, str, float, float]]:
    """Zwraca wiersze (scenariusz, tryb, czas [s], przyspieszenie względem sekwencyjnego)."""
    cpus = os.cpu_count() or 1
    workers = workers or cpus
    files = files or max(4, cpus)
    ips = [f"10.0.{i // 250}.{i % 250 + 1}" for i in range(40)]
    blocks = [bytes(16_000_000) for _ in range(max(4, cpus))]
    rows: list[tuple[str, str, float, float]] = []

    with tempfile.TemporaryDirectory() as tmp:
        paths = [str(p) for p in write_logs(tmp, files=files, lines=lines)]
        scenarios = [
            (f"CPU: analiza logów ({files} plików x {lines} linii)", analyze_file, paths, workers),
            (f"I/O: {len(ips)} zapytań do API ({LATENCY * 1000:.0f} ms)", io_task, ips, max(workers, 8)),
            (f"hashlib: {len(blocks)} bloków po 16 MB (zwalnia GIL)", hash_task, blocks, workers),
        ]
        for name, func, items, n in scenarios:
            baseline = 0.0
            for mode in MODES:
                elapsed = _best(mode, func, items, n, repeats)
                baseline = baseline or elapsed
                rows.append((name, mode, elapsed, baseline / elapsed))
    return rows


def environment() -> str:
    gil = sys._is_gil_enabled() if hasattr(sys, "_is_gil_enabled") else True
    free = bool(sysconfig.get_config_var("Py_GIL_DISABLED"))
    return (f"Python {sys.version.split()[0]}, rdzenie CPU: {os.cpu_count()}, "
            f"free-threading build: {free}, GIL włączony: {gil}")


def format_markdown(rows: list[tuple[str, str, float, float]]) -> str:
    out = [f"_{environment()}_", "", "| Scenariusz | Tryb | Czas [s] | Przyspieszenie |", "|---|---|---:|---:|"]
    out += [f"| {name} | {mode} | {t:.2f} | {s:.2f}x |" for name, mode, t, s in rows]
    return "\n".join(out)


def main() -> None:
    table = format_markdown(run_benchmark())
    print(table)


if __name__ == "__main__":
    main()
