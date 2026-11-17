"""Source-only inspection or separately selected full NEURAL098 operation."""
import time
ORIGIN = time.monotonic()
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import types


def need(ok, why):
    if not ok:
        raise ValueError(why)


def bootstrap_capture(path, expected, cap=1_048_576):
    p = Path(path).absolute()
    need(all(not x.is_symlink() for x in (p, *p.parents)), 'ordinary bootstrap ancestry')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and before.st_size == expected['bytes'] <= cap, 'bounded bootstrap object')
        raw = bytearray()
        while len(raw) <= before.st_size:
            piece = os.read(fd, min(65536, before.st_size + 1 - len(raw)))
            if not piece:
                break
            raw.extend(piece)
        after = os.fstat(fd); named = p.lstat()
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink')
        need(len(raw) == before.st_size and all(getattr(before, k) == getattr(after, k) == getattr(named, k) for k in fields)
             and hashlib.sha256(raw).hexdigest() == expected['sha256'], 'exact stable bootstrap source/EOF')
        return bytes(raw)
    finally:
        os.close(fd)


def bootstrap(source_bytes, source_sha):
    base = Path(__file__).absolute().parent
    raw = bootstrap_capture(base / 'SOURCE_MANIFEST.json', {'bytes': source_bytes, 'sha256': source_sha})
    manifest = json.loads(raw)
    need(manifest['schema'] == 'neural098-complete-runtime-source-v1', 'complete runtime source schema')
    rows = manifest['files']
    need(type(rows) is list and 0 < len(rows) <= 32, 'closed bounded runtime source set')
    bodies = {}; read_bytes = len(raw) + 1
    for d in rows:
        relative = d['path']
        need(type(relative) is str and not relative.startswith('/') and '\\' not in relative
             and all(x not in ('', '.', '..') for x in relative.split('/')) and relative not in bodies,
             'unique owned source relative path')
        body = bootstrap_capture(base / relative, d)
        bodies[relative] = body; read_bytes += len(body) + 1
    need('entry.py' in bodies and 'PARENT_BINDINGS.json' in bodies, 'entry and complete dependency metadata present')
    need(read_bytes <= 4_194_304, 'whole bounded bootstrap source envelope')
    name = 'neural098_' + source_sha[:16]
    need(name not in sys.modules, 'fresh source module namespace')
    package = types.ModuleType(name); package.__path__ = []
    package.__package__ = name; sys.modules[name] = package
    expected = ['custody', 'parents', 'selection', 'process', 'views', 'broker', 'independent_reference', 'workflow']
    need([x['module'] for x in manifest['load_order']] == expected, 'closed complete module order')
    for row in manifest['load_order']:
        need(row['path'] in bodies, 'module belongs to exact source capture')
        fullname = name + '.' + row['module']
        module = types.ModuleType(fullname); module.__package__ = name
        module.__file__ = str(base / row['path']); sys.modules[fullname] = module
        setattr(package, row['module'], module)
        exec(compile(bodies[row['path']], module.__file__, 'exec'), module.__dict__)
    return package, json.loads(bodies['PARENT_BINDINGS.json']), read_bytes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--source-bytes', type=int, required=True)
    parser.add_argument('--source-sha256', required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('inspect-source')
    run = sub.add_parser('run')
    for key in ('selection', 'selection-sha256'):
        run.add_argument('--' + key, required=True)
    run.add_argument('--selection-bytes', required=True, type=int)
    worker = sub.add_parser('trusted-worker')
    for key in ('job', 'job-sha256'):
        worker.add_argument('--' + key, required=True)
    worker.add_argument('--job-bytes', required=True, type=int)
    args = parser.parse_args(argv)
    need(sys.flags.isolated and sys.flags.dont_write_bytecode and not sys.flags.optimize,
         'isolated bytecode-free interpreter required')
    root = Path(args.repo)
    need(root.is_absolute() and str(root) == args.repo and not root.is_symlink(), 'explicit ordinary repository root')
    modules, bindings, startup = bootstrap(args.source_bytes, args.source_sha256)
    if args.command == 'inspect-source':
        for d in bindings['source_files']:
            bootstrap_capture(root / d['path'], d)
            startup += d['bytes'] + 1
        result = modules.selection.inspect(bindings, args.source_sha256)
        result['verified_bootstrap_and_parent_source_bytes_plus_EOF'] = startup
    elif args.command == 'run':
        selected_pin = {'path': args.selection, 'bytes': args.selection_bytes, 'sha256': args.selection_sha256}
        raw = bootstrap_capture(args.selection, selected_pin)
        selection = modules.custody.parse(raw); startup += len(raw) + 1
        controller = modules.workflow.Controller(root=root, source_sha=args.source_sha256,
            source_bytes=args.source_bytes, entry=Path(__file__).absolute(), bindings=bindings,
            selection=selection, selection_pin=selected_pin, origin=ORIGIN, startup_read_bytes=startup)
        result = controller.run()
    else:
        job_pin = {'path': args.job, 'bytes': args.job_bytes, 'sha256': args.job_sha256}
        raw = bootstrap_capture(args.job, job_pin); startup += len(raw) + 1
        job = modules.custody.parse(raw)
        raw = bootstrap_capture(job['selection']['path'], job['selection']); startup += len(raw) + 1
        selection = modules.custody.parse(raw)
        result = modules.workflow.trusted_worker(root=root, bindings=bindings, selection=selection,
            source_sha=args.source_sha256, job=job, startup_read_bytes=startup)
    sys.stdout.write(json.dumps(result, sort_keys=True, allow_nan=False) + '\n')
    sys.stdout.flush()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
