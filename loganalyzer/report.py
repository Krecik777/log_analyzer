"""Tekstowy raport z wyników analizy."""
from __future__ import annotations

from collections import Counter

from .models import LogStats


def _bars(rows: list[tuple[str, int]], width: int = 30) -> list[str]:
    if not rows:
        return []
    peak = max(count for _, count in rows)
    label = max(len(name) for name, _ in rows)
    return [f"  {name:<{label}} {count:>8}  {'#' * max(1, round(width * count / peak))}"
            for name, count in rows]


def render_report(stats: LogStats, countries: dict[str, str] | None = None, top: int = 5) -> str:
    """Buduje raport tekstowy; `countries` (ip -> kraj) jest opcjonalne."""
    out = [
        f"Poprawnych wpisów:      {stats.total}",
        f"Nieprawidłowych linii:  {stats.invalid}",
        f"Błędy HTTP (4xx/5xx):   {stats.error_rate():.1%}",
        f"Przesłano:              {stats.bytes_sent / 1_048_576:.1f} MiB",
        "",
        "Kody odpowiedzi:",
        *_bars([(str(code), n) for code, n in sorted(stats.status.items())]),
        "",
        f"Top {top} adresów IP:",
        *_bars(stats.top_ips(top)),
        "",
        f"Top {top} adresów URL:",
        *_bars(stats.top_urls(top)),
        "",
        "Ruch wg godzin:",
        *_bars([(f"{h:02d}:00", n) for h, n in sorted(stats.hours.items())]),
    ]
    if countries:
        by_country: Counter[str] = Counter()
        for ip, country in countries.items():
            by_country[country] += stats.ips.get(ip, 0)
        out += ["", "Ruch wg krajów (dla sprawdzonych adresów IP):", *_bars(by_country.most_common())]
    return "\n".join(out)
