"""Explicit NEURAL-095 operator selection; never an execution grant.

Authenticate the selected task source, then replace this process with its
existing CLI. Original owner/runtime/collection gates remain authoritative.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = "benchmarks/neural/NEURAL-095/current-operator-routes.v1.json"
CONFIG_PIN = {'bytes': 5893, 'sha256': 'b487d5c3c4cc04334cd55ddda054b44fb04e21a1c438827e1e6ce170908a813c'}


def need(ok, why):
    if not ok:
        raise ValueError(why)


def captured(relative, expected):
    rel = Path(relative)
    need(type(relative) is str and not rel.is_absolute() and rel.as_posix() == relative and
         '..' not in rel.parts and relative.startswith('benchmarks/neural/NEURAL-095/'), 'Task-local source required')
    path = ROOT / rel
    need(all(not p.is_symlink() for p in (path, *path.parents)), 'Unlinked source required')
    need(type(expected) is dict and set(expected) == {'bytes','sha256'} and
         type(expected['bytes']) is int and 0 < expected['bytes'] <= 262144, 'Bounded source identity')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == expected['bytes'], 'Ordinary source extent')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(expected['bytes'] + 1)
        after = os.fstat(fd)
        need(len(raw) == expected['bytes'] and hashlib.sha256(raw).hexdigest() == expected['sha256'] and
             all(getattr(before,k) == getattr(after,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),
             'Stable selected source')
        current = path.lstat()
        need(stat.S_ISREG(current.st_mode) and current.st_nlink == 1 and
             all(getattr(before,k) == getattr(current,k) for k in
                 ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')) and
             all(not p.is_symlink() for p in (path, *path.parents)), 'Selected source path changed after capture')
        return raw
    finally:
        os.close(fd)


def restricted_session(session, view):
    path = Path(session).absolute() / 'BOUNDARY.json'
    need('..' not in path.parts and all(not p.is_symlink() for p in (path, *path.parents)), 'Ordinary selected session')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= 65536,
             'Bounded session boundary metadata')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(65537)
        after = os.fstat(fd); current = path.lstat()
        fields = ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
        need(len(raw) == before.st_size and all(getattr(before,k) == getattr(after,k) == getattr(current,k) for k in fields)
             and all(not p.is_symlink() for p in (path, *path.parents)), 'Stable ordinary selected session metadata')
    finally:
        os.close(fd)
    def unique(pairs):
        value = {}
        for key, item in pairs:
            need(key not in value, 'Duplicate session boundary key'); value[key] = item
        return value
    boundary = json.loads(raw, object_pairs_hook=unique,
        parse_constant=lambda value: need(False, 'Nonfinite session metadata'))
    need(type(boundary) is dict and boundary.get('schema') == 'neural095-participant-view/v1' and
         boundary.get('mode') == 'restricted_count_viewer/v1' and boundary.get('view') == view and
         boundary.get('sandbox') == 'macos', 'Canonical restricted route requires macOS sessions in both views')
    # This is only condition selection. Original transport replay, source/profile
    # checks, closure and private-grading barriers remain mandatory downstream.


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--condition', required=True, choices=('stateful_case_investigator/v2','restricted_count_viewer/v1'))
    parser.add_argument('--stage', required=True, choices=('configure','admit','view','collect','grade'))
    parser.add_argument('--show-command', action='store_true')
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    routes = json.loads(captured(CONFIG_PATH, CONFIG_PIN))
    need(routes['schema'] == 'neural095-current-operator-routes/v1' and routes['execution_authority'] is False,
         'Current source-only route selection')
    selected = routes['conditions'][args.condition]
    need(args.stage in selected['stages'], 'Stage must belong to selected condition')
    for name, expected in selected['source_closure'].items():
        captured(selected['source_directory'] + name, expected)
    step = selected['stages'][args.stage]
    need(step['entrypoint'].startswith(selected['source_directory']) and
         step['entrypoint'][len(selected['source_directory']):] in selected['source_closure'], 'Pinned selected entrypoint')
    arguments = args.arguments
    need(arguments and arguments[0] == '--', 'Pass original CLI arguments after explicit --')
    need(not any(word.split('=',1)[0] in ('--condition','--stage','--show-command','--') for word in arguments[1:]),
         'Forwarded arguments cannot select another route or launcher operation')
    if args.condition == 'restricted_count_viewer/v1':
        allowed = {
            'view': {'--inputs','--view','--output','--client','--python','--sandbox',
                     '--max-actions','--max-images','--max-output-bytes','--wall-seconds'},
            'collect': {'--inputs','--cue-session','--neural-session','--output'},
            'grade': {'--inputs','--cue-session','--neural-session','--collection','--evaluator-inputs','--output'},
        }[args.stage]
        forwarded = arguments[1:]
        need(len(forwarded) % 2 == 0, 'Viewer arguments require exact option/value pairs')
        options = {}
        for flag, value in zip(forwarded[::2], forwarded[1::2]):
            need(flag in allowed and flag not in options and not value.startswith('--'),
                 'Only unique unabbreviated viewer options; no equals or mode overrides')
            options[flag] = value
        if args.stage == 'view':
            need(options.get('--sandbox') == 'macos',
                 'Current restricted viewer route requires the actual macOS boundary')
        else:
            need('--cue-session' in options and '--neural-session' in options, 'Two explicit sessions required')
            restricted_session(options['--cue-session'], 'cue_only')
            restricted_session(options['--neural-session'], 'neural')
    command = [sys.executable, '-I', '-B', str(ROOT / step['entrypoint']), *step['prefix'], *arguments[1:]]
    if args.show_command:
        print(json.dumps({'condition':args.condition,'stage':args.stage,'argv':command,
                          'execution_authority':False,'runtime_qualified':False}))
        return 0
    os.execv(sys.executable, command)


if __name__ == '__main__':
    raise SystemExit(main())
