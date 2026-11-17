"""Strict released-array-position profile; no physical-person join is admitted."""
from __future__ import annotations
import hashlib
import json
import math
import os
import stat
import time

PARTICIPANTS = [1, 3, 5, 6, 7, 10, 12, 14, 15, 17, 22, 23, 25, 26, 27]
CONDITIONS = ['NT.pin.all', 'NT.pout.all', 'T.pin.all', 'T.pout.all']
SHAPE = [62, 53, 200, 15]
WINDOWS = {'delay1': [0.5, 1.5], 'delay2': [3.0, 4.0]}
FREQUENCY = [8.0, 12.0]
MASTER_PIN = {'bytes':298290277,'sha256':'536e9513b13dc721cf60613334ee37ce546e7bf67154d95bd067ddc0f0023a95'}
EXPECTED_LABELS = ['Fp1', 'Fz', 'F3', 'F7', 'FT9', 'FC5', 'FC1', 'C3', 'T7', 'CP5', 'CP1', 'Pz', 'P3', 'P7', 'O1', 'Oz', 'O2', 'P4', 'P8', 'CP6', 'CP2', 'C4', 'T8', 'FT10', 'FC6', 'FC2', 'F4', 'F8', 'Fp2', 'AF7', 'AF3', 'AFz', 'F1', 'F5', 'FT7', 'FC3', 'C1', 'C5', 'TP7', 'CP3', 'P1', 'P5', 'PO7', 'PO3', 'POz', 'PO4', 'PO8', 'P6', 'P2', 'CPz', 'CP4', 'TP8', 'C6', 'C2', 'FC4', 'FT8', 'F6', 'AF8', 'AF4', 'F2', 'FCz', 'Cz']
FT_COMMIT = '878647eb0f1621aa1e21f0d47a663eedf1b9d65f'
HOLDS = [
 'complete authentic derivative custody, binary64 storage and measured axes',
 'physical-person identity remains unverified; paired-person endpoints are excluded',
 'induced/evoked and dB baseline preprocessing provenance',
 'publication/source exposure and data access terms',
 'exact MATLAB and complete FieldTrip environment and path qualification',
 'native numerical parity and operator tolerance justification',
 'candidate isolation, complete capture, natural exit and exclusive custody',
 'matched A/B model, resource and context policy with no cross-arm feedback',
 'scientific execution authorization and empirical reproduction',
]

class Refusal(ValueError): pass

def require(ok, why):
    if not ok: raise Refusal(why)

def strict_int(value, lower=0):
    return type(value) is int and value >= lower

def keys(value, expected):
    require(type(value) is dict and set(value) == set(expected), 'closed schema keys')

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def pin(value):
    keys(value, ['bytes', 'sha256'])
    require(strict_int(value['bytes'], 1) and type(value['sha256']) is str and len(value['sha256']) == 64 and all(x in '0123456789abcdef' for x in value['sha256']), 'body pin')

class Budget:
    """Explicit cumulative logical transfers; not a native hard quota or memory cap."""
    def __init__(self, read_bytes, write_bytes, seconds):
        require(strict_int(read_bytes, 1) and strict_int(write_bytes, 1), 'positive byte operands')
        require(type(seconds) in (int, float) and math.isfinite(seconds) and seconds > 0, 'positive deadline operand')
        self.read_limit, self.write_limit = read_bytes, write_bytes
        self.reads = self.writes = 0
        self.deadline = time.monotonic() + seconds
    def charge(self, read=0, write=0):
        require(strict_int(read) and strict_int(write), 'nonnegative transfer')
        require(time.monotonic() < self.deadline, 'deadline')
        require(self.reads + read <= self.read_limit and self.writes + write <= self.write_limit, 'transfer cap')
        self.reads += read; self.writes += write

def open_pinned(path, expected, budget):
    """Read-only ordinary single-link capture; caller must exclude concurrent writers."""
    pin(expected)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == expected['bytes'], 'ordinary pinned body')
        h = hashlib.sha256()
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            while True:
                budget.charge(read=min(65536, before.st_size - stream.tell()))
                block = stream.read(min(65536, before.st_size - stream.tell()))
                if not block: break
                h.update(block)
        after = os.fstat(fd)
        require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns), 'body changed during authentication')
        require(h.hexdigest() == expected['sha256'], 'body digest')
        os.lseek(fd, 0, os.SEEK_SET)
        return fd
    except BaseException:
        os.close(fd); raise

def read_pinned(path, expected, budget):
    fd = open_pinned(path, expected, budget)
    try:
        budget.charge(read=expected['bytes'])
        with os.fdopen(fd, 'rb', closefd=False) as stream: data = stream.read(expected['bytes'] + 1)
        require(len(data)==expected['bytes'] and hashlib.sha256(data).hexdigest()==expected['sha256'], 'changed captured body')
        return data
    finally: os.close(fd)

def json_body(data):
    def pairs(rows):
        out = {}
        for k,v in rows:
            require(k not in out, 'duplicate JSON key'); out[k]=v
        return out
    return json.loads(data, object_pairs_hook=pairs, parse_constant=lambda x: (_ for _ in ()).throw(Refusal('nonfinite JSON')))

DRIVER_SOURCE = {'bytes':1872,'sha256':'41861a53e44b7e316374515739fff12b80b4f4676b3bc0b8086476357b4b8b1e'}
HELPER_SOURCE = {'bytes':2546,'sha256':'c62c71d3f96c8399d9cd578c91b9fa6a3a99cdb449e8dbedd683c5c5490c0e23'}
IDENTITY_SCHEMA = 'tms_figure2b_source_position_identity_v1'
OUTPUT_SCHEMA = 'tms_figure2b_source_position_full_output_v1'

def metadata(meta):
    keys(meta, ['schema','shape','participant_axis_identity','conditions','labels','frequency','time','source','provenance'])
    require(meta['schema']==IDENTITY_SCHEMA and type(meta['shape']) is list and meta['shape']==SHAPE and all(type(x) is int for x in meta['shape']), 'full released-array geometry')
    axis=meta['participant_axis_identity']
    keys(axis,['kind','positions','physical_id_map_verified','source_order_preserved','source_declared_study_roster'])
    require(axis['kind']=='released_array_positions' and type(axis['positions']) is list and axis['positions']==list(range(15)) and all(type(x) is int for x in axis['positions']), 'all 15 original source positions')
    require(axis['physical_id_map_verified'] is False and axis['source_order_preserved'] is True, 'source positions do not admit physical-person identity or reordering')
    roster=axis['source_declared_study_roster']
    require(type(roster) is list and roster==PARTICIPANTS and all(type(x) is int for x in roster), 'source-declared roster is informational, never a position map')
    require(meta['conditions']==CONDITIONS, 'all four conditions')
    labels=meta['labels']
    require(type(labels) is list and len(labels)==62 and all(type(x) is str and x and '\0' not in x for x in labels), 'complete string channel identity')
    require(len(set(labels))==62 and set(labels)==set(EXPECTED_LABELS),'complete exact plotting-channel set; no reorder or drop')
    for key,n in [('frequency',53),('time',200)]:
        coordinates=meta[key]
        require(type(coordinates) is list and len(coordinates)==n and all(type(x) in (int,float) and math.isfinite(x) for x in coordinates), 'finite full numeric axis; no booleans')
        require(all(a<b for a,b in zip(coordinates,coordinates[1:])), 'strictly increasing axis')
    pin(meta['source']); require(meta['source']==MASTER_PIN,'selected released derivative body')
    provenance=meta['provenance']
    keys(provenance,['endpoint','published_driver','published_helper','units_interpretation','storage','upstream_preprocessing_verified','paired_person_inference_admitted'])
    require(provenance['endpoint']=='released_artifact_group_topography', 'operator-specific group endpoint')
    for key,expected in [('published_driver',DRIVER_SOURCE),('published_helper',HELPER_SOURCE)]:
        pin(provenance[key]); require(provenance[key]==expected, 'exact published arithmetic source')
    require(provenance['units_interpretation']=='dB_as_used_by_published_operator' and provenance['storage']=='MATLAB-double', 'explicit source arithmetic interpretation and binary64 storage')
    require(provenance['upstream_preprocessing_verified'] is False and provenance['paired_person_inference_admitted'] is False, 'no inferred preprocessing or paired-person admission')
    return meta

def field_specs(meta, nearest_window):
    metadata(meta)
    nfreq=len(nearest_window(meta['frequency'], FREQUENCY))
    out={}
    def add(name,shape,kind): out[name]={'shape':shape,'dtype':kind,'bytes':math.prod(shape)*{'f8':8,'u2':2,'u1':1}[kind]}
    for cond in CONDITIONS:
        stem='mean.'+cond
        for suffix,kind in [('value','f8'),('undefined','u1'),('positions','u2'),('contributors','u1')]: add(stem+'.'+suffix,[62,53,200],kind)
    for cond in ['NT','T']:
        for suffix,kind in [('value','f8'),('undefined','u1')]:add('normalized.'+cond+'.'+suffix,[62,53,200],kind)
        for win in WINDOWS:
            stem='window.'+cond+'.'+win
            for suffix,shape,kind in [('value',[62],'f8'),('undefined',[62],'u1'),('time_contributors',[62,nfreq],'u2'),('frequency_contributors',[62],'u1')]: add(stem+'.'+suffix,shape,kind)
    return out
