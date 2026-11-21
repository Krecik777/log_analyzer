"""Testy jednostkowe projektu."""
import tempfile
import time
import unittest
from pathlib import Path

from loganalyzer.analyzer import analyze_file, analyze_files
from loganalyzer.decorators import retry, ttl_cache
from loganalyzer.generate import write_logs
from loganalyzer.geo import GeoDatabase, lookup_many
from loganalyzer.models import LogEntry, LogStats
from loganalyzer.patterns import LOG_RE, is_log_file, is_valid_ip
from loganalyzer.pipeline import discover_logs, only_errors, parse_entries, read_lines
from loganalyzer.reader import ChunkReader

LINE = '192.168.1.10 - - [03/Oct/2026:10:00:01 +0200] "GET /index.html HTTP/1.1" 200 512'


class PatternTests(unittest.TestCase):
    def test_ip_validation(self):
        self.assertTrue(is_valid_ip("192.168.1.255"))
        for bad in ("256.1.1.1", "1.2.3", "a.b.c.d", "1.2.3.4.5"):
            self.assertFalse(is_valid_ip(bad), bad)

    def test_log_line_named_groups(self):
        m = LOG_RE.match(LINE)
        self.assertEqual((m["ip"], m["method"], m["url"], m["status"], m["size"]),
                         ("192.168.1.10", "GET", "/index.html", "200", "512"))

    def test_log_file_names(self):
        self.assertTrue(is_log_file("access.log"))
        self.assertTrue(is_log_file("access.log.3"))
        self.assertFalse(is_log_file("notes.txt"))


class ReaderTests(unittest.TestCase):
    def test_chunks_contain_whole_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.log"
            lines = [f"linia-{i}" for i in range(500)]
            path.write_text("\n".join(lines), encoding="utf-8")
            self.assertEqual(list(read_lines(str(path), chunk_size=17)), lines)

    def test_invalid_chunk_size_and_missing_file(self):
        with self.assertRaises(ValueError):
            ChunkReader("x", chunk_size=0)
        with self.assertRaises(FileNotFoundError):
            next(ChunkReader("nie_istnieje.log"))


class ModelTests(unittest.TestCase):
    def test_status_setter_validates(self):
        entry = LogEntry.from_match(LOG_RE.match(LINE))
        with self.assertRaises(ValueError):
            entry.status = 999
        entry.status = 404
        self.assertTrue(entry.is_error)

    def test_stats_require_data_and_merge(self):
        with self.assertRaises(ValueError):
            LogStats().error_rate()
        a, b = LogStats(), LogStats()
        stats = LogStats()
        entries = list(parse_entries([LINE, "śmieci", LINE.replace(" 200 ", " 500 ")], stats))
        a.add_all(entries[:1])
        b.add_all(entries[1:])
        merged = LogStats().merge(a).merge(b)
        self.assertEqual(merged.total, 2)
        self.assertEqual(merged.error_rate(), 0.5)
        self.assertEqual(stats.invalid, 1)
        self.assertEqual(len(list(only_errors(entries))), 1)


class DecoratorTests(unittest.TestCase):
    def test_retry_succeeds_after_failures(self):
        calls = []

        @retry(attempts=3, exceptions=(ConnectionError,))
        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise ConnectionError("x")
            return "ok"

        self.assertEqual(flaky(), "ok")
        self.assertEqual(flaky.__name__, "flaky")

    def test_retry_raises_after_limit(self):
        @retry(attempts=2, exceptions=(ConnectionError,))
        def always():
            raise ConnectionError("x")

        with self.assertRaises(ConnectionError):
            always()

    def test_ttl_cache(self):
        calls = []

        @ttl_cache(ttl=0.1)
        def f(x):
            calls.append(x)
            return x * 2

        self.assertEqual((f(2), f(2)), (4, 4))
        self.assertEqual(len(calls), 1)
        time.sleep(0.15)
        f(2)
        self.assertEqual(len(calls), 2)


class GeoTests(unittest.TestCase):
    def test_lookup_many_returns_every_ip(self):
        db = GeoDatabase(latency=0.001)
        ips = [f"10.0.0.{i}" for i in range(1, 60)]
        result = lookup_many(db, ips + ips[:10], workers=6)
        self.assertEqual(set(result), set(ips))
        self.assertNotIn("??", result.values())
        self.assertGreater(db.calls, len(ips))

    def test_negative_latency_rejected(self):
        with self.assertRaises(ValueError):
            GeoDatabase(latency=-1)


class AnalyzerTests(unittest.TestCase):
    def test_all_modes_give_same_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_logs(tmp, files=3, lines=2000)
            found = list(discover_logs(tmp))
            self.assertEqual(len(found), 3)
            results = [analyze_files(found, mode=m, workers=2)
                       for m in ("sequential", "threads", "processes")]
            self.assertEqual(results[0], results[1])
            self.assertEqual(results[0], results[2])
            self.assertEqual(results[0].total + results[0].invalid, 6000)
            self.assertEqual(analyze_file(str(paths[0])).total + analyze_file(str(paths[0])).invalid, 2000)

    def test_bad_arguments(self):
        with self.assertRaises(ValueError):
            analyze_files([])
        with self.assertRaises(ValueError):
            analyze_files(["x"], mode="nope")


if __name__ == "__main__":
    unittest.main()
