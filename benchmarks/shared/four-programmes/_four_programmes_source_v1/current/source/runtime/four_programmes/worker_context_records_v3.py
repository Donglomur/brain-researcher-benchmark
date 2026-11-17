"""Closed native V2 wire records, using the unchanged base-record validator.

This module validates metadata only. A valid value never issues a live owner.
"""
import hashlib
import re
from .common import need
from .backend_json import canonical, parse, scalar_text
from .precommit_records import validate_type as validate_base
from .worker_context_schema_v3 import PRIMITIVES, RECORDS

_ARRAY = re.compile(r'([^\[]+)\[([0-9]+):([0-9]+)\]')
_HASH = re.compile(r'[0-9a-f]{64}')

def validate(kind, value, depth=0):
    need(type(depth) is int and depth <= 64, 'finite native record nesting')
    if type(kind) is str:
        match = _ARRAY.fullmatch(kind)
        if match:
            child, lo, hi = match.groups()
            need(type(value) is list and int(lo) <= len(value) <= int(hi), 'closed native array extent')
            for item in value:
                validate(child, item, depth + 1)
            return
        definition = RECORDS.get(kind, PRIMITIVES.get(kind))
        if definition is None:
            validate_base(kind, value)
            return
        validate(definition, value, depth + 1)
        if kind == 'ChunkHex':
            need(len(value) % 2 == 0 and re.fullmatch('[0-9a-f]*', value) is not None,
                 'exact lower hex bytes')
        elif kind in ('AbsolutePath', 'PathComponent'):
            parts = value.split('/')
            if kind == 'AbsolutePath':
                need(value.startswith('/') and not value.endswith('/') and
                     all(part not in ('', '.', '..') for part in parts[1:]), 'canonical absolute path')
            else:
                need('/' not in value and value not in ('.', '..'), 'one safe path component')
        elif kind == 'NamespaceLink':
            need(re.fullmatch(r'(cgroup|ipc|mnt|net|pid|user|uts):\[[0-9]+\]', value) is not None,
                 'fixed kernel namespace link')
        return
    need(type(kind) is dict, 'source-owned closed type definition')
    tag = kind['kind']
    if tag == 'literal':
        need(type(value) is type(kind['value']) and value == kind['value'], 'exact literal including bool type')
    elif tag == 'boolean':
        need(type(value) is bool, 'builtin boolean')
    elif tag == 'integer':
        need(type(value) is int and kind['minimum'] <= value <= kind['maximum'], 'bounded exact integer')
    elif tag == 'string':
        scalar_text(value, maximum=kind['maximum_length'])
        need(len(value) >= kind['minimum_length'], 'minimum string length')
    elif tag == 'enum':
        need(type(value) is str and value in kind['values'], 'closed string enum')
    elif tag == 'nullable':
        if value is not None:
            validate(kind['value_type'], value, depth + 1)
    elif tag == 'closed_map':
        need(type(value) is dict and set(value) == set(kind['keys']), 'all exact resource dimensions')
        for item in value.values():
            validate(kind['values'], item, depth + 1)
    elif tag == 'closed_record':
        need(type(value) is dict and set(value) == set(kind['fields']), 'exact native record fields')
        for field, child in kind['fields'].items():
            validate(child, value[field], depth + 1)
    elif tag == 'closed_schema_discriminated_union':
        need(type(value) is dict and type(value.get('schema')) is str, 'closed schema discriminator')
        choices = [name for name in kind['alternatives'] if RECORDS[name]['schema_literal'] == value['schema']]
        need(len(choices) == 1, 'one selected current payload alternative')
        validate(choices[0], value, depth + 1)
    else:
        raise RuntimeError('unimplemented native schema kind')

def body(record_kind, **fields):
    result = {'schema': RECORDS[record_kind]['schema_literal'], **fields}
    validate(record_kind, result)
    return result

def encode(kind, value, cap):
    validate(kind, value)
    return canonical(value, cap, maximum_depth=64)

def decode(kind, raw, cap):
    value = parse(raw, cap, maximum_depth=64, maximum_members=cap, maximum_string_bytes=cap)
    validate(kind, value)
    need(canonical(value, cap, maximum_depth=64) == raw, 'exact canonical complete wire bytes')
    return value

def pinned(raw, descriptor):
    validate_base('Pin', descriptor)
    need(type(raw) is bytes and len(raw) == descriptor['bytes'] and
         hashlib.sha256(raw).hexdigest() == descriptor['sha256'], 'actual retained bytes match delivered Pin')
    return True

def equal(left, right):
    # Exact metadata equality, never live-owner/capability equality.
    return type(left) is type(right) and left == right
