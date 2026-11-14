"""Finite public N090 source preparation and exact engineering-result admission.

This file never imports a task module or dispatches the engineering child.
The workflow separately invokes the unchanged captured control_owner.py.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time

SELECTION_BYTES = 9710
SELECTION_SHA256 = 'aec8a46659093590cdbee6a3f5d4322555eff6b52b105b85ab7952139aeb34fe'
ROOT = Path(__file__).absolute().parent
USED = 0
END = time.monotonic() + 12.0

def need(ok, message):
    if not ok:
        raise ValueError(message)

def tick():
    if time.monotonic() >= END:
        raise TimeoutError('original public source/admission endpoint')

def charge(n):
    global USED
    need(type(n) is int and n >= 0 and USED + n <= 4 * 1048576,
         'fixed4MiB wrapper logical allowance')
    USED += n
    tick()

def ordinary_parents(path):
    for p in (path, *path.parents):
        s = p.lstat()
        need(stat.S_ISDIR(s.st_mode) and not p.is_symlink(),
             'ordinary absolute directory ancestry')

def stamp(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size,
            s.st_mtime_ns, s.st_ctime_ns)

def close_owned(fd, first):
    try:
        os.close(fd)
    except BaseException as error:
        if first is None:
            return error
        first.add_note('Secondary descriptor-close failure: ' + repr(error))
        prior = getattr(first, 'secondary_close_errors', ())
        first.secondary_close_errors = prior + (error,)
    return first

def captured(path, limit, pin=None):
    tick()
    ordinary_parents(path.parent)
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
         and 0 <= before.st_size <= limit, 'bounded ordinary single-link member')
    n = before.st_size
    charge(n + 1)
    fd = None
    first = None
    raw = bytearray()
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        need(stamp(before) == stamp(os.fstat(fd)), 'same opened source identity')
        while len(raw) <= n:
            tick()
            part = os.read(fd, min(65536, n + 1 - len(raw)))
            if not part:
                break
            raw.extend(part)
        need(stamp(before) == stamp(os.fstat(fd)) == stamp(path.lstat()),
             'stable complete selected member')
        need(len(raw) == n, 'complete selected extent')
        if pin is not None:
            need(n == pin['bytes'] and hashlib.sha256(raw).hexdigest() == pin['sha256'],
                 'exact selected member digest')
    except BaseException as error:
        first = error
    finally:
        if fd is not None:
            first = close_owned(fd, first)
    if first is not None:
        first.consumed_prefix = bytes(raw)
        raise first
    tick()
    return bytes(raw)

def put(path, body):
    charge(len(body))
    fd = None
    first = None
    done = 0
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        while done < len(body):
            tick()
            n = os.write(fd, body[done:])
            need(type(n) is int and n > 0, 'complete create-only source write')
            done += n
        os.fsync(fd)
    except BaseException as error:
        first = error
    finally:
        if fd is not None:
            first = close_owned(fd, first)
    if first is not None:
        first.intended_body = body
        first.published_prefix_bytes = done
        raise first
    tick()

def selection():
    raw = captured(ROOT / 'CI_SOURCE_SELECTION.json', 32768,
                   {'bytes': SELECTION_BYTES, 'sha256': SELECTION_SHA256})
    value = json.loads(raw)
    need(value['schema'] == 'n090_public_exact_engineering_v1'
         and value['scientific_execution'] is False, 'exact public source selection')
    need(len(value['controller']) == 44 and len(value['harness']) == 7,
         'complete44controller/sevenharness roster')
    return value

def roots():
    task = ROOT.parent
    source = task / 'native-controller-v6'
    supplied = Path(os.environ['RUNNER_TEMP'])
    need(supplied.is_absolute(), 'absolute RUNNER_TEMP required')
    ordinary_parents(supplied)
    temporary = supplied.resolve(strict=True)
    stage = temporary / 'neural090-controls-v6'
    ordinary_parents(ROOT)
    ordinary_parents(source)
    need(not stage.is_relative_to(task) and not task.is_relative_to(stage),
         'control output outside public source custody')
    need(len(str(stage).encode()) <= 384, 'finite control-root path extent')
    return source, stage

def exact_tree(root, rows):
    expected = {r['path'] for r in rows}
    need(len(expected) == len(rows), 'unique exact source members')
    directories = {str(p) for name in expected for p in Path(name).parents if str(p) != '.'}
    visited = set()
    pending = [root]
    count = 0
    while pending:
        folder = pending.pop()
        iterator = None
        first = None
        try:
            iterator = os.scandir(folder)
            for entry in iterator:
                tick()
                count += 1
                need(count <= 128, 'finite source namespace bound')
                p = Path(entry.path)
                relative = str(p.relative_to(root))
                s = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(s.st_mode):
                    need(relative in directories, 'exact source directory')
                    pending.append(p)
                else:
                    need(stat.S_ISREG(s.st_mode) and relative in expected,
                         'no extra or nonordinary controller member')
                    visited.add(relative)
        except BaseException as error:
            first = error
        finally:
            if iterator is not None:
                try:
                    iterator.close()
                except BaseException as error:
                    if first is None:
                        first = error
                    else:
                        first.add_note('Secondary inventory close: ' + repr(error))
                        first.inventory_close_error = error
        if first is not None:
            raise first
    need(visited == expected, 'complete selected controller namespace')

def prepare(value, source, stage):
    exact_tree(source, value['controller'])
    for row in value['controller']:
        captured(source / row['path'], 1048576, row)
    bodies = [(row, captured(ROOT / row['path'], 1048576, row))
              for row in value['harness']]
    # No source byte has been executed. Fixed seven-file staging is create-only.
    need(not stage.exists() and not stage.is_symlink(), 'fresh control stage required')
    stage.mkdir(mode=0o700)
    for row, raw in bodies:
        put(stage / row['path'], raw)
        need(captured(stage / row['path'], 1048576, row) == raw,
             'copied exact harness source')
    return {'status': 'PASS', 'controller_sources': 44, 'harness_sources': 7,
            'control_stage': str(stage), 'task_code_executed': False}

def results(value, source, stage):
    ordinary_parents(stage)
    output = stage / 'actual-v1'
    ordinary_parents(output)
    owner = json.loads(captured(output / 'ORIGINAL_OWNER.json', 262144))
    child_raw = captured(output / 'CHILD_RESULT.json', 131072)
    child = json.loads(child_raw)
    need(owner['schema'] == 'n090_original_engineering_owner_v1'
         and owner['status'] == 'PASS' and owner['first'] is None
         and owner['secondary'] == [] and owner['wait_returns'] == [0]
         and owner['original_reaped'] is True and owner['wait_ownership_lost'] is False
         and owner['stream_eof'] == ['stderr', 'stdout'] and owner['kill_sent'] is False
         and owner['kill_actions_retired'] is True
         and owner['native_scientific_provider_runs'] == 0
         and owner['automatic_retry'] is False, 'complete natural original engineering owner')
    waits = owner['raw_wait_observations']
    need(type(owner['child_pid']) is int and owner['child_pid'] > 0
         and waits == [{'pid': owner['child_pid'], 'status': 0}],
         'one exact original natural-zero wait')
    need(owner['group_absence_measured'] is False, 'no invented process-group qualification')
    expected_argv = [sys.executable, '-I', '-S', '-B', '-c']
    argv = owner['argv']
    need(argv[:5] == expected_argv and len(argv) == 23
         and argv[6] == str(stage / 'control_child.py')
         and argv[7:9] == [str(value['harness'][1]['bytes']), value['harness'][1]['sha256']]
         and argv[9:17] == ['--manifest', str(stage / 'SOURCE_SELECTION.json'),
                           '--manifest-bytes', str(value['original_selection']['bytes']),
                           '--manifest-sha256', value['original_selection']['sha256'],
                           '--source-root', str(source)]
         and argv[17:19] == ['--output', str(output)]
         and argv[19] == '--work-end' and argv[21] == '--publication-end',
         'actual selected child caller and paths')
    need(child == owner['child_result'], 'same captured child and owner result')
    need(child['schema'] == 'n090_complete24_engineering_result_v1'
         and child['status'] == 'PASS' and child['case'] is None
         and child['attempted'] == 24 and child['assertions'] == 333
         and child['first'] is None and child['secondary'] == []
         and child['source_manifest_sha256'] == value['controller_manifest']['sha256']
         and child['full_scope_invocations'] == 76800
         and child['native_scientific_provider_effects'] == 0
         and child['physical_IO_or_RSS_measured'] is False,
         'exact complete engineering-only child')
    rows = child['cases']
    need([r['case'] for r in rows] == value['case_roster']
         and [r['assertions'] for r in rows] == value['assertions_per_case']
         and all(r['status'] == 'PASS' for r in rows), 'all24 ordered groups/333 assertions')
    for row in rows:
        need(type(row['managed_transfer']) is int and 0 <= row['managed_transfer']
             <= value['case_transfer_bounds'][row['case']], 'original case transfer cap')
    need(child['fixed_case_transfer_reserved'] == 487325696
         and owner['whole_attempt_charge_bytes'] == 536870912
         and 0 <= owner['owner_managed_transfer'] <= 8 * 1048576,
         'original prospective charge boundaries')
    need(0 <= child['seconds'] < 105 and 0 <= owner['seconds_before_final'] < 120,
         'original child/owner reported intervals')
    for name in ('stdout', 'stderr'):
        raw = captured(output / (name + '.txt'), 65536)
        pin = owner['streams'][name]
        need(pin['complete'] is True and pin['bytes'] == len(raw)
             and pin['sha256'] == hashlib.sha256(raw).hexdigest(),
             'actual stream body matches original owner')
        if name == 'stderr':
            need(raw == b'', 'no hidden engineering stderr on positive run')
        else:
            terminal = json.loads(raw)
            need(terminal == {'status': 'PASS', 'case': None, 'passed': 24,
                              'assertions': 333, 'durable_child_record': True},
                 'actual complete child terminal')
    return {'status': 'PASS', 'engineering_groups': 24, 'assertions': 333,
            'full_scope_invocations': 76800, 'scientific_execution': False,
            'native_platform_qualification': False, 'open_qualification_gates': 22,
            'requires_prior_workflow_owner_step_natural_zero': True}

def main():
    need(sys.version_info[:2] == (3, 11) and sys.platform.startswith('linux'),
         'selected Linux CPython3.11 CI environment')
    need(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
         and not sys.flags.optimize, 'actual -I -S -B without optimization')
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('mode', choices=('prepare', 'results'))
    args = parser.parse_args()
    value = selection()
    source, stage = roots()
    report = prepare(value, source, stage) if args.mode == 'prepare' else results(value, source, stage)
    report['wrapper_managed_transfer'] = USED
    tick()
    body = json.dumps(report, sort_keys=True, allow_nan=False) + '\n'
    need(sys.stdout.write(body) == len(body), 'complete terminal write')
    sys.stdout.flush()
    tick()

if __name__ == '__main__':
    main()
