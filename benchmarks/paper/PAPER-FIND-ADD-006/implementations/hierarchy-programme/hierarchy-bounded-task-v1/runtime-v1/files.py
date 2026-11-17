"""Small source/metadata helpers; never interpret empirical numerical arrays."""
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import re
import types

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ID = 'PAPER-FIND-ADD-006'
RUNTIME_ID = 'hierarchy_bounded_task_v1'


def need(ok, text):
    if not ok:
        raise ValueError(text)


def path(relative):
    p = Path(relative)
    need(type(relative) is str and relative and not p.is_absolute() and '..' not in p.parts
         and p.as_posix() == relative and not any(c in relative for c in ',\r\n'), 'Canonical project path')
    return ROOT / p


def stream(source, cap):
    p = Path(source).absolute()
    need('..' not in p.parts and all(not x.is_symlink() for x in (p, *p.parents)), 'Unlinked path')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    a = os.fstat(fd)
    if not (stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and 0 < a.st_size <= cap):
        os.close(fd)
        raise ValueError('Bounded ordinary single-link file')
    return os.fdopen(fd, 'rb'), a


def stable(a, b):
    need(all(getattr(a, k) == getattr(b, k) for k in
             ('st_dev', 'st_ino', 'st_size', 'st_nlink', 'st_mode', 'st_mtime_ns', 'st_ctime_ns')), 'Stable full input')


def read(source, cap=250000):
    f, a = stream(source, cap)
    with f:
        raw = f.read(cap + 1)
        stable(a, os.fstat(f.fileno()))
    need(len(raw) == a.st_size, 'Complete bytes')
    return raw


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def opaque(source, cap):
    f, a = stream(source, cap)
    h = hashlib.sha256()
    with f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
        stable(a, os.fstat(f.fileno()))
    return {'bytes': a.st_size, 'sha256': h.hexdigest()}


def descriptor(value, cap=250000, decode=True):
    need(type(value) is dict and set(value) == {'path', 'bytes', 'sha256'}, 'Exact file descriptor')
    need(type(value['bytes']) is int and 0 < value['bytes'] <= cap and
         type(value['sha256']) is str and re.fullmatch('[a-f0-9]{64}', value['sha256']), 'Typed file descriptor')
    raw = read(path(value['path']), cap)
    need(pin(raw) == {k: value[k] for k in ('bytes', 'sha256')}, 'Pinned identity')
    return strict_json(raw) if decode else raw


def strict_json(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'Unique JSON keys')
            result[key] = value
        return result
    def number(token):
        value = float(token)
        need(math.isfinite(value), 'Finite JSON number')
        return value
    return json.loads(raw, object_pairs_hook=pairs, parse_float=number,
                      parse_constant=lambda value: need(False, 'Finite JSON constants'))


def captured_module(source, name, register=False):
    import sys
    body = descriptor(source, 2000000, decode=False)
    source_path = path(source['path'])
    if name in sys.modules:
        need(Path(sys.modules[name].__file__).resolve() == source_path.resolve(), 'Exact module namespace')
        return sys.modules[name]
    module = types.ModuleType(name)
    module.__file__ = str(source_path)
    module.__package__ = ''
    if register:
        sys.modules[name] = module
    try:
        exec(compile(body, str(source_path), 'exec'), module.__dict__)
    except BaseException:
        if register:
            sys.modules.pop(name, None)
        raise
    return module


def json_read(source, cap=250000):
    return strict_json(read(source, cap))


def write(source, value, cap=250000):
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    need(len(raw) <= cap, 'Bounded complete metadata')
    fd = os.open(source, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    with os.fdopen(fd, 'wb') as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    return pin(raw)


def freeze(review, filename='FREEZE.json'):
    need(filename in ('FREEZE.json', 'PREP_FREEZE.json'), 'Declared source closure role')
    raw = read(HERE / filename, 500000)
    need(pin(raw)['sha256'] == review['freeze_sha256'], 'Root-bound final source freeze')
    value = strict_json(raw)
    need(value['candidate_id'] == ID and 1 <= len(value['files']) <= 256, 'Bounded exact source closure')
    for relative, item in value['files'].items():
        need(pin(read(path(relative), 2000000)) == item, 'Source closure drift: ' + relative)
    return value


def accounting(review, seconds):
    old = descriptor(review['latest_accounting_evidence'], 500000)
    field = review['prior_seconds_field']
    need(type(field) is str and '.' not in field and field in old, 'Explicit actual prior field')
    prior = review['prior_known_seconds']
    need(type(prior) in (int, float) and math.isfinite(prior) and prior >= 2520 and old[field] == prior
         and review['known_after_seconds'] == prior + seconds, 'Full family history, no reset')
    need(old.get('candidate_id') == ID and review['prior_required_status'] == old['status'], 'Same closed task family')
    need(review['prior_is_latest_known_closed_family_event'] is True,
         'Root attests latest actual closed family event')
    initial = {'path': 'authoring/next-two-unbuilt-papers-20261103/hierarchy-source-curves-reference-v1/runtime-v1/root-neural-hierarchycurves001/ROOT_OBSERVED_PROCESS.json',
               'bytes': 3462, 'sha256': '9d5c1cfb40b3e79cd79e307324ebaaff080b8b95d51b59bfd41b5d718eeed944'}
    if review['latest_accounting_evidence'] == initial:
        root = descriptor({'path': 'authoring/next-two-unbuilt-papers-20261103/hierarchy-source-curves-reference-v1/runtime-v1/root-authority001/ROOT_OBSERVED_PROCESS.json',
                           'bytes': 1225, 'sha256': '88c37d617731763a66ad16d9a6a1dcacabab43dd559fc7c22eb58ceb2bf3f8fd'})
        need(prior == 2520 and field == 'known_recorded_chain_after_seconds'
             and old['status'] == 'source_defined_hierarchy_reference_admitted'
             and old.get('known_recorded_chain_before_seconds') == 2340 and old.get('full_charge_seconds') == 180
             and old.get('source_freeze', {}).get('sha256') == 'aac4f32902234e7f0a07d0e7903e015c4028591ec7089ee3a03d278d2b428a33'
             and old.get('create_outcome_unresolved') is False and old.get('worker_returncode') == 0
             and old.get('audit_failures') == [] and old.get('all_owned_absent') is True
             and old.get('id_absent') is True and old.get('name_absent') is True
             and old.get('all_attach_clis_reaped') is True and old.get('all_cli_groups_absent') is True,
             'Exact admitted source-curves actual001 with complete native closure through2520')
        need(root.get('root_invocation_sha256') == '833adb2a31a41f90b479781c5a7021c1c96f3612a36bea9a357f44ea58ce704e'
             and root.get('known_before_seconds') == 2340 and root.get('full_allocation_seconds') == 180
             and root.get('known_after_dispatch_seconds') == 2520 and root.get('returncode') == 0
             and root.get('process_reaped') is True and root.get('outer_group_absent') is True
             and root.get('external_timeout') is False and root.get('overrun_requires_separate_accounting') is False,
             'Exact enclosing root observer is closed with the same full180 allowance')
    else:
        need(old.get('runtime_id') == RUNTIME_ID and field == 'known_after_seconds' and
             old.get('source_freeze_sha256') == review['freeze_sha256'] and
             old.get('controller_process_reaped') is True and
             type(old.get('charged_seconds')) in (int, float) and old['charged_seconds'] >= 780 and
             type(old.get('prior_known_seconds')) in (int, float) and old['prior_known_seconds'] >= 2520 and
             old['known_after_seconds'] == old['prior_known_seconds'] + old['charged_seconds'],
             'Same reviewed ordinary actual additive allowance')
        need(old.get('all_owned_absent') is True and old.get('all_activated_groups_absent') is True,
             'Actual prior resources and process groups absent')
    return prior
