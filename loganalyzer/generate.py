"""Generator syntetycznych logów serwera WWW (dane testowe)."""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

URLS = ("/index.html", "/login", "/admin", "/api/items", "/api/users", "/static/app.js",
        "/static/style.css", "/contact", "/products/42", "/search?q=python")
METHODS = ("GET", "GET", "GET", "POST", "PUT", "DELETE")
STATUSES = (200,) * 14 + (301, 304, 304, 400, 401, 403, 404, 404, 500, 503)
TZ = timezone(timedelta(hours=1))


def generate_lines(count: int, rng: random.Random, ips: list[str],
                   bad_ratio: float = 0.01) -> Iterator[str]:
    """Generator `count` linii w formacie Apache; ok. `bad_ratio` linii jest uszkodzonych."""
    moment = datetime(2026, 10, 1, tzinfo=TZ)
    for _ in range(count):
        moment += timedelta(seconds=rng.randint(0, 3))
        if rng.random() < bad_ratio:
            yield rng.choice(("uszkodzona linia", "999.1.1.1 - - [zła data] \"GET / HTTP/1.1\" 200 1", "-"))
            continue
        yield (f'{rng.choice(ips)} - - [{moment.strftime("%d/%b/%Y:%H:%M:%S %z")}] '
               f'"{rng.choice(METHODS)} {rng.choice(URLS)} HTTP/1.1" '
               f'{rng.choice(STATUSES)} {rng.randint(0, 50_000)}')


def write_logs(directory: str | Path, files: int = 4, lines: int = 100_000,
               seed: int = 42, unique_ips: int = 200) -> list[Path]:
    """Zapisuje `files` plików `access_N.log` po `lines` linii i zwraca ich ścieżki."""
    if files < 1 or lines < 1:
        raise ValueError("files i lines muszą być >= 1")
    rng = random.Random(seed)
    ips = [f"{rng.randint(1, 223)}.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}"
           for _ in range(unique_ips)]
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in range(1, files + 1):
        path = target / f"access_{i}.log"
        with open(path, "w", encoding="utf-8") as fh:
            fh.writelines(f"{line}\n" for line in generate_lines(lines, rng, ips))
        paths.append(path)
    return paths
