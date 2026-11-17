"""Captured-byte binding to accepted NEURAL-031 delivery and ratio scoring."""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import types

HERE = Path(__file__).resolve().parent
PINS = {
    'paired-delivery-v1/io031.py': '41f1b0b696584307c16988e1e5c6e0e771084b7fe6a71fcd6afdf465c9ebd844',
    'paired-delivery-v1/projection031.py': '352ff8bd66e907925a51578962a885ddf0e5e4a34acee99aa49c509d3dcd99d8',
    'paired-delivery-v1/delivery.py': '66bffffab60f3d2b8e1298154601b336770958c1566b1a9d3f5f178a26cdce81',
    'paired-delivery-v1/SOURCES.json': '64fc0b0a0fa1191706181704867ff330ce8f549e3cc8a5e390153f6a79efdbbd',
    'paired-delivery-v1/SOURCE_INPUTS.json': '399d6bf289710f0041cdde25b8613ed87d692e0eff9a3a3ad7b77e909664c63f',
    'ratio-scoring-v1/endpoint.py': 'c297b57480238d03603413833a9e808f1c7326a39ea11670428abf80e51219fc',
    'ratio-scoring-v1/score.py': '6e063200b9f294f1dbce4c69f7ead5036e72926f4866f317f039b127466f90ed'}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def read(path, cap, expected=None):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and 0 < info.st_size <= cap,
             'Bounded ordinary singly linked file required')
        body = stream.read(cap + 1)
        need(len(body) == info.st_size, 'File extent changed')
    need(expected is None or pin(body) == expected, 'Content identity changed')
    return body


def decode(body):
    def unique(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=unique,
                      parse_constant=lambda _: need(False, 'Nonfinite JSON constant'))


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def write(path, body, cap, mode=0o600):
    need(type(body) is bytes and 0 < len(body) <= cap, 'Bounded output bytes required')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body); stream.flush(); os.fsync(stream.fileno())
    os.chmod(path, mode)
    return pin(body)


def dependencies():
    bodies = {}
    for relative, digest in PINS.items():
        body = read(HERE.parent / relative, 131072)
        need(pin(body)['sha256'] == digest, 'Accepted dependency changed: ' + relative)
        bodies[relative] = body
    modules = {}
    for relative, name in [('paired-delivery-v1/io031.py', 'io031'),
                           ('paired-delivery-v1/projection031.py', 'projection031'),
                           ('ratio-scoring-v1/endpoint.py', 'endpoint'),
                           ('paired-delivery-v1/delivery.py', '_n031_delivery'),
                           ('ratio-scoring-v1/score.py', '_n031_score')]:
        module = types.ModuleType(name)
        module.__file__ = str(HERE.parent / relative)
        sys.modules[name] = module
        exec(compile(bodies[relative], module.__file__, 'exec'), module.__dict__)
        modules[name] = module
    delivery, endpoint, score = modules['_n031_delivery'], modules['endpoint'], modules['_n031_score']
    source = delivery.validate_inputs(decode(bodies['paired-delivery-v1/SOURCE_INPUTS.json']))
    # Preserve accepted operations while binding their late dependency lookup
    # to already authenticated captured bytes, not a second mutable file read.
    delivery.endpoint = lambda: endpoint
    delivery.inputs = lambda: decode(encoded(source))
    need(score.endpoint is endpoint, 'Captured scorer endpoint binding')
    return delivery, endpoint, score
