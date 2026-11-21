"""Iterator czytający plik blokami zawierającymi tylko kompletne linie."""
from __future__ import annotations

from pathlib import Path
from typing import BinaryIO


class ChunkReader:
    """Iterator: każdy `next()` zwraca listę kompletnych linii z kolejnego bloku pliku."""

    def __init__(self, path: str | Path, chunk_size: int = 1 << 20) -> None:
        if chunk_size < 1:
            raise ValueError("chunk_size musi być >= 1")
        self.path = Path(path)
        self.chunk_size = chunk_size
        self._file: BinaryIO | None = None
        self._tail = b""
        self._done = False

    def __iter__(self) -> "ChunkReader":
        return self

    def __next__(self) -> list[str]:
        if self._done:
            raise StopIteration
        if self._file is None:
            self._file = open(self.path, "rb")
        while True:
            data = self._file.read(self.chunk_size)
            if not data:
                tail, self._tail = self._tail, b""
                self.close()
                if tail.strip():
                    return tail.decode("utf-8", "replace").splitlines()
                raise StopIteration
            data = self._tail + data
            cut = data.rfind(b"\n")
            if cut == -1:
                self._tail = data
                continue
            self._tail = data[cut + 1:]
            return data[:cut].decode("utf-8", "replace").splitlines()

    def close(self) -> None:
        """Zamyka plik i kończy iterację."""
        self._done = True
        if self._file is not None:
            self._file.close()
            self._file = None
