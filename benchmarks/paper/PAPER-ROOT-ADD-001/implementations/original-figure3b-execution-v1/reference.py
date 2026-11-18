"""Read the fixed accepted author-result receipt; no source-array recomputation.

Its42 saved observations retain their row-major session/lag order. This is an
attributed released-result comparator, not authenticated baseline reexecution.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import os
import stat
import sys
import types

HERE=Path(__file__).resolve().parent
ENDPOINT_SHA='bbf81e3f3f8a82edfbeb8005de6b52d335e21d674e3798238a5f8a14555c3afa'
REFERENCE_SHA='d822f284c2d781f920841705a63fec38d3267ee5c62e5dd5635272cf087e49c9'
REFERENCE_BYTES=485111
CENSUS_SHA='3d2d46bbc6534b282f97d29c51b1961c8d284cf7a9894839fb851550b7549e37'
path=HERE.parent/'original-figure3b-improvement-v1/improvement.py'
if any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('No endpoint source symlink')
fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
with os.fdopen(fd,'rb') as stream:
    before=os.fstat(stream.fileno())
    if not (stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<before.st_size<=32768):
        raise ValueError('Bounded ordinary endpoint source before allocation')
    raw=stream.read(before.st_size+1)
    identity=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    if not (len(raw)==before.st_size and hashlib.sha256(raw).hexdigest()==ENDPOINT_SHA
            and identity(before)==identity(os.fstat(stream.fileno()))==identity(path.lstat())):
        raise ValueError('Exact stable reviewed endpoint source')
name='_language_selected_reference_endpoint'
endpoint=types.ModuleType(name);endpoint.__file__,endpoint.__package__=str(path),''
sys.modules[name]=endpoint
try:exec(compile(raw,str(path),'exec',dont_inherit=True),endpoint.__dict__)
except BaseException:
    sys.modules.pop(name,None)
    raise
need=endpoint.need


def parse(raw):
    def pairs(items):
        out={}
        for key,value in items:
            need(key not in out,'Duplicate saved-reference key');out[key]=value
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'Nonfinite saved reference'))


def _packet_from_saved_reference(value):
    """Pure private shape/order adapter; caller must authenticate fixed raw bytes."""
    need(type(value) is dict and value.get('schema')=='language_original_figure3_reduction_v1'
         and value.get('sessions')==list(endpoint.SESSIONS) and value.get('participants')==8
         and value.get('released_fr_matrix_unit_columns')==567,'Exact saved source cohort')
    observations=value.get('source_permutation_observations',{}).get('population')
    need(type(observations) is list and len(observations)==42,'All42 saved source lag observations, no synthesis from rounded means')
    packet={'schema':'language-original-figure3b-scores/v1','role':'provided_author_reference',
        'selection_sha256':hashlib.sha256(endpoint.encoded(endpoint.selection())).hexdigest(),
        'source_support_sha256':CENSUS_SHA,'prediction_run_sha256':REFERENCE_SHA,
        'scores':[{'context':c,'pearson_r':r} for c,r in zip(endpoint.contexts(),observations)],
        'execution_qualified':False}
    endpoint._packet(packet,'provided_author_reference')
    return packet


def packet_from_bytes(raw):
    need(type(raw) is bytes and len(raw)==REFERENCE_BYTES and hashlib.sha256(raw).hexdigest()==REFERENCE_SHA,
         'Exact accepted complete author-reference receipt before parsing')
    return _packet_from_saved_reference(parse(raw))


def load(path):
    path=Path(path).absolute()
    need(not any(p.is_symlink() for p in (path,*path.parents)),'No reference path symlink')
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
    with os.fdopen(fd,'rb') as stream:
        before=os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==REFERENCE_BYTES,
             'Fixed ordinary reference receipt extent before read')
        raw=stream.read(REFERENCE_BYTES+1)
        identity=lambda x:(x.st_dev,x.st_ino,x.st_mode,x.st_nlink,x.st_size,x.st_mtime_ns,x.st_ctime_ns)
        need(identity(before)==identity(os.fstat(stream.fileno()))==identity(path.lstat()),'Stable saved reference')
    return packet_from_bytes(raw)
