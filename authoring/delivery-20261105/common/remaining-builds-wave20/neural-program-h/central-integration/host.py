"""Concrete central custody and inherited clocks; caller module is source-bound."""
import os
from pathlib import Path
import resource
import shutil
import signal
import time


class Host:
    def __init__(self, entry_start, source_reads):
        self.entry_start = entry_start; self.origin = entry_start; self.deadline = entry_start+120
        self.read_limit = 268435456; self.write_limit = 2097152
        self.reads = source_reads; self.writes = 0; self.root = None; self.prepared = False
        self.original_origin_admitted = False

    def now(self): return time.monotonic()

    def tick(self):
        now = self.now()
        u.need(self.origin <= now < self.deadline, 'inherited central deadline or clock expired')
        return now

    def adopt_origin(self, origin):
        origin = u.finite(origin)
        u.need(origin <= self.entry_start <= self.now() and self.now() < origin+120,
               'inherited actual root origin; no late startup or clock reset')
        self.origin = origin; self.original_origin_admitted = True
        self.arm(origin+120)

    def arm(self, deadline):
        deadline = u.finite(deadline); u.need(deadline > self.now(), 'remaining original deadline')
        self.deadline = deadline
        signal.setitimer(signal.ITIMER_REAL, max(.001, deadline-self.now()))

    def reserve(self, count):
        self.tick(); count = u.integer(count)
        u.need(self.reads+count <= self.read_limit, 'central logical read reservation exhausted')
        self.reads += count

    def reserve_write(self, count):
        self.tick(); count = u.integer(count)
        u.need(self.writes+count <= self.write_limit, 'central logical write reservation exhausted')
        self.writes += count

    def read(self, path, cap, expected=None, readonly=False):
        return u.capture(path, cap, expected, self.reserve, self.tick, readonly=readonly)

    def configure(self, limits):
        u.need(u.integer(limits['read_bytes'], 1) >= self.reads, 'full central read allowance')
        self.read_limit = limits['read_bytes']; self.write_limit = u.integer(limits['write_bytes'], 1)
        memory = u.integer(limits['host_memory_bytes'], 1073741824)
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))

    def prepare(self, root, original, other_reserve, limits):
        root = u.path(root)
        u.need(not os.path.lexists(root) and root.parent.is_dir(), 'fresh central output')
        # Original whole write ceiling is a conservative storage component, not
        # measured occupied bytes; unrelated holds and free floor stay separate.
        need_free = (u.integer(other_reserve)+u.integer(original['resources']['whole_write_bytes'], 1)
                     +u.integer(limits['retained_bytes'], 1)+u.integer(limits['free_floor_bytes'], 1))
        u.need(shutil.disk_usage(root.parent).free >= need_free, 'full original+central storage and unrelated holds')
        os.mkdir(root, 0o700); u.sync_dir(root.parent); self.root = root; self.prepared = True

    def save(self, name, value, cap):
        u.need(self.prepared and name in ('INTENT.json','CAMPAIGN.json','INVOCATION.json','CALLER.json',
               'RESULT.json','FAILURE.json','caller.stdout','caller.stderr'), 'fixed central evidence member')
        raw = value if type(value) is bytes else u.encode(value)
        return u.save(self.root/name, raw, cap, self.reserve_write, self.tick)

    def launch(self, argv, normal_end, cleanup_end, repo):
        # Concrete bound implementation; no FinishedProcess/candidate callback.
        env = {'PATH': os.defpath, 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'}
        return caller.run(argv, normal_end, cleanup_end, env, str(repo))

    def record(self):
        return {'entry_start': self.entry_start, 'original_origin': self.origin,
                'original_origin_admitted': self.original_origin_admitted, 'current_deadline': self.deadline,
                'observed': self.now(), 'read_reserved_bytes': self.reads, 'write_reserved_bytes': self.writes,
                'read_limit': self.read_limit, 'write_limit': self.write_limit,
                'physical_IO_and_total_RSS_measured': False,
                'snapshot_precedes_following_receipt_publication': True}
