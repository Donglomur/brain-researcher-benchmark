"""Strict primitive metadata and prospective admission; no original operands at import."""
import hashlib
import json
import math
import re

class Refused(ValueError):
    pass

def need(test, message):
    if not test:
        raise Refused(message)

def integer(x, minimum=0):
    return type(x) is int and x >= minimum

def finite(x):
    return type(x) in (float, int) and math.isfinite(x)

def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')

def typed_equal(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(typed_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(typed_equal(x,y) for x,y in zip(a,b))
    return a == b

def pin(x):
    need(type(x) is dict and set(x)=={'bytes','sha256'} and integer(x['bytes'])
         and type(x['sha256']) is str and re.fullmatch('[0-9a-f]{64}',x['sha256']), 'exact byte/hash pin')
    return x

def pin_bytes(b):
    need(type(b) is bytes, 'explicit bytes')
    return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}

def relative(s):
    need(type(s) is str and s and not s.startswith('/') and '\\' not in s
         and all(x not in ('','.','..') for x in s.split('/')), 'canonical relative path')
    return s

def artifact(d):
    need(type(d) is dict and set(d)=={'path','pin'}, 'artifact descriptor')
    relative(d['path']);pin(d['pin']);return d

def opaque(x):
    need(type(x) is str and re.fullmatch('[0-9a-f]{32}',x), 'opaque identity')
    return x

ENDPOINTS = {'angle':'Reach_angle_degrees','magnitude':'Reach_magnitude_px','speed':'Onset_speed_px_per_sec'}
D_LITERAL = 'NEURAL049.curated-retrospective.v1.D'
SCHEMA = 'neural049_nwb_converter_f44ca6f6_v1'
QUALIFICATIONS = ('source_membership','cue_target_provenance','clock_grid','channel_axis',
                  'availability','upstream_retrospective','license_privacy','environment',
                  'physical_roots','resources')
BASE_LIMITS = {'read_bytes','write_bytes','array_bytes','metadata_bytes','files'}
EXTRA_LIMITS = {'array_elements','live_bytes','rows','channels','source_files','output_files'}

def array_descriptor(d):
    need(type(d) is dict and set(d)=={'path','bytes','sha256','dtype','shape'}, 'array descriptor fields')
    relative(d['path']);pin({'bytes':d['bytes'],'sha256':d['sha256']})
    need(d['dtype'] in ('<f8','|b1') and type(d['shape']) is list
         and all(integer(n) for n in d['shape']), 'primitive array shape/dtype')
    return d

def shape_bytes(shape, dtype):
    need(type(shape) in (tuple,list) and all(integer(n) for n in shape), 'primitive shape')
    need(dtype in ('<f8','|b1'), 'only little-endian float64 or bool')
    count=1
    for n in shape: count*=n
    return count, count*(8 if dtype=='<f8' else 1)


def parse_json(body):
    def pairs(items):
        result={}
        for key,value in items:
            need(key not in result,'duplicate JSON key')
            result[key]=value
        return result
    def invalid(value):
        raise Refused('nonfinite JSON constant')
    return json.loads(body,object_pairs_hook=pairs,parse_constant=invalid)
