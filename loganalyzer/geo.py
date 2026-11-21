"""Lokalna, symulowana baza geolokalizacji IP z opóźnieniem (zadanie I/O-bound) i pula wątków."""
from __future__ import annotations

import threading
import time
import zlib
from queue import Queue
from typing import Iterable

from .decorators import retry, ttl_cache


class GeoDatabase:
    """Symuluje zdalne API: każde zapytanie trwa `latency` s, część pierwszych prób kończy się błędem."""

    COUNTRIES = ("PL", "DE", "US", "FR", "GB", "CZ", "UA", "SE")

    def __init__(self, latency: float = 0.05, flaky: bool = True) -> None:
        self.latency = latency
        self.flaky = flaky
        self.calls = 0
        self._attempts: dict[str, int] = {}
        self._lock = threading.Lock()

    @property
    def latency(self) -> float:
        return self._latency

    @latency.setter
    def latency(self, value: float) -> None:
        if value < 0:
            raise ValueError("latency nie może być ujemne")
        self._latency = value

    @ttl_cache(ttl=300)
    @retry(attempts=3, delay=0.01, exceptions=(ConnectionError,))
    def lookup(self, ip: str) -> str:
        """Zwraca kod kraju dla adresu IP (z cache i ponawianiem przy błędach połączenia)."""
        time.sleep(self.latency)
        code = zlib.crc32(ip.encode())
        with self._lock:
            self.calls += 1
            attempt = self._attempts[ip] = self._attempts.get(ip, 0) + 1
        if self.flaky and attempt == 1 and code % 7 == 0:
            raise ConnectionError(f"timeout przy zapytaniu o {ip}")
        return self.COUNTRIES[code % len(self.COUNTRIES)]


def lookup_many(db: GeoDatabase, ips: Iterable[str], workers: int = 8) -> dict[str, str]:
    """Współbieżnie sprawdza adresy IP: wątki pobierają zadania z `Queue`, wyniki chroni `Lock`."""
    if workers < 1:
        raise ValueError("workers musi być >= 1")
    unique = list(dict.fromkeys(ips))
    tasks: Queue[str | None] = Queue()
    results: dict[str, str] = {}
    lock = threading.Lock()

    def worker() -> None:
        while (ip := tasks.get()) is not None:
            try:
                country = db.lookup(ip)
            except ConnectionError:
                country = "??"
            with lock:
                results[ip] = country

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(workers)]
    for t in threads:
        t.start()
    for ip in unique:
        tasks.put(ip)
    for _ in threads:
        tasks.put(None)
    for t in threads:
        t.join()
    return results
