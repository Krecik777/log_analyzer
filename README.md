# Analizator logów serwera WWW

Projekt zaliczeniowy z przedmiotu *Zaawansowane techniki programowania w języku Python*.

Aplikacja wczytuje duże pliki logów serwera WWW (format Apache), wyciąga z nich IP, daty, metody, adresy URL i kody HTTP, liczy statystyki (równolegle dla wielu plików) i opcjonalnie sprawdza kraje najczęstszych adresów IP w (symulowanej) bazie geolokalizacji. Zawiera też benchmark pokazujący działanie GIL.

Wymagania: Python 3.12+, **brak zależności zewnętrznych** (tylko biblioteka standardowa).

## Uruchomienie

```bash
python3 main.py generate dane --files 4 --lines 100000      # dane testowe
python3 main.py analyze dane                                # procesy (domyślnie)
python3 main.py analyze dane --mode threads --top 10
python3 main.py analyze dane --geo --geo-limit 50           # + kraje IP (wątki)
python3 main.py -v analyze dane                             # logowanie (-vv = DEBUG)
python3 main.py benchmark                                   # pomiar GIL
python3 -m unittest discover -s tests -t .                  # testy
```

## Struktura

```
main.py                    CLI (argparse)
loganalyzer/
  decorators.py            dekoratory funkcji i metod
  patterns.py              wyrażenia regularne
  reader.py                iterator ChunkReader
  pipeline.py              potok generatorów
  models.py                LogEntry, LogStats
  analyzer.py              analiza równoległa (procesy)
  geo.py                   baza IP + wątki (Queue, Lock)
  report.py                raport tekstowy
  generate.py              generator danych testowych
benchmarks/gil_benchmark.py
tests/test_all.py
```

## Tabela mapowania

| Zagadnienie | Gdzie w kodzie |
|---|---|
| Dekoratory funkcji (min. 2, w tym z parametrami, `functools.wraps`) | `loganalyzer/decorators.py` → `measure_time`, `retry(attempts, delay, exceptions)`, `ttl_cache(ttl)` |
| Użycie dekoratorów funkcji | `analyzer.py` → `analyze_files` (`@measure_time`); `geo.py` → `GeoDatabase.lookup` (`@ttl_cache` + `@retry`, nakładane) |
| Dekorator metody korzystający z `self` | `decorators.py` → `log_call`, `requires_data`; użyte w `models.py` → `LogStats.error_rate`, `top_ips`, `top_urls` |
| `@property` z setterem | `models.py` → `LogEntry.status`, `geo.py` → `GeoDatabase.latency` |
| `@classmethod` / `@staticmethod` | `models.py` → `LogEntry.from_match`, `LogEntry.parse_timestamp` |
| Iterator (`__iter__`, `__next__`) | `reader.py` → klasa `ChunkReader` |
| Generator (`yield`, `yield from`) | `pipeline.py` → `discover_logs`, `read_lines`, `parse_entries`; `generate.py` → `generate_lines` |
| Wyrażenie generujące | `pipeline.py` → `only_errors`; `models.py` → `LogStats.error_count` |
| Potok generatorów | `analyzer.py` → `analyze_file`: `read_lines` → `parse_entries` → `add_all` |
| Regex (grupy nazwane, `VERBOSE`) | `patterns.py` → `LOG_RE`, `IP_RE`, `LOG_NAME_RE`; walidacja `is_valid_ip`, `is_log_file` |
| Wątki + synchronizacja | `geo.py` → `lookup_many` (`Thread`, `Queue`, `Lock`), `GeoDatabase._lock` |
| Procesy (CPU-bound) | `analyzer.py` → `analyze_files(mode="processes")` (`ProcessPoolExecutor`) |
| Pomiar GIL | `benchmarks/gil_benchmark.py` |
| Obsługa błędów | `ValueError` w walidacji, `FileNotFoundError` w `ChunkReader`, kod wyjścia 2 w `main.py` |
| Elementy dodatkowe | testy (`tests/test_all.py`, 14 testów), CLI `argparse`, `logging`, type hints, raport z wykresami tekstowymi |

## Wyniki pomiarów

Uruchomienie: `python3 main.py benchmark` (najlepszy z 2 pomiarów).

_Python 3.13.18, 12 wątków CPU (6 rdzeni), standardowy build (GIL włączony)._

| Scenariusz | Tryb | Czas [s] | Przyspieszenie |
|---|---|---:|---:|
| CPU: analiza logów (12 plików x 100000 linii) | sekwencyjnie | 17.82 | 1.00x |
| CPU: analiza logów (12 plików x 100000 linii) | wątki | 17.93 | 0.99x |
| CPU: analiza logów (12 plików x 100000 linii) | procesy | 3.72 | 4.79x |
| I/O: 40 zapytań do API (50 ms) | sekwencyjnie | 2.01 | 1.00x |
| I/O: 40 zapytań do API (50 ms) | wątki | 0.20 | 9.95x |
| I/O: 40 zapytań do API (50 ms) | procesy | 0.48 | 4.17x |
| hashlib: 12 bloków po 16 MB (zwalnia GIL) | sekwencyjnie | 0.12 | 1.00x |
| hashlib: 12 bloków po 16 MB (zwalnia GIL) | wątki | 0.02 | 5.03x |
| hashlib: 12 bloków po 16 MB (zwalnia GIL) | procesy | 0.49 | 0.25x |
Wyniki zależą od sprzętu (mój: środowisko z 6 rdzeniami)

## Wnioski dotyczące GIL

W zadaniu CPU-bound (parsowanie regexem i agregacja w czystym Pythonie) wątki nie przyspieszyły pracy (0.99x), bo GIL pozwala w danej chwili wykonywać kod bajtowy tylko jednemu wątkowi, a narzut przełączania wręcz nieco spowolnił program. Procesy mają własny interpreter i własny GIL, więc rzeczywiście wykorzystały wielordzeniowy procesor (4.79x przy 12 wątkach). W zadaniu I/O-bound wątki dały prawie 10-krotne przyspieszenie (9.95x), ponieważ GIL jest zwalniany podczas oczekiwania (`time.sleep`, operacje sieciowe), a procesy działają wolniej (4.17x) przez koszt uruchomienia interpreterów. Dla `hashlib` wątki są szybsze od wersji sekwencyjnej (5.03x), bo SHA-256 na dużych blokach zwalnia GIL. Procesy wypadają tu najgorzej (0.25x), bo przesłanie 16 MB bloków przez `pickle` kosztuje więcej niż samo liczenie skrótu. Reguła: czekanie na I/O – wątki, czyste obliczenia w Pythonie – procesy, biblioteki w C zwalniające GIL – wątki wystarczą. GIL nie zwalnia też z synchronizacji, dlatego współdzielone dane w `geo.py` chronimy `Lock`-iem i `Queue`.## Napotkane problemy

- **Serializacja (pickle) w procesach.** Funkcja robocza (`analyze_file`) musi być zdefiniowana na poziomie modułu, a wynik (`LogStats`) składać się z prostych struktur (`Counter`), żeby dało się go odesłać i scalić (`merge`).
- **Linie przecięte na granicy bloku.** `ChunkReader` zachowuje niepełną ostatnią linię bloku i dokłada ją do następnego, dzięki czemu parser nigdy nie dostaje połowy linii.
- **Kolejność dekoratorów.** `@ttl_cache` musi być nałożony na `@retry` (a nie odwrotnie), żeby w cache trafiały tylko udane wyniki, a nie wyjątki.
- **Błędne dane.** Linie niepasujące do wzorca, z nieprawidłową datą lub kodem HTTP są zliczane w `LogStats.invalid` zamiast przerywać analizę.
- **Benchmark procesów dla `hashlib`.** Początkowo oczekiwane przyspieszenie nie wystąpiło, bo koszt przesyłania danych do procesów przewyższył zysk – opisane w wnioskach.
- **Start procesów na Windows (`spawn`).** Cały kod uruchamiający procesy jest chroniony przez `if __name__ == "__main__":`.
