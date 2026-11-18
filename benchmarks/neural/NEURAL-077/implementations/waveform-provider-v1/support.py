"""Exact NEURAL-077 source and private-artifact operations; no provider requests."""
from pathlib import Path
import hashlib
import json
import os
import stat
import sys
import types

HERE = Path(__file__).resolve().parent
CONDITION = 'legacy_waveform_no_tools'
ROUTE = 'trusted_openai_responses_waveform_v1'


def need(value, message):
    if not value:
        raise ValueError(message)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def pairs(items):
    result = {}
    for key, value in items:
        need(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def decode(body):
    return json.loads(body.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def encode(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n').encode()


def path(value):
    result = Path(value).absolute()
    need(all(not item.is_symlink() for item in (result, *result.parents)), 'Linked path refused')
    return result


def read(value, cap=1048576, expected=None, empty=False):
    target = path(value)
    fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and (0 if empty else 1) <= before.st_size <= cap, 'Bounded ordinary single-link file required')
        body = stream.read(cap + 1)
        need(len(body) == before.st_size and fields(before) == fields(os.fstat(stream.fileno()))
             == fields(target.lstat()), 'Input changed during capture')
    need(expected is None or pin(body) == expected, 'Input pin mismatch')
    return body


def write(value, body):
    target = path(value)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    return pin(body)


def module(name, source_path, body):
    result = types.ModuleType(name)
    result.__file__ = str(source_path)
    sys.modules[name] = result
    exec(compile(body, str(source_path), 'exec'), result.__dict__)
    return result


def sources(implementations_root):
    root = path(implementations_root)
    bindings = decode(read(HERE / 'SOURCE_BINDINGS.json', 16384))
    bodies = {name: read(root / name, 65536, expected) for name, expected in bindings.items()}
    bundle = module('neural077_provider_original_bundle', root / 'waveform-pair-v1/bundle.py',
                    bodies['waveform-pair-v1/bundle.py'])
    previous = sys.modules.get('bundle')
    try:
        sys.modules['bundle'] = bundle
        pair = module('neural077_provider_original_pair', root / 'waveform-pair-v1/pair.py',
                      bodies['waveform-pair-v1/pair.py'])
    finally:
        if previous is None:
            sys.modules.pop('bundle', None)
        else:
            sys.modules['bundle'] = previous
    transport, comparator, original_bodies, original_bindings = pair.sources()
    need(all(bindings[name] == value for name, value in original_bindings.items()), 'Original pair closure mismatch')
    delivery, parser = transport.dependencies()
    bridge = module('neural077_provider_original_bridge', root / 'waveform-transport-v1/provider_bridge.py',
                    bodies['waveform-transport-v1/provider_bridge.py'])
    return {'root': root, 'bindings': bindings, 'bodies': bodies, 'pair': pair, 'transport': transport,
            'comparator': comparator, 'original_bodies': original_bodies, 'original_bindings': original_bindings,
            'delivery': delivery, 'parser': parser, 'bridge': bridge}


def identity():
    return {name: pin(read(HERE / name, 131072))
            for name in ('support.py', 'client.py', 'provider_arm.py', 'SOURCE_BINDINGS.json')}
