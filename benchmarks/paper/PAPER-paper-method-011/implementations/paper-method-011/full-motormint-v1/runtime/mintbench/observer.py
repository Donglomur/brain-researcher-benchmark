"""Linux managed-cgroup observer; no collection or kernel access on import.

Requires a separately qualified private cgroup containing the entire controller,
children and Docker descendants. memory.peak is a conservative RSS upper bound,
not an exact process-RSS measurement. Inaccessible counters fail, never become 0.
"""
import os
import time
from pathlib import Path
from .validation import need, integer


class CgroupObserver:
    def __init__(self, cgroup_path, gpu_devices=()):
        self.path = Path(cgroup_path)
        need(self.path.is_absolute() and str(self.path).startswith('/sys/fs/cgroup/'), 'explicit Linux cgroup scope')
        need(all(not p.is_symlink() for p in (self.path, *self.path.parents)), 'no cgroup path alias')
        from .transport import gpu_arguments
        gpu_arguments(gpu_devices)
        self.gpu_devices = tuple(gpu_devices)
        self.active = None
        self.custody = {'sensor': 'private_cgroup_v2', 'RSS_semantics': 'memory.peak_upper_bound',
                        'gpu_seconds_policy': 'allocated physical-device count times owned observed wall seconds; not active utilization',
                        'gpu_devices': list(self.gpu_devices),
                        'token_policy': 'networkless submitted program; authoring-model attempts separately metered'}

    def _read(self, name):
        with (self.path / name).open('rb') as handle:
            raw = handle.read(65537)
        need(len(raw) <= 65536, 'bounded kernel counter')
        return raw.decode('ascii')

    def _snapshot(self):
        cpu = dict(line.split() for line in self._read('cpu.stat').splitlines())
        usec = int(cpu['usage_usec'])
        peak = int(self._read('memory.peak').strip())
        writes = 0
        for line in self._read('io.stat').splitlines():
            fields = dict(item.split('=', 1) for item in line.split()[1:])
            writes += int(fields.get('wbytes', '0'))
        for number in (usec, peak, writes):
            integer(number)
        return {'cpu_usec': usec, 'peak_upper_bound': peak, 'write_bytes': writes}

    def begin(self, attempt, origin, normal_end):
        need(self.active is None and origin <= time.monotonic() < normal_end, 'single observer under original deadline')
        # The operator must place this supervisor and the Docker descendants in
        # this dedicated group. Do not silently observe the whole host cgroup.
        observed = Path('/proc/self/cgroup').read_text()
        relative = str(self.path)[len('/sys/fs/cgroup'):]
        need(any(line == '0::' + relative for line in observed.splitlines()), 'supervisor in admitted private cgroup')
        self.active = (attempt, time.monotonic(), self._snapshot())

    def finish(self, attempt):
        need(self.active is not None and self.active[0] == attempt, 'observed owned attempt')
        _, start, before = self.active
        after = self._snapshot()
        self.active = None
        need(after['cpu_usec'] >= before['cpu_usec'] and after['write_bytes'] >= before['write_bytes'], 'monotone owned resource counters')
        elapsed = time.monotonic() - start
        return {'wall_seconds': elapsed,
                'cpu_seconds': (after['cpu_usec'] - before['cpu_usec']) / 1e6,
                'gpu_seconds': elapsed * len(self.gpu_devices), 'token_count': 0,
                'bytes_written': after['write_bytes'] - before['write_bytes'],
                'peak_rss_bytes': after['peak_upper_bound'], 'custody': self.custody}
