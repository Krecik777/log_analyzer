"""Dekoratory funkcji (measure_time, retry, ttl_cache) i metod (log_call, requires_data)."""
from __future__ import annotations

import functools
import logging
import threading
import time
from typing import Any, Callable, TypeVar

log = logging.getLogger(__name__)
F = TypeVar("F", bound=Callable[..., Any])


def measure_time(func: F) -> F:
    """Mierzy czas wykonania funkcji; wynik zapisuje w `wrapper.last_elapsed`."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            wrapper.last_elapsed = time.perf_counter() - start
            log.info("%s: %.4f s", func.__name__, wrapper.last_elapsed)

    wrapper.last_elapsed = 0.0
    return wrapper  # type: ignore[return-value]


def retry(attempts: int = 3, delay: float = 0.0,
          exceptions: tuple[type[BaseException], ...] = (Exception,)) -> Callable[[F], F]:
    """Dekorator z parametrami: ponawia wywołanie po wyjątku z listy `exceptions`."""
    if attempts < 1:
        raise ValueError("attempts musi być >= 1")

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    log.warning("%s: próba %d/%d nieudana: %s", func.__name__, attempt, attempts, exc)
                    if attempt == attempts:
                        raise
                    time.sleep(delay)

        return wrapper  # type: ignore[return-value]

    return decorator


def ttl_cache(ttl: float = 60.0) -> Callable[[F], F]:
    """Cache wyników z czasem życia `ttl` sekund; bezpieczny wątkowo (Lock)."""
    if ttl <= 0:
        raise ValueError("ttl musi być dodatni")

    def decorator(func: F) -> F:
        store: dict[tuple, tuple[float, Any]] = {}
        lock = threading.Lock()

        @functools.wraps(func)
        def wrapper(*args: Any) -> Any:
            with lock:
                hit = store.get(args)
                if hit is not None and time.monotonic() - hit[0] < ttl:
                    return hit[1]
            value = func(*args)
            with lock:
                store[args] = (time.monotonic(), value)
            return value

        def cache_clear() -> None:
            with lock:
                store.clear()

        wrapper.cache_clear = cache_clear  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator


def log_call(method: F) -> F:
    """Dekorator metody: loguje wywołanie wraz z nazwą klasy (korzysta z `self`)."""

    @functools.wraps(method)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        log.debug("%s.%s%s", type(self).__name__, method.__name__, args)
        return method(self, *args, **kwargs)

    return wrapper  # type: ignore[return-value]


def requires_data(method: F) -> F:
    """Dekorator metody: blokuje wywołanie, gdy obiekt nie zawiera danych (`self.total == 0`)."""

    @functools.wraps(method)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        if not self.total:
            raise ValueError(f"{method.__name__}: brak danych do analizy")
        return method(self, *args, **kwargs)

    return wrapper  # type: ignore[return-value]
