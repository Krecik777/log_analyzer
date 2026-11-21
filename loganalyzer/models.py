"""Modele danych: pojedynczy wpis logu i zagregowane statystyki."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Iterable
import re

from .decorators import log_call, requires_data


class LogEntry:
    """Pojedynczy wpis logu serwera WWW."""

    __slots__ = ("ip", "timestamp", "method", "url", "_status", "size")

    def __init__(self, ip: str, timestamp: datetime, method: str, url: str,
                 status: int, size: int = 0) -> None:
        self.ip = ip
        self.timestamp = timestamp
        self.method = method
        self.url = url
        self.size = size
        self.status = status

    @property
    def status(self) -> int:
        return self._status

    @status.setter
    def status(self, value: int) -> None:
        if not 100 <= value <= 599:
            raise ValueError(f"nieprawidłowy kod HTTP: {value}")
        self._status = value

    @property
    def is_error(self) -> bool:
        return self._status >= 400

    @classmethod
    def from_match(cls, match: re.Match[str]) -> "LogEntry":
        """Alternatywny konstruktor: tworzy wpis z dopasowania `LOG_RE`."""
        size = match["size"]
        return cls(match["ip"], cls.parse_timestamp(match["date"]), match["method"],
                   match["url"], int(match["status"]), 0 if size == "-" else int(size))

    @staticmethod
    def parse_timestamp(raw: str) -> datetime:
        """Parsuje datę w formacie `03/Oct/2026:10:00:01 +0200`."""
        return datetime.strptime(raw, "%d/%b/%Y:%H:%M:%S %z")


class LogStats:
    """Statystyki z wielu wpisów; obiekty można scalać (`merge`) po obliczeniach równoległych."""

    def __init__(self) -> None:
        self.total = 0
        self.invalid = 0
        self.bytes_sent = 0
        self.status: Counter[int] = Counter()
        self.ips: Counter[str] = Counter()
        self.urls: Counter[str] = Counter()
        self.hours: Counter[int] = Counter()

    def add(self, entry: LogEntry) -> None:
        self.total += 1
        self.bytes_sent += entry.size
        self.status[entry.status] += 1
        self.ips[entry.ip] += 1
        self.urls[entry.url] += 1
        self.hours[entry.timestamp.hour] += 1

    def add_all(self, entries: Iterable[LogEntry]) -> None:
        for entry in entries:
            self.add(entry)

    def merge(self, other: "LogStats") -> "LogStats":
        """Dodaje do siebie wyniki innego obiektu i zwraca `self`."""
        self.total += other.total
        self.invalid += other.invalid
        self.bytes_sent += other.bytes_sent
        self.status.update(other.status)
        self.ips.update(other.ips)
        self.urls.update(other.urls)
        self.hours.update(other.hours)
        return self

    @property
    def error_count(self) -> int:
        return sum(n for code, n in self.status.items() if code >= 400)

    @requires_data
    def error_rate(self) -> float:
        return self.error_count / self.total

    @requires_data
    @log_call
    def top_ips(self, n: int = 5) -> list[tuple[str, int]]:
        return self.ips.most_common(n)

    @requires_data
    @log_call
    def top_urls(self, n: int = 5) -> list[tuple[str, int]]:
        return self.urls.most_common(n)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, LogStats):
            return NotImplemented
        return (self.total, self.invalid, self.bytes_sent, self.status, self.ips, self.urls, self.hours) == \
               (other.total, other.invalid, other.bytes_sent, other.status, other.ips, other.urls, other.hours)
