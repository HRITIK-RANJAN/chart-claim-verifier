"""Disk cache of every tool output (design principle 3).

Keyed by (tool, tool version, figure image, series, x). Because every reading
is stored, baselines, decision rules and stopping policies can be re-run on a
CPU without calling any model again.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from pathlib import Path


class ReadingCache:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(self.path), check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS readings (k TEXT PRIMARY KEY, v TEXT)")
        self.hits = self.misses = 0

    @staticmethod
    def _key(parts: tuple) -> str:
        return hashlib.sha1(json.dumps([str(p) for p in parts]).encode()).hexdigest()

    def get(self, parts: tuple) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT v FROM readings WHERE k=?", (self._key(parts),)).fetchone()
        if row is None:
            self.misses += 1
            return None
        self.hits += 1
        return json.loads(row[0])

    def put(self, parts: tuple, value: dict) -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO readings VALUES (?, ?)", (self._key(parts), json.dumps(value)))
            self._db.commit()
