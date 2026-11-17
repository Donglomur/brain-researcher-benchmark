"""Lossless bounded transport for complete non-executable JSON metadata.

Chunking changes transport only. Original canonical byte count/order/hash are
validated before decoding; scientific result records remain separately typed.
"""
from __future__ import annotations
import hashlib
import json
from .common import require,FRAME_LIMIT,decode_any
from .collection import Records

def put_object(store,prefix,value,*,producer,role='sealed_object_chunk'):
    encoder=json.JSONEncoder(sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
    rows=Records(store,prefix+'/index','sealed_object_member',producer)
    buffer=bytearray();sha=hashlib.sha256();total=0;ordinal=0
    def flush():
        nonlocal buffer,total,ordinal
        if not buffer:return
        body=bytes(buffer);sha.update(body);total+=len(body)
        desc=store.write(f'{prefix}/chunk-{ordinal:08d}.bin',body,role=role,
                         producer=producer,media_type='application/octet-stream')
        rows.append({'ordinal':ordinal,'descriptor':desc});ordinal+=1;buffer.clear()
    for text in encoder.iterencode(value):
        store.meter.checkpoint('metadata_object_encoding')
        piece=text.encode('utf-8');offset=0
        while offset<len(piece):
            amount=min(FRAME_LIMIT-len(buffer),len(piece)-offset)
            buffer.extend(piece[offset:offset+amount]);offset+=amount
            if len(buffer)==FRAME_LIMIT:flush()
    flush()
    return {'schema':'finite_object_ref_v1','chunks':rows.seal(),'bytes':total,
            'sha256':sha.hexdigest(),'role':role,'encoding':'canonical-json-utf8'}

def get_object(store,ref,*,allowed_roles,max_bytes):
    require(ref['schema']=='finite_object_ref_v1' and ref['role'] in allowed_roles,
            'WRONG_OBJECT_ROLE')
    require(0<=ref['bytes']<=max_bytes,'OBJECT_EXCEEDS_SELECTED_CAPACITY')
    result=bytearray();sha=hashlib.sha256();ordinal=0
    for row in Records.iterate(store,ref['chunks']):
        require(row['ordinal']==ordinal,'OBJECT_CHUNK_ORDER_CHANGED');ordinal+=1
        desc=row['descriptor'];require(desc['bytes']<=FRAME_LIMIT,'OVERSIZED_OBJECT_CHUNK')
        body=store.read(desc,allowed_roles);require(len(result)+len(body)<=ref['bytes'],'EXTRA_OBJECT_BYTES')
        sha.update(body);result.extend(body)
    require(len(result)==ref['bytes'] and sha.hexdigest()==ref['sha256'],'OBJECT_INVERSE_MISMATCH')
    store.meter.checkpoint('before_metadata_object_decode')
    return decode_any(bytes(result),max_bytes)

def object_descriptors(store,ref):
    """Exact whole object exposure list; only explicitly own/public objects use it."""
    out=[]
    def walk(desc):
        out.append(desc);value=store.json(desc,{'sealed_record_index'})
        for member in value['members']:
            if value['depth']:walk(member)
            else:out.append(member)
    walk(ref['chunks']['root'])
    out.extend(row['descriptor'] for row in Records.iterate(store,ref['chunks']))
    return out
