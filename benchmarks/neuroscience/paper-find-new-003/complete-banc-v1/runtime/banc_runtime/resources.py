"""Whole-attempt logical accounting; physical process enclosure is a gate."""
from dataclasses import dataclass, field
import time
from .codec import need


@dataclass(frozen=True)
class Limits:
    read_bytes: int
    output_bytes: int
    row_count: int
    pair_work: int
    jobs: int
    deadline_ns: int

    def __post_init__(self):
        need(all(type(v) is int and v > 0 for v in self.__dict__.values()),
             'positive whole-attempt limits')


@dataclass
class Meter:
    limits: Limits
    read_reserved: int = 0
    read_completed: int = 0
    output_reserved: int = 0
    output_completed: int = 0
    rows: int = 0
    pair_work: int = 0
    jobs: int = 0
    events: list = field(default_factory=list)
    deadline_checks: int = 0

    def check_deadline(self, where):
        now = time.monotonic_ns()
        self.deadline_checks += 1
        if len(self.events)<128 or now>self.limits.deadline_ns:
            self.events.append({'where':where,'monotonic_ns':now})
        need(now <= self.limits.deadline_ns, 'whole-attempt deadline exceeded: ' + where)

    def _reserve(self, field, amount, ceiling):
        need(type(amount) is int and amount >= 0, 'nonnegative reservation')
        before = getattr(self, field)
        need(before + amount <= ceiling, 'whole-attempt resource refusal: ' + field)
        setattr(self, field, before + amount)

    def reserve_read(self, n):
        self._reserve('read_reserved', n, self.limits.read_bytes)

    def complete_read(self, n):
        need(type(n) is int and n>=0, 'nonnegative read completion')
        self.read_completed += n
        need(self.read_completed <= self.read_reserved, 'read completion exceeds reservation')

    def reserve_output(self, n):
        self._reserve('output_reserved', n, self.limits.output_bytes)

    def complete_output(self, n):
        need(type(n) is int and n>=0, 'nonnegative output completion')
        self.output_completed += n
        need(self.output_completed <= self.output_reserved, 'output completion exceeds reservation')

    def admit_rows(self, n):
        self._reserve('rows', n, self.limits.row_count)

    def admit_pairs(self, n):
        self._reserve('pair_work', n, self.limits.pair_work)

    def start_job(self):
        self.check_deadline('before_job')
        self._reserve('jobs', 1, self.limits.jobs)

    def report(self):
        return {**{k:v for k,v in self.__dict__.items() if k!='limits'},
                'limits':dict(self.limits.__dict__),
                'physical_IO_RSS_CPU_isolation_qualified':False,
                'failed_attempt_cost_refunds':False}
