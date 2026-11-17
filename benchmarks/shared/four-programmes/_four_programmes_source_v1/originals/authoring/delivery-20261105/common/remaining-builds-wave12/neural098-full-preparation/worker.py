"""Future explicitly selected trusted preparation worker; never a model runner."""
import time
ORIGIN = time.monotonic()
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sys
import types

from custody import Budget, below, need, read_pinned, write_exclusive
from source_plan import encode, digest
from driver import run, limits, json_value
from runtime import qualify

WORK_SECONDS = 21600
CLEANUP_SECONDS = 21720
OUTER_SECONDS = 21840
MAX_READ = 8 * 2**40
MAX_WRITE = 130 * 2**30
RAM_BYTES = 24 * 2**30


def module(raw, name):
    value = types.ModuleType(name)
    exec(compile(raw, '<authenticated ' + name + '>', 'exec'), value.__dict__)
    return value


def alarm(*_): raise TimeoutError('original preparation worker deadline')


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--selection', required=True)
    parser.add_argument('--selection-sha256', required=True)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--origin', required=True, type=float)
    args = parser.parse_args(argv)
    import math
    need(math.isfinite(args.origin) and 0 < args.origin <= ORIGIN
         and ORIGIN - args.origin < 60, 'original enclosing origin and bounded startup')
    origin = args.origin
    need(sys.platform == 'linux', 'prospective qualified Linux preparation profile')
    root_fd = repo_fd = source_fd = parent_fd = work_fd = None
    previous_handler = None; armed = False
    original = None
    try:
        # No borrowed alarm may be erased. Startup is part of ORIGIN.
        need(signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0), 'exclusive worker timer custody')
        previous_handler = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, alarm)
        signal.setitimer(signal.ITIMER_REAL, max(.001, origin + WORK_SECONDS - time.monotonic()))
        armed = True
        for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
            need(os.environ.get(key) == '1', 'selected single-thread native environment')
        resource.setrlimit(resource.RLIMIT_AS, (RAM_BYTES, RAM_BYTES))
        resource.setrlimit(resource.RLIMIT_CPU, (WORK_SECONDS, WORK_SECONDS))
        resource.setrlimit(resource.RLIMIT_FSIZE, (2_000_000_000, 2_000_000_000))
        resource.setrlimit(resource.RLIMIT_NOFILE, (512, 512))
        budget = Budget(deadline=float(origin + WORK_SECONDS), read_cap=MAX_READ, write_cap=MAX_WRITE)
        root_fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
        def absolute(value):
            p = Path(value)
            need(p.is_absolute() and str(p) == value, 'canonical absolute operator path')
            return value[1:]
        # Selection itself is ordinary source metadata, captured before any
        # source asset or native package. Its whole pinned extent is capped.
        selection_name = absolute(args.selection)
        fd = below(root_fd, selection_name, os.O_RDONLY)
        try: n = os.fstat(fd).st_size
        finally: os.close(fd)
        selected_pin = {'path': selection_name, 'bytes': n, 'sha256': args.selection_sha256}
        selected_raw = read_pinned(root_fd, selected_pin, budget, 1_048_576)
        selection = json_value(selected_raw)
        keys = {'schema', 'enabled', 'source_manifest_sha256', 'source_plan', 'runtime_qualification',
                'source_root', 'output_parent', 'output_name', 'caps', 'profile', 'capacity'}
        need(type(selection) is dict and set(selection) == keys and selection['enabled'] is True
             and selection['schema'] == 'neural098-full33-preparation-selection-v1', 'explicit fresh preparation selection')
        limits(selection['caps'])
        repo_fd = below(root_fd, absolute(args.repo), os.O_RDONLY | os.O_DIRECTORY)
        source_dir = Path(__file__).absolute().parent
        manifest_relative = str(source_dir.relative_to(Path(args.repo))) + '/SOURCE_MANIFEST.json'
        fd = below(repo_fd, manifest_relative, os.O_RDONLY)
        try: manifest_n = os.fstat(fd).st_size
        finally: os.close(fd)
        manifest_raw = read_pinned(repo_fd, {'path': manifest_relative, 'bytes': manifest_n,
            'sha256': selection['source_manifest_sha256']}, budget, 65536)
        manifest = json_value(manifest_raw)
        from source_plan import source_manifest
        source_manifest(manifest, str(source_dir.relative_to(Path(args.repo))))
        own = {}
        for pin in manifest['files']:
            own[pin['path']] = read_pinned(repo_fd, pin, budget, 1_000_000)
        lock_path = str(source_dir.relative_to(Path(args.repo))) + '/SOURCE_LOCK.json'
        lock = json_value(own[lock_path]); dependencies = {}
        for role, pin in lock['dependencies'].items():
            dependencies[role] = read_pinned(repo_fd, pin, budget, 1_000_000)
        # A disabled/missing qualification refuses before original source paths
        # and any MNE scientific reader are opened.
        qpin = selection['runtime_qualification']
        qualification = json_value(read_pinned(repo_fd, qpin, budget, 1_048576))
        qualify(qualification, selection=selection, manifest_sha256=digest(manifest_raw), root_fd=root_fd, budget=budget)
        plan_raw = read_pinned(repo_fd, selection['source_plan'], budget, 4_000_000)
        plan = json_value(plan_raw)
        bridge = module(dependencies['bridge'], 'binding_bridge')
        terminal = module(dependencies['terminal'], 'terminal_v2')
        cohort = json_value(dependencies['cohort'])
        need(cohort['participants'] == list(bridge.PEOPLE), 'canonical complete33 cohort identity')
        from source_plan import validate
        validate(plan, bridge.PEOPLE, selection['caps'])
        source_fd = below(root_fd, absolute(selection['source_root']), os.O_RDONLY | os.O_DIRECTORY)
        parent_fd = below(root_fd, absolute(selection['output_parent']), os.O_RDONLY | os.O_DIRECTORY)
        from source_plan import capacity
        protected = capacity(selection['capacity'], parent_fd, initial=True)
        budget.space = (parent_fd, protected)
        name = selection['output_name']
        from custody import relative
        need(len(relative(name)) == 1, 'fresh single output name')
        os.mkdir(name, 0o700, dir_fd=parent_fd)
        work_fd = below(parent_fd, name, os.O_RDONLY | os.O_DIRECTORY)
        os.fsync(parent_fd); budget.check()
        from native_library import Library
        library = Library(budget)
        pin = run(plan=plan, caps=selection['caps'], profile=selection['profile'], source_root_fd=source_fd,
            work=Path(selection['output_parent']) / name, work_fd=work_fd, budget=budget,
            bridge=bridge, terminal=terminal, scientific_raw={k: dependencies[k] for k in ('prepare', 'protocol', 'reference')}, library=library)
        os.fsync(parent_fd); budget.check()
        body = encode({'completion': pin, 'selection_sha256': args.selection_sha256,
                       'original_origin': origin, 'managed_reads': budget.read, 'managed_writes': budget.write,
                       'complete_preparation_provisional': True, 'outer_exit_required': True})
        need(len(body) <= 4096, 'bounded worker terminal receipt')
        sys.stdout.buffer.write(body); sys.stdout.buffer.flush(); budget.check()
    except BaseException as exc:
        original = exc
    errors = []
    for fd in (work_fd, parent_fd, source_fd, repo_fd, root_fd):
        if fd is not None:
            try: os.close(fd)
            except BaseException as exc: errors.append(exc)
    if armed:
        try: signal.setitimer(signal.ITIMER_REAL, 0)
        except BaseException as exc: errors.append(exc)
    if previous_handler is not None:
        try: signal.signal(signal.SIGALRM, previous_handler)
        except BaseException as exc: errors.append(exc)
    if original is not None and not isinstance(original, Exception): raise original
    if errors: raise errors[0] from original
    if original is not None: raise original
    need(time.monotonic() < origin + WORK_SECONDS, 'original worker clock through publication/restoration')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
