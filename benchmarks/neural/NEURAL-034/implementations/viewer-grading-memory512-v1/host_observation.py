"""One bounded host metadata observation through a caller-owned capture API.

No subprocess, signal handler, watchdog or admission policy is implemented here.
The injected call must bound/reap its own command and honor the supplied deadline
and combined-stream cap. Values are observations, never a stability/health proof.
"""
from datetime import datetime, timezone
import math
import re
import time

CAP = 16384
COMMANDS = (
    ('vm_stat', ('/usr/bin/vm_stat',)),
    ('pressure_level', ('/usr/sbin/sysctl', 'kern.memorystatus_vm_pressure_level')),
)


def need(ok, message):
    if not ok:
        raise ValueError(message)


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def parse_vm_stat(stdout):
    need(type(stdout) is str and len(stdout.encode('utf-8')) <= CAP, 'Bounded vm_stat text')
    lines = stdout.splitlines()
    need(bool(lines), 'Missing vm_stat header')
    header = re.fullmatch(r'Mach Virtual Memory Statistics: \(page size of ([0-9]+) bytes\)', lines[0].strip())
    need(header is not None, 'Explicit vm_stat page size required')
    page_size = int(header.group(1))
    need(0 < page_size <= 1048576 and page_size & (page_size - 1) == 0, 'Bounded power-of-two page size')
    pages = {}
    for line in lines[1:]:
        if not line.strip():
            continue
        match = re.fullmatch(r'([^:]+):\s*([0-9]+)\.?', line.strip())
        need(match is not None and match.group(1) not in pages, 'Unique integer vm_stat fields')
        count = int(match.group(2))
        need(count <= 2**63 - 1, 'Bounded page/event count')
        pages[match.group(1)] = count
    estimates = {}
    for name, keys in (
        ('free_plus_file_backed', ('Pages free', 'File-backed pages')),
        ('free_plus_inactive', ('Pages free', 'Pages inactive')),
        ('free_plus_inactive_plus_speculative', ('Pages free', 'Pages inactive', 'Pages speculative')),
    ):
        missing = [key for key in keys if key not in pages]
        estimates[name] = {'status': 'unknown' if missing else 'observed',
            'bytes': None if missing else sum(pages[key] for key in keys) * page_size,
            'components': list(keys), 'missing_fields': missing}
    return {'page_size_bytes': page_size, 'raw_counts': pages, 'estimates': estimates,
            'scope': 'Named arithmetic heuristics; neither an allocation guarantee nor a health gate'}


def parse_pressure(stdout):
    need(type(stdout) is str and len(stdout.encode('utf-8')) <= CAP, 'Bounded sysctl text')
    match = re.fullmatch(r'kern\.memorystatus_vm_pressure_level:\s*([0-9]+)\s*', stdout)
    need(match is not None and int(match.group(1)) <= 2**31 - 1, 'Named integer pressure level required')
    return {'kernel_pressure_level': int(match.group(1)), 'interpretation': 'raw numeric observation only'}


def observe(call, deadline, *, clock=time.monotonic, utc=utc_now):
    """call(argv, deadline, cap=16384) -> {returncode:int, stdout:str, stderr:str}.

    Each attempted command gets at most one second and the remaining external
    deadline. The capture implementation, not this pure glue, enforces that bound.
    No second observation or automatic admission decision is made.
    """
    need(type(deadline) in (int, float) and math.isfinite(deadline), 'Finite external monotonic deadline')
    report = {'schema': 'neural034-host-memory-observation/v1', 'started_utc': utc(),
        'started_monotonic': clock(), 'external_deadline': deadline, 'observations': {},
        'single_observation': True, 'admission_decision': None,
        'swap_growth_measured': False, 'stability_established': False,
        'scope': 'Bounded OS metadata only; no pressure induction, repeated sampling or runtime qualification'}
    for name, argv in COMMANDS:
        now = clock()
        row = {'argv': list(argv), 'started_utc': utc(), 'started_monotonic': now,
            'deadline': min(deadline, now + 1), 'combined_stream_cap_bytes': CAP,
            'status': 'unknown', 'returncode': None, 'stdout': None, 'stderr': None, 'parsed': None}
        report['observations'][name] = row
        try:
            need(now < deadline, 'External deadline exhausted before command')
            result = call(list(argv), row['deadline'], cap=CAP)
            need(type(result) is dict and type(result.get('returncode')) is int and
                 type(result.get('stdout')) is str and type(result.get('stderr')) is str, 'Typed capture result')
            stdout, stderr = result['stdout'], result['stderr']
            row['returncode'] = result['returncode']
            need(len(stdout.encode('utf-8')) + len(stderr.encode('utf-8')) <= CAP,
                 'Capture violated combined stream cap; oversized streams not retained')
            row.update(stdout=stdout, stderr=stderr)
            need(result['returncode'] == 0 and stderr == '', 'Command failed or produced stderr')
            need(clock() <= row['deadline'], 'Capture returned after its command deadline')
            row['parsed'] = parse_vm_stat(stdout) if name == 'vm_stat' else parse_pressure(stdout)
            row['status'] = 'observed'
        except Exception as error:
            row['reason'] = type(error).__name__ + ': ' + str(error)[:240]
        finally:
            row.update(finished_utc=utc(), finished_monotonic=clock())
    report.update(finished_utc=utc(), finished_monotonic=clock())
    return report
