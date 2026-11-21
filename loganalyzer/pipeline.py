"""Potok generatorów: wykrywanie plików -> linie -> wpisy -> filtrowanie."""
from __future__ import annotations

import os
from typing import Iterable, Iterator

from .models import LogEntry, LogStats
from .patterns import LOG_RE, is_log_file
from .reader import ChunkReader


def discover_logs(root: str | os.PathLike[str]) -> Iterator[str]:
    """Rekurencyjnie wyszukuje pliki logów w katalogu (lub zwraca sam plik)."""
    root = os.fspath(root)
    if os.path.isfile(root):
        yield root
        return
    with os.scandir(root) as it:
        for item in sorted(it, key=lambda e: e.name):
            if item.is_dir(follow_symlinks=False):
                yield from discover_logs(item.path)
            elif item.is_file() and is_log_file(item.name):
                yield item.path


def read_lines(path: str, chunk_size: int = 1 << 20) -> Iterator[str]:
    """Generator linii pliku oparty na iteratorze `ChunkReader`."""
    for chunk in ChunkReader(path, chunk_size):
        yield from chunk


def parse_entries(lines: Iterable[str], stats: LogStats) -> Iterator[LogEntry]:
    """Zamienia linie na wpisy; błędne linie zlicza w `stats.invalid`."""
    for line in lines:
        if not line.strip():
            continue
        match = LOG_RE.match(line)
        if match is None:
            stats.invalid += 1
            continue
        try:
            yield LogEntry.from_match(match)
        except ValueError:
            stats.invalid += 1


def only_errors(entries: Iterable[LogEntry]) -> Iterator[LogEntry]:
    """Wyrażenie generujące: tylko wpisy z kodem 4xx/5xx."""
    return (e for e in entries if e.is_error)
