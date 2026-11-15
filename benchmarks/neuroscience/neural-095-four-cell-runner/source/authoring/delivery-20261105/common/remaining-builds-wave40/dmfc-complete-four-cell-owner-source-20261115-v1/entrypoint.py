"""Source-bound DMFC entrypoint shared by outer, controller and actor creators.

Import is inert. Actual execution additionally requires the exact current root
request, runtime/capacity admission and the complete operation owner.
"""
import argparse
import ast
import ctypes
import hashlib
import json
import os
from pathlib import Path
import stat
import socket
import struct
import sys
import time
import types

sys.dont_write_bytecode = True
HERE = Path(__file__).absolute().parent
ROOT = HERE.parents[4]
MARKERS = ('process_intent.json', 'process_ready.json', 'process_owner.json',
           'process_gate.json', 'process_completion.json')
BOOTSTRAP_READ_CHARGE = 6 * 1024**2
FAMILY_BOOTSTRAP_READ_CHARGE = 6 * BOOTSTRAP_READ_CHARGE


def need(ok, message):
    if not ok:
        raise ValueError(message)


def _capture(path, cap=262144):
    path = Path(path).absolute()
    need('..' not in path.parts and all(not x.is_symlink() for x in (path, *path.parents)), 'ordinary bootstrap path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             'bounded bootstrap metadata')
        with os.fdopen(fd, 'rb', closefd=False) as f:
            body = f.read(cap + 1)
        after = os.fstat(fd)
        need(len(body) == before.st_size and all(getattr(before, k) == getattr(after, k) for k in
             ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')), 'stable bootstrap bytes')
    finally:
        os.close(fd)
    return body


def _pinned(root, pin):
    relative = pin['path']
    need(type(relative) is str and not Path(relative).is_absolute() and '..' not in Path(relative).parts,
         'relative bootstrap source')
    body = _capture(root / relative)
    need(len(body) == pin['bytes'] and hashlib.sha256(body).hexdigest() == pin['sha256'], 'exact bootstrap source')
    return body


def _module(name, path, body):
    value = types.ModuleType(name); value.__file__ = str(path)
    sys.modules[name] = value
    try:
        exec(compile(body, str(path), 'exec'), value.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return value


def bootstrap(config_path, config_sha):
    started = time.monotonic()  # Original whole-operation clock precedes source reads.
    raw = _capture(config_path)
    need(hashlib.sha256(raw).hexdigest() == config_sha, 'exact selected configuration')
    header = json.loads(raw)
    need(header['repository_root'] == str(ROOT), 'fixed actual repository')
    frozen_raw = _pinned(ROOT, header['successor_freeze']); header_freeze = json.loads(frozen_raw)
    config_rel = (HERE / 'configuration.py').relative_to(ROOT).as_posix()
    entry_rel = (HERE / 'entrypoint.py').relative_to(ROOT).as_posix()
    need(header_freeze['entrypoint'] == {'path': entry_rel, **header_freeze['files'][entry_rel]},
         'source freeze names this actual entrypoint')
    entry_raw = _pinned(ROOT, header_freeze['entrypoint'])
    config_raw = _pinned(ROOT, {'path': config_rel, **header_freeze['files'][config_rel]})
    cm = _module('_dmfc_bootstrap_configuration', ROOT / config_rel, config_raw)
    config, captured, freeze = cm.load(config_path, config_sha)
    bootstrap_known = len(raw) + len(frozen_raw) + len(entry_raw) + len(config_raw) + config.source_bytes_read
    # Each bundle also covers its bounded actor/controller prelude, inherited
    # helper rereads and the V4 leader's source/journal/controller reads. The
    # latter processes do not themselves install Python read hooks.
    need(bootstrap_known + 2 * 1048576 <= BOOTSTRAP_READ_CHARGE, 'complete bootstrap/leader read reservation')
    config.started_monotonic = started
    # Reserve the outer, controller and all four potential actor bootstraps
    # before dispatch. This retains their charge even if a bootstrap dies early.
    config.bootstrap_read_bytes = FAMILY_BOOTSTRAP_READ_CHARGE
    rb_rel = (HERE / 'runtime_binding.py').relative_to(ROOT).as_posix()
    rb = _module('_dmfc_bootstrap_runtime', ROOT / rb_rel, captured[rb_rel])
    runtime = rb.load_runtime(ROOT, captured, freeze['files'], config.value['runtime_identity'])
    runtime.loader.bind_aliases(freeze['modules'])
    required = ('configuration', 'operation_owner', 'wire', 'actor_contract', 'actor_stream',
                'actor_runtime', 'actor_service', 'live', 'producer', 'actor_backend', 'controller', 'entrypoint')
    need(set(freeze['modules']) == set(required), 'complete explicit DMFC/shared module assembly')
    loaded = {}
    for name in required:
        injected = {'live': loaded['live']} if name == 'actor_backend' else {}
        loaded[name] = runtime.loader.load(freeze['modules'][name], injected=injected)
    stack = types.SimpleNamespace(**loaded)
    stack.operator_config = stack.configuration; stack.source_freeze = freeze
    stack.captured_sources = captured; stack.runtime_binding = rb
    need(stack.actor_contract.PIDS == stack.actor_backend.ACTOR_TASKS == 8 and
         stack.actor_backend.MAX_UNITS == 46, 'fixed actor-accounting and numerical-unit profile')
    need(3 * 1024**3 + 256 * 1024**2 + 40 * 1024**2 + stack.actor_contract.MEMORY <=
         config.value['limits']['max_memory_bytes'], 'simultaneous candidate/holder/volume/actor memory ceilings')
    peer_relative = 'authoring/delivery-20261105/common/remaining-builds-wave40/neural017-interactive-transport-source-20261115-v1/unix_arm.py'
    peer_body = captured[peer_relative]
    need((len(peer_body), hashlib.sha256(peer_body).hexdigest()) ==
         (10409, '696c000800fa86efb900840ec126f3786858a9e8ce6ca44f6da5815c95095d4b'),
         'exact accepted kernel-peer authentication source')
    peer_nodes = [n for n in ast.parse(peer_body).body if isinstance(n, ast.FunctionDef) and n.name == 'peer_uid']
    need(len(peer_nodes) == 1, 'single unchanged peer credential function')
    peer_ns = {'socket': socket, 'struct': struct, 'ctypes': ctypes}
    exec(compile(ast.Module(body=peer_nodes, type_ignores=[]), str(ROOT / peer_relative), 'exec'), peer_ns)
    stack.peer_uid = peer_ns['peer_uid']
    # Actor/controller processes join only an already admitted operation root.
    # Initial outer admission creates that root and installs its own guard.
    config.guard = None
    if Path(config.value['output_root']).exists():
        args = list(sys.argv[1:])
        need(args.count('--owner-directory') == 1, 'existing roots admit only an actual owned child bootstrap')
        index = args.index('--owner-directory')
        need(index + 1 < len(args), 'explicit child owner directory')
        folder = Path(args[index + 1]).absolute(); out = Path(config.value['output_root'])
        allowed = [out / 'owner', *(out / 'actors' / key / 'owner' for key in cm.CONTEXTS)]
        need(folder in allowed, 'one exact operation-owned child scope')
        owner, unused = runtime.owner.expected(folder)
        need(os.getpgrp() == owner['pgid'] and os.getppid() == owner['pid'] and
             owner['child_argv'] == [sys.executable, str(Path(sys.argv[0]).absolute()), *args],
             'actual owned parent/group before joining a shared budget')
        config.bootstrap_read_bytes = 0  # Already reserved by the admitted outer.
        config.guard = stack.operation_owner.install_managed_reads(config, 0)
        need(config.guard.report()['total_bytes'] >= FAMILY_BOOTSTRAP_READ_CHARGE,
             'complete potential bootstrap family was reserved before child launch')
    return cm, config, stack, runtime


def durable(path, value, budget):
    body = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    need(0 < len(body) <= 1048576, 'bounded complete durable metadata')
    budget.write(path, body, receipt=True, mode=0o444)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    fd = os.open(Path(path).parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def captured_descriptor(stack, name, root):
    relative = stack.source_freeze['modules'][name]
    need(Path(getattr(stack, name).__file__) == Path(root) / relative, 'one actual captured module origin')
    return {'path': relative, **stack.source_freeze['files'][relative]}


def group_stop(owner, folder, until, proc=None):
    return owner.stop(Path(folder), until, proc)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True); parser.add_argument('--config-sha256', required=True)
    args = parser.parse_args(argv)
    unused, config, stack, runtime = bootstrap(args.config, args.config_sha256)
    result = stack.operation_owner.run_operation(config, stack, runtime)
    print(json.dumps({'status': result['status'], 'output_root': config.value['output_root'],
                      'all_owned_absent': result.get('all_owned_absent', False)}), flush=True)
    return 0 if result['status'] == 'complete_four_cell_operation' and result.get('all_owned_absent') is True else 2


if __name__ == '__main__':
    raise SystemExit(main())
