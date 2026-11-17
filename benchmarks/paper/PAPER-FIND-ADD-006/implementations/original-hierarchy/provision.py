#!/usr/bin/env python3
"""Provision the fixed owner-local dependencies of the original full25 endpoint.

No acquisition, container, subprocess, model, scientific decoding or execution.
Failed installations preserve exclusive partial files and an owner-only receipt.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
TASK = 'PAPER-FIND-ADD-006'
BASE = 'benchmarks/paper/PAPER-FIND-ADD-006/implementations/hierarchy-programme/hierarchy-bounded-task-v1'
COMPONENT = 'benchmarks/paper/PAPER-FIND-ADD-006/implementations/original-hierarchy'
CURRENT = 'benchmarks/integrity/current-closures/hierarchy25a-original'
EXTERNAL_SHA = 'db345052413236d4275dee349e689bba15879eb157fc7773d0fd51edcc63983e'
FREEZE_SHA = '40d4b1bcf8b62cfdeef1b4ff1d519445b534c87f4a101b548500a116aec781fc'
PUBLIC_READ = {'paper_text', 'paper_pdf', 'released_archive', 'private_linkages', 'private_report'}
PRIVATE_REFERENCE = {'private_linkages', 'private_report'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pairs(rows):
    out = {}
    for key, value in rows:
        need(key not in out, 'Duplicate JSON key')
        out[key] = value
    return out


def parse(raw):
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'Nonfinite JSON'))


def canonical(path):
    path = Path(path).absolute()
    need('..' not in path.parts and path == path.resolve()
         and all(not p.is_symlink() for p in (path, *path.parents)), 'Unlinked canonical path')
    return path


def member(root, relative):
    need(type(relative) is str and relative and Path(relative).as_posix() == relative
         and not Path(relative).is_absolute() and '..' not in Path(relative).parts
         and not any(c in relative for c in '\\\r\n\0'), 'Canonical relative member')
    return canonical(root / relative)


def opened(path, expected):
    path = canonical(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    info = os.fstat(fd)
    try:
        need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
             and info.st_size == expected['bytes'], 'Exact ordinary single-link extent')
    except BaseException:
        os.close(fd)
        raise
    return fd, info


def stream(path, expected, destination=None, mode=0o400):
    source, before = opened(path, expected)
    output = None
    h = hashlib.sha256()
    count = 0
    try:
        if destination is not None:
            output = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        while count < expected['bytes']:
            block = os.read(source, min(1048576, expected['bytes'] - count))
            need(bool(block), 'Complete input')
            h.update(block)
            count += len(block)
            if output is not None:
                view = memoryview(block)
                while view:
                    n = os.write(output, view)
                    need(n > 0, 'Complete exclusive output')
                    view = view[n:]
        need(not os.read(source, 1), 'No input growth')
        after = os.fstat(source)
        need(all(getattr(before, k) == getattr(after, k) for k in
                 ('st_dev', 'st_ino', 'st_size', 'st_nlink', 'st_mode', 'st_mtime_ns', 'st_ctime_ns')),
             'Input remained stable')
        need(h.hexdigest() == expected['sha256'], 'Exact accepted input hash')
        if output is not None:
            os.fsync(output)
            os.fchmod(output, mode)
        return {'bytes': count, 'sha256': h.hexdigest()}
    finally:
        os.close(source)
        if output is not None:
            os.close(output)


def metadata(path, sha, cap=32768):
    p = canonical(path)
    need(0 < p.stat().st_size <= cap, 'Bounded metadata')
    b = p.read_bytes()
    need(hashlib.sha256(b).hexdigest() == sha, 'Exact metadata identity')
    return parse(b)


def contract(root):
    root = canonical(root)
    external = metadata(root / COMPONENT / 'EXTERNAL_INPUTS.json', EXTERNAL_SHA)
    freeze = metadata(root / BASE / 'runtime-v1/FREEZE.json', FREEZE_SHA)
    need(external['candidate_id'] == TASK and len(external['files']) == 11
         and freeze['candidate_id'] == TASK and len(freeze['files']) == 44, 'Fixed complete endpoint')
    by_path = {v['destination']: v for v in external['files'].values()}
    need(len(by_path) == 11, 'Unique external destinations')
    public = {}
    deferred = {}
    for relative, pin in freeze['files'].items():
        if relative in by_path:
            row = by_path[relative]
            need({k: row[k] for k in ('bytes', 'sha256')} == pin, 'External ancestry join')
            deferred[relative] = pin
        else:
            public[relative] = pin
    need(len(public) == 40 and len(deferred) == 4, 'Full44 source check split40 public plus4 owner-local')
    current_path = member(root, CURRENT + '/FREEZE.json')
    need(0 < current_path.stat().st_size <= 65536, 'Bounded current source closure')
    current_raw = current_path.read_bytes()
    current = parse(current_raw)
    need(current.get('schema') == 'hierarchy25a_current_runtime_closure_v1'
         and current.get('candidate_id') == TASK
         and current.get('ancestry_freeze_sha256') == FREEZE_SHA
         and current.get('ancestry_files') == freeze['files']
         and current.get('deferred_files') == deferred
         and current.get('new_native_qualification') is False
         and current.get('runtime_execution_ready') is False,
         'Current source identity retains original ancestry and execution hold')
    locator_path = CURRENT + '/LOCATORS.json'
    locators = metadata(member(root, locator_path), current['files'][locator_path]['sha256'])
    reserved = {external['files']['owner_engine']['destination']:
                'benchmarks/shared/program-execution/dmfc-transport-v2/program-runner-v2/engine.py'}
    need(set(locators) == {'schema', 'candidate_id', 'paths'}
         and locators['schema'] == 'hierarchy25a_exact_current_locators_v1'
         and locators['candidate_id'] == TASK and set(locators['paths']) == set(public) | set(reserved)
         and current.get('deferred_locators') == reserved
         and all(locators['paths'][name] == target for name, target in reserved.items()),
         'Forty public ancestry locators and the exact reserved external engine destination')
    mapped = {}
    for relative in public:
        target = locators['paths'][relative]
        member(root, target)
        need(target not in mapped and target not in locators['paths'], 'Unique one-step current locator')
        mapped[target] = current['files'][target]
    deferred_current = {reserved.get(relative, relative): pin for relative, pin in deferred.items()}
    need(all(current['files'][relative] == pin for relative, pin in deferred_current.items()),
         'Deferred current destinations retain exact ancestry bytes')
    auxiliary = {CURRENT + '/' + name for name in ('LOCATORS.json', 'SOURCE_BINDINGS.json', 'IMPORTS.json')}
    need(set(current['files']) == set(mapped) | set(deferred_current) | auxiliary,
         'Same forty public and four deferred ancestry slots plus three current binding manifests')
    for relative in auxiliary:
        stream(member(root, relative), current['files'][relative])
    operative = {role: dict(row, destination=reserved.get(row['destination'], row['destination']))
                 for role, row in external['files'].items()}
    return operative, mapped


def check_public(root, public):
    for relative, pin in public.items():
        stream(member(root, relative), pin)


def parents(root, target):
    current = root
    for part in target.relative_to(root).parts[:-1]:
        current = current / part
        if not current.exists():
            current.mkdir(mode=0o700)
        need(current.is_dir() and not current.is_symlink(), 'Ordinary destination parents')


def private_parent(target, allow_missing=False):
    parent = canonical(target.parent)
    if allow_missing and not parent.exists():
        return
    info = parent.stat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid()
         and stat.S_IMODE(info.st_mode) == 0o700,
         'Private reference parent must be owned by the operator and mode0700')


def install(root, inputs, receipt):
    root = canonical(root)
    receipt = canonical(receipt)
    need(not receipt.is_relative_to(root), 'Receipt stays outside the public checkout')
    rows, public = contract(root)
    need(type(inputs) is dict and set(inputs) == set(rows)
         and all(type(v) is str and Path(v).is_absolute() for v in inputs.values()),
         'All eleven absolute owner-local input paths required')
    check_public(root, public)
    sources = {role: canonical(path) for role, path in inputs.items()}
    targets = {role: member(root, row['destination']) for role, row in rows.items()}
    for role, path in targets.items():
        need(not path.exists(), 'Never replace an existing dependency or failed partial')
        if role in PRIVATE_REFERENCE:
            private_parent(path, allow_missing=True)
        fd, _ = opened(sources[role], rows[role])
        os.close(fd)
    # Opening this receipt before the first copy gives every partial installation
    # an exact terminal record; no rollback or multi-file atomicity is claimed.
    fd = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    record = {'schema': 'hierarchy25a_provision_outcome_v1', 'candidate_id': TASK,
              'status': 'started', 'completed': [], 'attempted': [], 'native_execution': False}
    def save():
        body = (json.dumps(record, indent=2, sort_keys=True) + '\n').encode()
        os.lseek(fd, 0, os.SEEK_SET)
        os.ftruncate(fd, 0)
        view = memoryview(body)
        while view:
            n = os.write(fd, view)
            need(n > 0, 'Complete receipt')
            view = view[n:]
        os.fsync(fd)
    try:
        save()
        for role in sorted(rows):
            record['attempted'].append(role)
            save()
            parents(root, targets[role])
            if role in PRIVATE_REFERENCE:
                private_parent(targets[role])
            stream(sources[role], rows[role], targets[role], 0o444 if role in PUBLIC_READ else 0o400)
            if role in PRIVATE_REFERENCE:
                private_parent(targets[role])
            record['completed'].append(role)
            save()
        record['status'] = 'complete_exact_dependencies_installed'
    except BaseException as error:
        record['status'] = 'failed_partials_preserved'
        record['error_type'] = type(error).__name__
        raise
    finally:
        try:
            save()
        finally:
            os.close(fd)
    return record


def check(root, source_only=False):
    rows, public = contract(root)
    check_public(root, public)
    if not source_only:
        for role, row in rows.items():
            if role in PRIVATE_REFERENCE:
                private_parent(member(root, row['destination']))
            stream(member(root, row['destination']), row)
    return {'candidate_id': TASK, 'current_public_members_checked': 40,
            'ancestry_manifest_members_authenticated': 44,
            'current_binding_manifests_checked': 3,
            'public_members_identity': 'current_source_successor',
            'ancestry_freeze_sha256': FREEZE_SHA,
            'current_freeze_sha256': hashlib.sha256(member(root, CURRENT + '/FREEZE.json').read_bytes()).hexdigest(),
            'runtime_execution_ready': False, 'new_native_qualification': False,
            'external_files_checked': 0 if source_only else 11,
            'native_execution': False, 'source_only': source_only}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=('check-source', 'check', 'install'))
    p.add_argument('--checkout', type=Path, default=ROOT)
    p.add_argument('--inputs', type=Path)
    p.add_argument('--receipt', type=Path)
    a = p.parse_args()
    if a.mode == 'install':
        need(a.inputs is not None and a.receipt is not None, 'Install needs paths JSON and outside receipt')
        need(0 < a.inputs.stat().st_size <= 16384, 'Bounded local input-path mapping')
        result = install(a.checkout, parse(a.inputs.read_bytes()), a.receipt)
    else:
        need(a.inputs is None and a.receipt is None, 'Check accepts no write operands')
        result = check(a.checkout, a.mode == 'check-source')
    print(json.dumps({k: v for k, v in result.items() if k not in ('attempted', 'completed')}, sort_keys=True))


if __name__ == '__main__':
    main()
