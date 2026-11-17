"""Prospective logical bounds and inherited cooperative clock; no hard CPU claim."""
import math
import time
from .protocol import Refusal, require

class Budget:
    FIELDS = {'original_origin', 'deadline', 'max_input_elements', 'max_logical_live_bytes', 'max_work_units', 'max_state_bytes', 'max_records'}
    def __init__(self, profile, clock=time.monotonic):
        require(type(profile) is dict and set(profile) == self.FIELDS, 'budget_schema')
        for k in ('original_origin', 'deadline'):
            require(type(profile[k]) in (int, float) and math.isfinite(profile[k]), 'budget_clock')
        require(profile['deadline'] > profile['original_origin'], 'budget_interval')
        for k in self.FIELDS - {'original_origin', 'deadline'}:
            require(type(profile[k]) is int and 0 < profile[k] <= 2**53, 'budget_cap')
        self.profile = dict(profile)
        self.clock = clock
        self.used = {'input_elements': 0, 'work_units': 0, 'records': 0, 'state_bytes': 0}
        self.resident = 0
        self.peak_logical_live = 0
        self.tick()

    def snapshot(self):
        return {'used': dict(self.used), 'reserved_resident_bytes': self.resident,
                'peak_logical_live_bytes': self.peak_logical_live, 'profile': dict(self.profile),
                'native_workspace_cpu_total_rss_and_hard_termination': 'unqualified'}

    def tick(self):
        now = self.clock()
        if not (type(now) in (int, float) and math.isfinite(now) and self.profile['original_origin'] <= now < self.profile['deadline']):
            raise Refusal('clock_outside_original_interval', self.snapshot())

    def stage(self, *, elements=0, work=0, live=0, records=0):
        self.tick()
        for v in (elements, work, live, records):
            require(type(v) is int and v >= 0, 'negative_resource_reservation')
        proposed = dict(self.used)
        proposed['input_elements'] += elements
        proposed['work_units'] += work
        proposed['records'] += records
        for k in ('input_elements', 'work_units', 'records'):
            if proposed[k] > self.profile['max_' + k]:
                raise Refusal('resource_' + k, self.snapshot())
        peak = self.resident + live
        if peak > self.profile['max_logical_live_bytes']:
            raise Refusal('resource_logical_live_bytes', self.snapshot())
        self.used = proposed
        self.peak_logical_live = max(self.peak_logical_live, peak)

    def hold(self, size):
        self.stage(live=size)
        self.resident += size

    def release(self, size):
        require(type(size) is int and 0 <= size <= self.resident, 'resident_release')
        self.resident -= size

    def state(self, body):
        # Caller preflights the primitive/list geometry before constructing body.
        require(type(body) is bytes, 'serialized_state_type')
        self.stage(live=2 * len(body))
        if len(body) > self.profile['max_state_bytes']:
            raise Refusal('resource_state_bytes', self.snapshot())
        self.used['state_bytes'] += len(body)
        self.tick()


def failure(exc, phase, budget):
    return {'phase': phase, 'status': 'failed', 'error_type': type(exc).__name__,
            'error_code': exc.code if isinstance(exc, Refusal) else 'numerical_or_runtime_failure',
            'costs': budget.snapshot()}


def is_fatal(exc):
    return isinstance(exc, Refusal) and (exc.code.startswith('resource_') or exc.code.startswith('clock_'))
