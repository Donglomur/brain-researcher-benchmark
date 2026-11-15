"""Bounded source/configuration capture; no runtime or scientific imports."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
CONTEXTS = ('frozen_program__cue_only', 'frozen_program__neural',
            'case_adaptive__cue_only', 'case_adaptive__neural')
MODES = ('frozen_program', 'case_adaptive')
RESERVATIONS = {key: {'calls': 1, 'cpu_us': 80000000 if key == 'decide' else 4608000000,
    'model_input_tokens': 0, 'model_output_tokens': 0, 'model_cost_microusd': 0}
    for key in ('prepare', 'decide', 'tool', 'export')}
LIMITS = {'total': {'calls': 292, 'cpu_us': 104864000000, 'model_input_tokens': 0,
                   'model_output_tokens': 0, 'model_cost_microusd': 0},
          'preparation': RESERVATIONS['prepare'], 'wall_us': 900000000,
          'preparation_wall_us': 120000000, 'max_memory_bytes': 4294967296,
          'response_bytes': 262144}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def decode(body):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate configuration key')
            result[key] = value
        return result
    value = json.loads(body, object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite configuration')))
    encode(value)
    return value


def capture(path, cap=262144):
    path = Path(path).absolute()
    need('..' not in path.parts and all(not x.is_symlink() for x in (path, *path.parents)), 'unlinked source/config path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and 0 < a.st_size <= cap, 'ordinary finite source/config')
        with os.fdopen(fd, 'rb', closefd=False) as f:
            body = f.read(cap + 1)
        b = os.fstat(fd)
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        need(len(body) == a.st_size and all(getattr(a, k) == getattr(b, k) for k in fields), 'stable complete source capture')
    finally:
        os.close(fd)
    return body


def checked(root, pin, cap=262144):
    need(type(pin) is dict and set(pin) == {'path', 'bytes', 'sha256'}, 'exact source descriptor')
    path = pin['path']
    need(type(path) is str and not Path(path).is_absolute() and Path(path).as_posix() == path and
         '..' not in Path(path).parts and not any(x in path for x in '\0\r\n'), 'canonical repository-relative descriptor')
    need(type(pin['bytes']) is int and 0 < pin['bytes'] <= cap and type(pin['sha256']) is str and
         re.fullmatch('[a-f0-9]{64}', pin['sha256']), 'bounded descriptor identity')
    body = capture(Path(root) / path, cap)
    need(len(body) == pin['bytes'] and hashlib.sha256(body).hexdigest() == pin['sha256'], 'exact captured descriptor')
    return body


def load(path, expected_sha):
    body = capture(path)
    need(hashlib.sha256(body).hexdigest() == expected_sha, 'exact root-selected config')
    value = decode(body)
    need(value['schema'] == 'dmfc-complete-four-cell-config/v1' and
         value['repository_root'] == str(ROOT), 'one DMFC source repository')
    need(value['limits'] == LIMITS and value['reservation_policy'] == RESERVATIONS,
         'fixed shared limits and complete resource reservations')
    out = Path(value['output_root'])
    need(out.is_absolute() and '..' not in out.parts and
         all(not x.is_symlink() for x in (out, *out.parents)), 'ordinary absolute output root')
    need(set(value['actor']) == {'arms'} and set(value['actor']['arms']) == set(CONTEXTS),
         'all four isolated actor contexts; semantic order comes from CONTEXTS')
    actor_read_bytes = 0
    for key in CONTEXTS:
        arm = value['actor']['arms'][key]
        need(set(arm) == {'actor_context', 'context_dir', 'program', 'config'} and arm['actor_context'] == key and
             arm['context_dir'] == str(out / 'actors' / key), 'exact separate actor directory')
        need(len(os.fsencode(out / 'arms' / key / 'arm.sock')) < 100, 'portable Unix socket path length')
        actor_raw = checked(ROOT, arm['config'], 65536)
        actor_config = decode(actor_raw)
        need(actor_config == {'schema': 'dmfc-offline-reference/v1', 'mode': key,
             'tool_id': 'dmfc_predict@' + value['numerical_tool']['sha256'],
             'policy': 'single_frozen_fit_batch/v1'}, 'only sanitized task config reaches actor')
        actor_body = checked(ROOT, arm['program'], 65536)
        actor_read_bytes += len(actor_raw) + len(actor_body)
        need(arm['program']['path'].startswith('authoring/') and arm['program']['path'].endswith('.py'),
             'admitted actor source executes only in its isolated container')
    for mode in MODES:
        need(value['actor']['arms'][mode + '__cue_only']['program'] ==
             value['actor']['arms'][mode + '__neural']['program'], 'same mode actor source across both views')
    numeric = checked(ROOT, value['numerical_tool'], 65536)
    method = checked(ROOT, value['method'], 32768)
    freeze_body = checked(ROOT, value['successor_freeze'], 262144)
    freeze = decode(freeze_body)
    need(freeze['schema'] == 'dmfc-complete-four-cell-source/v1' and freeze['execution_authority'] is False,
         'source closure itself grants no execution')
    need(freeze['entrypoint']['path'] == (HERE / 'entrypoint.py').relative_to(ROOT).as_posix(),
         'actual task-specific entrypoint')
    files = freeze['files']; need(type(files) is dict and 10 <= len(files) <= 128, 'finite direct source closure')
    captured = {}; total = len(body) + len(freeze_body) + len(numeric) + len(method) + actor_read_bytes
    for relative, pin in files.items():
        need(relative.endswith(('.py', '.json', '.md', '.patch')), 'source metadata only; no scientific arrays')
        raw = checked(ROOT, {'path': relative, **pin}, 1048576)
        total += len(raw); need(total <= 6 * 1024**2, 'complete source capture bound')
        captured[relative] = raw
    need(freeze['entrypoint'] == {'path': freeze['entrypoint']['path'], **files[freeze['entrypoint']['path']]},
         'entrypoint pin belongs to direct closure')
    for descriptor in [value['numerical_tool'], value['method'], *(a[k] for a in value['actor']['arms'].values() for k in ('program', 'config'))]:
        need(files.get(descriptor['path']) == {k: descriptor[k] for k in ('bytes', 'sha256')},
             'every actor/numerical/method input is frozen')
    need(type(freeze['modules']) is dict and all(type(k) is str and v in files for k, v in freeze['modules'].items()),
         'explicit captured module inventory')
    request_body = checked(ROOT, value['request'], 262144)
    request = decode(request_body); total += len(request_body)
    need(total <= 6 * 1024**2, 'complete bootstrap source/metadata read bound')
    payload = {k: v for k, v in value.items() if k != 'request'}
    need(request['configuration_payload_sha256'] == hashlib.sha256(encode(payload)).hexdigest(),
         'root request binds complete config without circular hash')
    return SimpleNamespace(value=value, source_path=Path(path).absolute(), sha256=expected_sha,
        request_sha256=value['request']['sha256'], source_bytes_read=total,
        request=request, numerical_source=numeric, method_source=method), captured, freeze
