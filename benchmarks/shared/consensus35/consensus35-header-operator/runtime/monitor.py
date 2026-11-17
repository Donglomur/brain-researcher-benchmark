"""Bounded lane-local diagnostics; no I/O on import and no scientific transforms.
A complete record can identify this monitor's decision, never an OS OOM.
Missing/empty/partial records remain unknown. The unchanged WallFuse can still
terminate first (124), and external SIGKILL can prevent any durable outcome.
"""
import json
import os
from pathlib import Path
import stat
import threading
import time

CAP = 8192
INTERVAL = .02
KINDS = frozenset(('closed', 'rss_limit', 'observer_exception',
                   'monitor_exception', 'monitor_join_timeout'))
PHASES = frozenset(('initial', 'background', 'final', 'checkpoint', 'thread_start', 'join'))

def need(ok, why):
    if not ok:
        raise ValueError(why)

def dumps(value):
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()
    need(len(raw) <= CAP, 'bounded monitor record')
    return raw

def _exclusive(path):
    p = Path(path)
    need(p.is_absolute() and '..' not in p.parts and
         not any(q.is_symlink() for q in (p, *p.parents)), 'ordinary monitor path')
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    s = os.fstat(fd)
    need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'ordinary exclusive monitor file')
    return fd

def _persist(fd, value):
    raw = dumps(value)
    # A short write or fsync error is not repaired/retried; the retained record
    # may be partial. Its parent must never interpret a prefix as a full event.
    need(os.write(fd, raw) == len(raw), 'complete monitor record write')
    os.fsync(fd)

class DurableMonitor:
    """One start record plus one terminal record inside the operator partition."""
    def __init__(self, limit, observe, snapshot, start_path, outcome_path, stage):
        need(type(limit) is int and limit > 0 and stage in ('intake', 'audit'), 'monitor binding')
        self.limit, self.observe, self.snapshot, self.stage = limit, observe, snapshot, stage
        self.start_path, self.outcome_path = start_path, outcome_path
        self.maximum, self.samples = None, 0
        self.stop, self.lock = threading.Event(), threading.RLock()
        self.thread = threading.Thread(target=self._watch, daemon=True)
        self.fd = None
        self.finished = False
        self.outcome = None

    def _base(self):
        return dict(schema='voltron-durable-monitor-v1', stage=self.stage,
                    pid=os.getpid(), group_id=os.getpgrp(), threshold_bytes=self.limit,
                    sampling_interval_seconds=INTERVAL,
                    hard_os_memory_limit=False, os_OOM_claim=False)

    def _terminal(self, kind, phase, sample=None, error=None):
        value = self._base()
        value.update(kind=kind, observation_phase=phase, observed_peak_rss_bytes=self.maximum,
                     sample_rss_bytes=sample, samples=self.samples, error_type=error,
                     observed_monotonic=time.monotonic(), accounting=self.snapshot(),
                     accounting_complete=False,
                     accounting_meaning='Last committed explicit source-read and pre-admitted byte-work checkpoint; '
                     'pending work and OS/system I/O are not measured. Not a final worker ledger.')
        _persist(self.fd, value)
        self.outcome = value
        self.finished = True

    def _fatal(self, kind, phase, sample=None, error=None):
        # Called with RLock held. Failure to persist must still stop the worker.
        try:
            self._terminal(kind, phase, sample, error)
        finally:
            os._exit(125)

    def sample(self, phase='checkpoint'):
        need(phase in PHASES, 'known monitor phase')
        with self.lock:
            need(not self.finished, 'monitor already terminal')
            try:
                value = self.observe()
                need(type(value) is int and value >= 0, 'valid RSS observation')
            except BaseException as exc:
                self._fatal('observer_exception', phase, error=type(exc).__name__[:128])
            self.samples += 1
            self.maximum = value if self.maximum is None else max(self.maximum, value)
            if value > self.limit:
                self._fatal('rss_limit', phase, sample=value)
            return value

    def _watch(self):
        try:
            while not self.stop.wait(INTERVAL):
                self.sample('background')
        except BaseException as exc:
            with self.lock:
                self._fatal('monitor_exception', 'background', error=type(exc).__name__[:128])

    def __enter__(self):
        # Reserve terminal pathname before the first observation. Empty is a
        # meaningful incomplete record, never a closed/success marker.
        self.fd = _exclusive(self.outcome_path)
        fd = _exclusive(self.start_path)
        try:
            value = self._base()
            value.update(kind='started', observed_monotonic=time.monotonic(),
                         accounting=self.snapshot(), accounting_complete=False)
            _persist(fd, value)
        finally:
            os.close(fd)
        self.sample('initial')
        try:
            self.thread.start()
        except BaseException as exc:
            with self.lock:
                self._fatal('monitor_exception', 'thread_start', error=type(exc).__name__[:128])
        return self

    def __exit__(self, *unused):
        self.stop.set()
        self.thread.join(timeout=.5)
        # A stuck observer can hold the sampling lock. Do not wait on it past
        # the bounded join; preserve the empty outcome as explicitly unknown.
        if self.thread.is_alive():
            if not self.lock.acquire(timeout=.05):
                os._exit(125)
            self._fatal('monitor_join_timeout', 'join')
        with self.lock:
            self.sample('final')
            self._terminal('closed', 'final', sample=self.maximum)
            os.close(self.fd)
            self.fd = None

    def receipt(self):
        need(self.finished and self.outcome['kind'] == 'closed' and not self.thread.is_alive(),
             'closed successful diagnostic monitor')
        return dict(observed_peak_rss_bytes=self.maximum, samples=self.samples,
                    threshold_bytes=self.limit, sampling_interval_seconds=INTERVAL,
                    hard_os_memory_limit=False,
                    meaning='sampled process high-water RSS; not an OS memory sandbox',
                    diagnostic_outcome=self.outcome)

def closure_ready(process):
    c = process.get('closure', {})
    pid = process.get('pid')
    return (type(pid) is int and pid > 1 and process.get('safely_owned_group') is True and
            process.get('closed_callback_completed') is True and c.get('reaped') is True and
            c.get('process_group_absent') is True and c.get('group_id') == pid and
            set(process.get('streams', {})) == {'stdout', 'stderr'} and
            all(x.get('complete') is True for x in process['streams'].values()))

def validate(value, kind, stage, pid, limit, source_cap, work_cap):
    need(type(value) is dict and value.get('schema') == 'voltron-durable-monitor-v1' and
         value.get('stage') == stage and value.get('pid') == value.get('group_id') == pid and
         value.get('threshold_bytes') == limit and value.get('hard_os_memory_limit') is False and
         value.get('os_OOM_claim') is False and value.get('accounting_complete') is False and
         value.get('sampling_interval_seconds') == INTERVAL, 'exact monitor identity/limits')
    a = value.get('accounting')
    need(type(a) is dict and set(a) == {'sequence', 'source_recorded_bytes', 'admitted_byte_work',
         'pending_source_read_requested_bytes', 'phase'}, 'exact checkpoint fields')
    need(all(type(a[k]) is int and a[k] >= 0 for k in a if k != 'phase') and
         a['source_recorded_bytes'] <= source_cap and
         a['source_recorded_bytes'] + a['pending_source_read_requested_bytes'] <= source_cap and
         a['source_recorded_bytes'] + a['admitted_byte_work'] <= work_cap and
         a['pending_source_read_requested_bytes'] <= source_cap and
         type(a['phase']) is str and len(a['phase']) <= 96, 'bounded incomplete accounting')
    need(type(value.get('observed_monotonic')) in (int, float) and
         0 <= value['observed_monotonic'] < float('inf'), 'finite observation time')
    if kind == 'start':
        need(value.get('kind') == 'started', 'start record')
        return
    need(value.get('kind') in KINDS and value.get('observation_phase') in PHASES and
         type(value.get('samples')) is int and value['samples'] >= 0, 'terminal kind and samples')
    peak, sample = value.get('observed_peak_rss_bytes'), value.get('sample_rss_bytes')
    need(peak is None or type(peak) is int and peak >= 0, 'known peak or unknown')
    need((peak is None) == (value['samples'] == 0), 'observed peak provenance')
    if value['kind'] == 'rss_limit':
        need(type(sample) is int and sample > limit and peak >= sample and
             value.get('error_type') is None, 'measured threshold event')
    elif value['kind'] == 'closed':
        need(value['observation_phase'] == 'final' and type(peak) is int and peak <= limit and
             sample == peak and value.get('error_type') is None, 'closed within threshold')
    elif value['kind'] in ('observer_exception', 'monitor_exception'):
        need(sample is None and type(value.get('error_type')) is str and
             1 <= len(value['error_type']) <= 128, 'explicit observer/monitor exception')
    else:
        need(sample is None and value.get('error_type') is None, 'join timeout')

def interpret(start, terminal, stage, pid, limit, source_cap, work_cap, exit_code):
    validate(start, 'start', stage, pid, limit, source_cap, work_cap)
    validate(terminal, 'terminal', stage, pid, limit, source_cap, work_cap)
    need(terminal['observed_monotonic'] >= start['observed_monotonic'] and
         terminal['accounting']['sequence'] >= start['accounting']['sequence'] and
         terminal['accounting']['source_recorded_bytes'] >= start['accounting']['source_recorded_bytes'] and
         terminal['accounting']['admitted_byte_work'] >= start['accounting']['admitted_byte_work'],
         'monotone start/terminal accounting')
    need(terminal['kind'] == 'closed' or exit_code == 125, 'fatal event/exit agreement')
    return dict(classification=terminal['kind'], observation_phase=terminal['observation_phase'],
                observed_peak_rss_bytes=terminal['observed_peak_rss_bytes'],
                sample_rss_bytes=terminal['sample_rss_bytes'], error_type=terminal['error_type'],
                last_committed_accounting=terminal['accounting'], worker_ledger_complete=False,
                os_OOM_claim=False, limitation='Record identifies this monitor decision only; '
                'closed monitor is not successful intake. External kills/fuse wins/partial writes remain unknown.')

