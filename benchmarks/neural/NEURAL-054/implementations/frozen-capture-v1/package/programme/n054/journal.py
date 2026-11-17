"""Append-only source-owned observations with bounded, authenticated prefix seals.
SQLite is only a lookup index. Every lookup opens the immutable original JSON and
checks its pin; a prefix verifier reconstructs the chain from those original bytes.
No model, numerical dependency or scientific operand is involved.
"""
import sqlite3
from pathlib import Path
from .common import need, put, load, digest, relative, stream_pin


class Journal:
    def __init__(self, root, kind, entry_cap=16 << 20, data_root=None):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=False)
        self.data_root = Path(data_root) if data_root else self.root
        self.kind = kind; self.entry_cap = entry_cap
        self.db = sqlite3.connect(self.root / 'index.sqlite')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE entries (ordinal INTEGER PRIMARY KEY, path TEXT UNIQUE, bytes INTEGER, hash TEXT UNIQUE, chain TEXT)')
        self.db.commit(); self.count = 0; self.chain = None; self.bytes = 0

    def append(self, value, path=None):
        if path is None:
            path = self.root / 'entries' / ('%07d' % (self.count // 1000)) / ('%012d.json' % self.count)
            identity = put(path, value, self.entry_cap)
        else:
            path = Path(path); identity = stream_pin(path, self.entry_cap)
        need(identity['sha256'] == digest(value), 'Journal original bytes differ')
        rel = path.relative_to(self.data_root).as_posix(); relative(rel)
        chain = digest({'ordinal': self.count, 'prior': self.chain, 'original': identity})
        self.db.execute('INSERT INTO entries VALUES (?,?,?,?,?)',
                        (self.count, rel, identity['bytes'], identity['sha256'], chain))
        self.db.commit(); self.count += 1; self.bytes += identity['bytes']; self.chain = chain
        return identity['sha256']

    def __len__(self): return self.count

    def _value(self, row):
        need(row is not None, 'Original journal entry absent')
        _, path, size, sha, _ = row; relative(path)
        return load(self.data_root / path, self.entry_cap, {'bytes': size, 'sha256': sha})

    def __getitem__(self, ordinal):
        if ordinal < 0: ordinal += self.count
        return self._value(self.db.execute('SELECT * FROM entries WHERE ordinal=?', (ordinal,)).fetchone())

    def __iter__(self):
        cursor = self.db.execute('SELECT * FROM entries ORDER BY ordinal')
        for row in cursor: yield self._value(row)

    def get(self, identity):
        return self._value(self.db.execute('SELECT * FROM entries WHERE hash=?', (identity,)).fetchone())

    def contains(self, identity):
        return self.db.execute('SELECT 1 FROM entries WHERE hash=?', (identity,)).fetchone() is not None

    def snapshot(self):
        return {'schema': 'n054_journal_prefix_v2', 'kind': self.kind, 'count': self.count,
                'original_bytes': self.bytes, 'chain': self.chain}

    def verify(self, seal):
        need(seal['schema'] == 'n054_journal_prefix_v2' and seal['kind'] == self.kind and
             type(seal['count']) is int and 0 <= seal['count'] <= self.count, 'Journal prefix identity')
        chain = None; count = total = 0
        for row in self.db.execute('SELECT * FROM entries WHERE ordinal < ? ORDER BY ordinal', (seal['count'],)):
            ordinal, _, size, sha, stored_chain = row; need(ordinal == count, 'Missing original ordinal')
            value = self._value(row); need(digest(value) == sha, 'Original canonical identity')
            chain = digest({'ordinal': ordinal, 'prior': chain, 'original': {'bytes': size, 'sha256': sha}})
            need(chain == stored_chain, 'Journal chain substitution'); count += 1; total += size
        need(count == seal['count'] and total == seal['original_bytes'] and chain == seal['chain'], 'Prefix seal mismatch')
        return True
