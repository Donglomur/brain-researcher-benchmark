"""One original clock and conservative logical I/O/retention ledger."""
import math
import time
from pathlib import Path
from core import encoded, identity, need
from safe_io import capture, durable_new, pin

class Budget:

    def __init__(self, limits, origin, root, clock=time.monotonic):
        need(set(limits) == {'wall_seconds', 'read_bytes', 'write_bytes', 'retained_bytes'}, 'Complete prospectively selected whole-program limits')
        need(all((type(v) in (int, float) and math.isfinite(v) and (v > 0) for v in limits.values())), 'Finite positive whole-program limits')
        self.limits, self.origin, self.clock = (dict(limits), origin, clock)
        self.end = origin + limits['wall_seconds']
        self.last = origin
        self.root = Path(root)
        self.reads = self.writes = self.retained = 0
        self.file_reads = self.file_writes = 0
        self.capture_observations = []
        self.reservations = {}
        self.events = []
        self.attempt = None
        self.subattempt = None
        self.tick()

    def tick(self):
        now = self.clock()
        cutoff = min(self.end, getattr(self, 'work_end', self.end), getattr(self, 'phase_deadline', self.end), self.attempt['deadline'] if self.attempt is not None else self.end, self.subattempt['deadline'] if self.subattempt is not None else self.end)
        need(type(now) in (float, int) and math.isfinite(now) and (self.last <= now <= cutoff), 'Original whole-program clock, no rollback or deadline extension')
        self.last = now
        return now

    def read(self, n):
        self.tick()
        need(type(n) is int and n >= 0 and (self.reads + n <= self.limits['read_bytes']), 'Whole-program logical read allocation')
        if self.subattempt is not None:
            need(self.reads + n - self.subattempt['read_origin'] <= self.subattempt['read_cap'], 'Shared-T tool read cap before I/O')
        if self.attempt is not None:
            need(self.reads + n - self.attempt['read_origin'] <= self.attempt['read_cap'], 'Original attempt conservative read allocation before I/O')
        self.reads += n

    def write(self, n):
        self.tick()
        need(type(n) is int and n >= 0 and (self.writes + n <= self.limits['write_bytes']) and (self.retained + n <= self.limits['retained_bytes']), 'Whole-program write/retention allocation')
        if self.attempt is not None:
            need(self.writes + n - self.attempt['write_origin'] <= self.attempt['write_cap'], 'Original attempt conservative write allocation before I/O')
        if self.subattempt is not None:
            need(self.writes + n - self.subattempt['write_origin'] <= self.subattempt['write_cap'], 'Shared-T tool write cap before I/O')
        self.writes += n
        self.retained += n

    def reserve_producer(self, phase_id, read_cap, write_cap, retained_cap):
        need(phase_id not in self.reservations, 'One reservation per complete owned phase')
        self.read(read_cap)
        self.tick()
        need(type(write_cap) is int and type(retained_cap) is int and (0 <= retained_cap <= write_cap) and (self.writes + write_cap <= self.limits['write_bytes']) and (self.retained + retained_cap <= self.limits['retained_bytes']), 'Full producer reservation')
        if self.subattempt is not None:
            need(self.writes + write_cap - self.subattempt['write_origin'] <= self.subattempt['write_cap'], 'Complete producer within original tool cap')
        self.writes += write_cap
        if self.attempt is not None:
            need(self.writes - self.attempt['write_origin'] <= self.attempt['write_cap'], 'Complete producer reservation within original attempt')
        self.retained += retained_cap
        self.reservations[phase_id] = {'read_upper': read_cap, 'write_upper': write_cap, 'retained_upper': retained_cap, 'settled': False}

    def begin_attempt(self, read_cap, write_cap, deadline):
        need(self.attempt is None and self.tick() < deadline <= self.end, 'Fresh nested attempt in original whole-study clock')
        self.attempt = {'read_origin': self.reads, 'write_origin': self.writes, 'read_cap': read_cap, 'write_cap': write_cap, 'deadline': deadline}

    def begin_subattempt(self, read_cap, write_cap, deadline):
        need(self.attempt is not None and self.subattempt is None and (self.tick() < deadline <= self.attempt['deadline']), 'Shared finite preliminary tool within original phase')
        self.subattempt = {'read_origin': self.reads, 'write_origin': self.writes, 'read_cap': read_cap, 'write_cap': write_cap, 'deadline': deadline}

    def end_subattempt(self):
        self.tick()
        self.subattempt = None

    def end_attempt(self):
        self.tick()
        self.attempt = None

    def settle(self, phase_id, retained, closed):
        self.tick()
        row = self.reservations[phase_id]
        need(not row['settled'] and closed is True and (type(retained) is int) and (0 <= retained <= row['retained_upper']), 'Only independently closed exact retained output settles credit')
        self.retained -= row['retained_upper'] - retained
        row.update(settled=True, retained_exact=retained)

    def read_file(self, path, expected, cap):
        observation = {}
        self.capture_observations.append(observation)
        body = capture(path, cap, expected, reserve=self.read, observation=observation)
        self.file_reads += len(body)
        return body

    def save(self, path, raw):
        self.write(len(raw))
        result = durable_new(path, raw)
        self.file_writes += len(raw)
        self.tick()
        return result

    def event(self, value):
        observed = self.tick()
        body = encoded({**value, 'index': len(self.events), 'ledger_clock': {'origin': self.origin, 'deadline': self.end, 'observed': observed}})
        need(len(body) <= getattr(self, 'max_event_bytes', len(body)) and len(self.events) < getattr(self, 'max_events', len(self.events) + 1), 'Complete prospectively bounded durable journal')
        name = f'{len(self.events):07d}.json'
        self.write(len(body))
        result = durable_new(self.root / name, body)
        self.file_writes += len(body)
        self.events.append({'path': name, **result})
        self.tick()
        return result

    def snapshot(self):
        return {'origin': self.origin, 'deadline': self.end, 'observed': self.tick(), 'logical_read_charge': self.reads, 'logical_write_charge': self.writes, 'retained_charge': self.retained, 'producer_reservations': self.reservations, 'successfully_captured_host_file_read_bytes': self.file_reads, 'acknowledged_capture_bytes_including_failed_prefixes': sum(r.get('acknowledged_bytes', 0) for r in self.capture_observations), 'unknown_capture_prefix_upper': sum(r.get('unknown_pending_upper', 0) for r in self.capture_observations), 'capture_observations': self.capture_observations, 'successfully_published_host_file_write_bytes': self.file_writes, 'measurement_scope': 'bounded source/metadata/artifact I/O plus conservative producer reservations; known returned prefixes and unknown read-error prefixes separate; no refund', 'kernel_native_IO_or_RSS_certified': False, 'events': self.events, 'scientific_qualification': False}

    def capture(self, path, expected, cap):
        return self.read_file(path, expected, cap)

    def publish(self, path, raw):
        return self.save(path, raw)
