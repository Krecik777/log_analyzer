"""Wzorce wyrażeń regularnych: walidacja IP, parsowanie linii logu, nazwy plików logów."""
from __future__ import annotations

import re

OCTET = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"

IP_RE = re.compile(rf"{OCTET}(?:\.{OCTET}){{3}}")

LOG_RE = re.compile(rf"""
    (?P<ip>{OCTET}(?:\.{OCTET}){{3}})
    \s-\s-\s
    \[(?P<date>\d{{2}}/[A-Za-z]{{3}}/\d{{4}}(?::\d{{2}}){{3}}\s[+-]\d{{4}})\]
    \s"(?P<method>GET|POST|PUT|DELETE|HEAD|PATCH)\s(?P<url>\S+)\s[^"]*"
    \s(?P<status>\d{{3}})
    \s(?P<size>\d+|-)
""", re.VERBOSE)

LOG_NAME_RE = re.compile(r".+\.log(?:\.\d+)?", re.IGNORECASE)


def is_valid_ip(text: str) -> bool:
    """Sprawdza, czy napis jest poprawnym adresem IPv4."""
    return IP_RE.fullmatch(text) is not None


def is_log_file(name: str) -> bool:
    """Sprawdza, czy nazwa pliku wygląda na plik logu (np. access.log, access.log.1)."""
    return LOG_NAME_RE.fullmatch(name) is not None
