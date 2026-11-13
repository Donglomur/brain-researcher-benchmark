"""Closed task-specific reference request; validation never reads recording data."""
import math
import os
from pathlib import Path
import re
import stat
import time
from find032.core import Refusal
from find032_runtime.staging import strict

SCOPE = {'participants': 33, 'recordings': 132, 'planned_products': 990,
         'comparison_dispositions': 52, 'BF10_dispositions': 3, 'figures': 6}
TIMES = ('origin', 'work_end', 'child_end', 'cleanup_end', 'owner_end', 'final_end')
CAPACITY = {'read_bytes', 'write_bytes', 'creation_attempts', 'child_attempts',
            'provider_calls', 'input_tokens', 'output_tokens', 'currency_units',
            'live_fds', 'rss_bytes', 'wall_seconds', 'cpu_seconds'}


def need(value, why):
    if not value:
        raise Refusal('reference production: ' + why)


def keys(value, expected, why):
    need(type(value) is dict and set(value) == set(expected), why + ' exact keys')
    return value


def path(value):
    need(type(value) is str and value.startswith('/') and '\x00' not in value and
         '\\' not in value and os.path.normpath(value) == value and len(value) <= 4096,
         'absolute normalized path')
    p = Path(value)
    need(not any(x.is_symlink() for x in (p, *p.parents)), 'no linked path ancestor')
    return p


def pin(value, *, executable=False):
    keys(value, ('bytes', 'sha256', 'mode'), 'selected pin')
    modes = (0o500, 0o555, 0o755) if executable else (0o400, 0o444, 0o644)
    need(type(value['bytes']) is int and 0 < value['bytes'] <= (134217728 if executable else 1048576)
         and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256'])
         and type(value['mode']) is int and value['mode'] in modes, 'selected finite pin')
    return value


def limits(value):
    keys(value, ('read_bytes', 'write_bytes', 'files'), 'logical budget')
    need(all(type(n) is int and n > 0 for n in value.values()), 'positive selected logical budgets')


def host(value):
    keys(value, ('schema', 'capacity', 'recovery_capacity', 'cgroup_parent', 'group_prefix',
                 'memory_bytes', 'pids', 'cpu_quota', 'cpu_period', 'cleanup_seconds'), 'host selection')
    need(value['schema'] == 'find032_original_host_owner_v1', 'existing concrete NativeOwner ABI')
    path(value['cgroup_parent'])
    need(type(value['group_prefix']) is str and re.fullmatch('[a-z0-9-]{1,80}', value['group_prefix']),
         'unique task cgroup prefix')
    for name in ('capacity', 'recovery_capacity'):
        keys(value[name], CAPACITY, name)
        for key, n in value[name].items():
            need(type(n) in (int, float) and math.isfinite(n) and n >= 0, 'finite capacity')
            if key not in ('wall_seconds', 'cpu_seconds', 'currency_units'):
                need(type(n) is int, 'integer capacity')
        need(value[name]['child_attempts'] >= 1, 'existing normal and cleanup reserve')
        need(all(value[name][x] == 0 for x in ('provider_calls', 'input_tokens', 'output_tokens', 'currency_units')),
             'reference uses no provider/model services')
    need(all(type(value[k]) is int and value[k] > 0 for k in ('memory_bytes', 'pids', 'cpu_quota', 'cpu_period')),
         'positive selected host enclosure')
    need(type(value['cleanup_seconds']) is int and math.isfinite(value['cleanup_seconds']) and
         value['cleanup_seconds'] > 0, 'positive original cleanup reserve')


def private_directory(p):
    p = path(str(p)); s = p.lstat()
    need(stat.S_ISDIR(s.st_mode) and s.st_uid == 0 and stat.S_IMODE(s.st_mode) == 0o700,
         'existing root-owned 0700 protected parent')
    return (s.st_dev, s.st_ino)


def validate(raw, source_root):
    cfg = strict(raw)
    keys(cfg, ('schema', 'profile', 'python', 'python_pin', 'input_root', 'input_manifest',
               'input_manifest_pin', 'protected_parent', 'run_name', 'final_name',
               'numerical_search_roots', 'runtime_environment', 'fixed_seed', 'output', 'budgets', 'times',
               'host_selection'), 'reference request')
    need(cfg['schema'] == 'FIND032_REFERENCE_PRODUCTION_V1' and cfg['profile'] == 'corrected_methods_v1',
         'exact complete corrected profile; no historical parity claim')
    pin(cfg['python_pin'], executable=True); pin(cfg['input_manifest_pin'])
    for key in ('python', 'input_root', 'input_manifest', 'protected_parent'):
        path(cfg[key])
    for key in ('run_name', 'final_name'):
        need(type(cfg[key]) is str and re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}', cfg[key]), 'private basename')
    need(len({cfg[k] for k in ('run_name', 'final_name')}) == 2, 'disjoint operation basenames')
    protected = path(cfg['protected_parent']); private_directory(protected)
    roots = [path(cfg['input_root']), path(str(source_root)), protected]
    for i, left in enumerate(roots):
        need(all(not left.is_relative_to(right) and not right.is_relative_to(left) for right in roots[i+1:]),
             'source, authentic input and protected output roots disjoint')
    manifest = path(cfg['input_manifest'])
    need(not manifest.is_relative_to(roots[0]) and not manifest.is_relative_to(roots[1]),
         'ordinary input metadata outside recording/source trees')
    need(type(cfg['fixed_seed']) is int and 0 <= cfg['fixed_seed'] <= 2**32 - 1, 'original explicit group seed')
    keys(cfg['output'], ('member_bytes', 'total_bytes', 'file_count', 'receipt_bytes'), 'output ceilings')
    out = cfg['output']
    need(all(type(n) is int and n > 0 for n in out.values()) and out['member_bytes'] <= out['total_bytes']
         and out['file_count'] == 1087 and 0 < out['receipt_bytes'] <= 1048576,
         'full output protocol and explicit finite ceilings')
    keys(cfg['budgets'], ('science', 'child_evidence', 'finalization', 'diagnostic'), 'phase budgets')
    for value in cfg['budgets'].values(): limits(value)
    need(cfg['budgets']['science']['write_bytes'] >= out['total_bytes'] and
         cfg['budgets']['science']['files'] >= 1087, 'full potential output reservation; no subset')
    need(cfg['budgets']['child_evidence']['read_bytes'] >= out['member_bytes'], 'child terminal pin capture reserve')
    need(cfg['budgets']['diagnostic']['write_bytes'] >= 2*out['receipt_bytes']+16384 and
         cfg['budgets']['diagnostic']['files'] >= 2, 'independent final failure/summary evidence reserve')
    need(cfg['budgets']['child_evidence']['write_bytes'] >= out['receipt_bytes'] and
         cfg['budgets']['child_evidence']['files'] >= 1, 'independent full child failure receipt reserve')
    need(cfg['budgets']['finalization']['read_bytes'] >= out['total_bytes'] + 36*out['member_bytes'] + out['receipt_bytes']
         and cfg['budgets']['finalization']['write_bytes'] >= 3*out['receipt_bytes'] + 65537
         and cfg['budgets']['finalization']['files'] >= 5,
         'complete output verification plus bounded streams and reports selected before launch')
    keys(cfg['times'], TIMES, 'original monotonic time selection')
    times = [cfg['times'][k] for k in TIMES]
    need(all(type(n) in (int,float) and math.isfinite(n) for n in times)
         and all(a < b for a,b in zip(times,times[1:])), 'strict original phase order')
    need(times[0] <= time.monotonic() < cfg['times']['work_end'], 'live original work interval')
    host(cfg['host_selection'])
    libs = cfg['numerical_search_roots']
    need(type(libs) is list and 1 <= len(libs) <= 8 and len(set(libs)) == len(libs), 'explicit numerical roots')
    for value in libs:
        library = path(value)
        need(library.is_dir() and all(not library.is_relative_to(p) and not p.is_relative_to(library) for p in roots),
             'scientific library prefixes outside source/input/protected custody')
    keys(cfg['runtime_environment'], ('R_HOME','LD_LIBRARY_PATH','TZ'), 'explicit native environment')
    need(cfg['runtime_environment']['TZ']=='UTC','same prospective selected timezone')
    rh=path(cfg['runtime_environment']['R_HOME']);rl=path(cfg['runtime_environment']['LD_LIBRARY_PATH'])
    need(rh.is_dir() and rl==rh/'lib' and rl.is_dir() and
         all(not rh.is_relative_to(p) and not p.is_relative_to(rh) for p in roots),
         'explicit disjoint existing R installation/library')
    return cfg
