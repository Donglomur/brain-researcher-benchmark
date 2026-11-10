"""Bounded source-owned immutable cache bindings; no whole-query RAM cache.
Original output/state files and journal receipts remain authoritative products.
This ordinary SQLite index contains data-only JSON, never executable objects.
"""
import json
import sqlite3
from pathlib import Path
from .common import canonical, digest, pin, need


class Bindings:
    def __init__(self, path, value_cap=16 << 20):
        path = Path(path); need(not path.exists(), 'Fresh binding index')
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path); self.cap = value_cap
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE bindings (key TEXT PRIMARY KEY, value BLOB, hash TEXT)')
        self.db.commit()

    def __contains__(self, key):
        return self.db.execute('SELECT 1 FROM bindings WHERE key=?', (digest(key),)).fetchone() is not None

    def __setitem__(self, key, value):
        body = canonical(value); need(len(body) <= self.cap, 'Bounded immutable binding')
        self.db.execute('INSERT INTO bindings VALUES (?,?,?)', (digest(key), body, pin(body)['sha256']))
        self.db.commit()

    def __getitem__(self, key):
        row = self.db.execute('SELECT value,hash FROM bindings WHERE key=?', (digest(key),)).fetchone()
        need(row is not None, 'Missing immutable binding')
        body, sha = row; need(len(body) <= self.cap and pin(body)['sha256'] == sha, 'Binding identity')
        return json.loads(body)
