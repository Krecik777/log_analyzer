"""Interfejs wiersza poleceń: generate | analyze | benchmark."""
from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from pathlib import Path

from loganalyzer.analyzer import MODES, analyze_files
from loganalyzer.generate import write_logs
from loganalyzer.geo import GeoDatabase, lookup_many
from loganalyzer.pipeline import discover_logs
from loganalyzer.report import render_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analizator logów serwera WWW")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="więcej logów (-v INFO, -vv DEBUG)")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="wygeneruj przykładowe logi")
    gen.add_argument("out", type=Path, help="katalog docelowy")
    gen.add_argument("--files", type=int, default=4)
    gen.add_argument("--lines", type=int, default=100_000)
    gen.add_argument("--seed", type=int, default=42)

    ana = sub.add_parser("analyze", help="przeanalizuj pliki lub katalogi z logami")
    ana.add_argument("paths", nargs="+", type=Path)
    ana.add_argument("--mode", choices=MODES, default="processes")
    ana.add_argument("--workers", type=int, default=None)
    ana.add_argument("--top", type=int, default=5)
    ana.add_argument("--geo", action="store_true", help="sprawdź kraje najczęstszych IP (wątki)")
    ana.add_argument("--geo-limit", type=int, default=50)

    sub.add_parser("benchmark", help="pomiar GIL: sekwencyjnie / wątki / procesy")
    return parser


def cmd_generate(args: argparse.Namespace) -> None:
    paths = write_logs(args.out, args.files, args.lines, args.seed)
    print(f"Zapisano {len(paths)} plików w {args.out}")


def cmd_analyze(args: argparse.Namespace) -> None:
    files = [f for root in args.paths for f in discover_logs(root)]
    stats = analyze_files(files, mode=args.mode, workers=args.workers)
    countries = None
    if args.geo:
        top_ips = [ip for ip, _ in stats.top_ips(args.geo_limit)]
        countries = lookup_many(GeoDatabase(), top_ips)
    print(f"Pliki: {len(files)}, tryb: {args.mode}, czas: {analyze_files.last_elapsed:.2f} s\n")
    print(render_report(stats, countries, args.top))


def cmd_benchmark(_: argparse.Namespace) -> None:
    from benchmarks.gil_benchmark import format_markdown, run_benchmark
    print(format_markdown(run_benchmark()))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    level = (logging.WARNING, logging.INFO, logging.DEBUG)[min(args.verbose, 2)]
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
    handlers = {"generate": cmd_generate, "analyze": cmd_analyze, "benchmark": cmd_benchmark}
    try:
        handlers[args.command](args)
    except (OSError, ValueError) as exc:
        print(f"Błąd: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
