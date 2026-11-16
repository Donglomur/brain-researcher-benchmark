"""Authenticate and load the REP012 source package. No candidate or Docker dispatch."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import types
sys.dont_write_bytecode = True
ROOT = Path(__file__).absolute().parent
MANIFEST = 'SOURCE_MANIFEST.json'
MAX_SOURCE = 1048576
MAX_TOTAL = 4194304


def need(ok, message):
    if not ok:
        raise ValueError(message)


def decode(body):
    def unique(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=unique,
                      parse_constant=lambda _: need(False, 'nonfinite JSON'))


def plain(value):
    p = Path(value)
    need(p.is_absolute() and str(p) == str(value) and '..' not in p.parts,
         'canonical absolute source path')
    need(all(not q.is_symlink() for q in (p, *p.parents)), 'unlinked source ancestry')
    return p


def signature(s):
    return tuple(getattr(s, k) for k in
                 ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns'))


def read(path, cap, expected=None):
    p = plain(path)
    before = p.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
         and 0 < before.st_size <= cap, 'ordinary bounded single-link source')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        need(signature(before) == signature(os.fstat(fd)), 'stable source open')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(cap + 1)
        need(signature(before) == signature(os.fstat(fd)) == signature(p.lstat())
             and len(body) == before.st_size, 'stable complete source')
    finally:
        os.close(fd)
    actual = {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}
    need(expected is None or actual == expected, 'exact selected source identity')
    return body


def verify(manifest_sha256, root=None):
    root = plain(ROOT if root is None else root)
    need(type(manifest_sha256) is str and re.fullmatch('[a-f0-9]{64}', manifest_sha256),
         'explicit externally selected release manifest hash')
    body = read(root / MANIFEST, 65536)
    need(hashlib.sha256(body).hexdigest() == manifest_sha256, 'selected release manifest')
    manifest = decode(body)
    need(set(manifest) == {'schema', 'task_id', 'execution_authority', 'files', 'total_bytes'}
         and manifest['schema'] == 'rep012-portable-source-manifest/v1'
         and manifest['task_id'] == 'PAPER-FIND-REP-012'
         and manifest['execution_authority'] is False, 'source-only task manifest')
    rows = manifest['files']
    need(type(rows) is dict and 1 <= len(rows) <= 64 and MANIFEST not in rows,
         'bounded nonrecursive source inventory')
    total = 0
    allowed_dirs = {'.'}
    for name, expected in rows.items():
        p = Path(name)
        need(type(name) is str and not p.is_absolute() and p.as_posix() == name
             and '..' not in p.parts and name != '.', 'canonical source member')
        need(type(expected) is dict and set(expected) == {'bytes', 'sha256'}
             and type(expected['bytes']) is int and 0 < expected['bytes'] <= MAX_SOURCE
             and type(expected['sha256']) is str
             and re.fullmatch('[a-f0-9]{64}', expected['sha256']), 'complete source descriptor')
        total += expected['bytes']
        allowed_dirs.update(q.as_posix() for q in p.parents)
    need(type(manifest['total_bytes']) is int and total == manifest['total_bytes'] <= MAX_TOTAL,
         'whole source byte bound')
    seen = set()
    for current, dirs, files in os.walk(root, followlinks=False):
        p = Path(current)
        need(p.relative_to(root).as_posix() in allowed_dirs, 'no unexpected source directory')
        for name in dirs + files:
            q = p / name
            need(not q.is_symlink(), 'no linked source members')
            s = q.lstat()
            if name in dirs:
                need(stat.S_ISDIR(s.st_mode), 'ordinary source directory')
            else:
                need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'ordinary source member')
                seen.add(q.relative_to(root).as_posix())
    need(seen == set(rows) | {MANIFEST}, 'complete exact source inventory')
    bodies = {name: read(root / name, MAX_SOURCE, expected) for name, expected in rows.items()}
    return root, manifest, bodies


def module(root, bodies, relative, name):
    need(relative in bodies, 'entrypoint inside authenticated graph')
    m = types.ModuleType(name)
    m.__file__ = str(root / relative)
    exec(compile(bodies[relative], m.__file__, 'exec'), m.__dict__)
    return m


def load(manifest_sha256, root=None):
    """Owner API only. Importing sources does not admit or launch an episode."""
    root, manifest, bodies = verify(manifest_sha256, root)
    controller = module(root, bodies, 'controller.py', '_rep012_portable_controller')
    staging = module(root, bodies, 'run_oracle_pair.py', '_rep012_existing_oracle_driver')
    core = module(root, bodies,
                  'authoring/compartment-plasticity-v1/bounded-task-v1/scorer_core.py',
                  '_rep012_unchanged_core')
    scorer = module(root, bodies, 'benchmarks/neuroscience/paper-find-rep-012/score.py',
                    '_rep012_relocated_artifact_scorer')
    return types.SimpleNamespace(root=root, manifest=manifest, controller=controller,
                                 staging=staging, core=core, scorer=scorer,
                                 packet_binding=root / 'PACKET_BINDING.json')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest-sha256', required=True)
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('check')
    validate = sub.add_parser('validate')
    validate.add_argument('--submission', required=True)
    score = sub.add_parser('score')
    for name in ('submission', 'reference', 'output'):
        score.add_argument('--' + name, required=True)
    a = p.parse_args(argv)
    if a.command == 'check':
        root, manifest, bodies = verify(a.manifest_sha256)
        print(json.dumps({'status': 'source_authenticated_only', 'task_id': manifest['task_id'],
                          'files': len(bodies), 'runtime_qualified': False,
                          'input_bodies_read': False, 'execution_authority': False}), flush=True)
        return 0
    api = load(a.manifest_sha256)
    if a.command == 'validate':
        body = api.controller.captured(Path(a.submission).absolute(), 32768)
        api.core.validate_submission(body, input_manifest_sha256=api.scorer.INPUT_SHA)
        print(json.dumps({'status': 'valid_result_artifact', 'private_reference_read': False,
                          'program_execution_or_pair_closure_proved': False}), flush=True)
        return 0
    # This is the existing owner-only artifact operation, not a paired lifecycle.
    # The selected external owner must first close both arms and all driver groups.
    return api.scorer.main(['--submission', a.submission, '--reference', a.reference,
                            '--output', a.output])


if __name__ == '__main__':
    raise SystemExit(main())
