"""Strict, captured, stdlib-only admission of a fixed embedding artifact roster."""
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import struct

MAX_FILE_BYTES=20_000_000
MAX_ARTIFACT_BYTES=40_000_000
METHODS=('candidate','marble','cebra-time','cebra-behavior')


def signature(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)


def captured_at(directory_fd,name,limit):
    if type(name)!=str or Path(name).name!=name or name in ('','.','..'):
        raise ValueError('flat exact filenames only')
    fd=os.open(name,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW,dir_fd=directory_fd)
    with os.fdopen(fd,'rb') as file:
        before=os.fstat(file.fileno())
        if not stat.S_ISREG(before.st_mode) or not 0<=before.st_size<=limit:
            raise ValueError('bounded regular file required')
        raw=file.read(limit+1)
        if len(raw)>limit or len(raw)!=before.st_size or signature(before)!=signature(os.fstat(file.fileno())):
            raise ValueError('changed or oversized file')
    return raw,hashlib.sha256(raw).hexdigest()


def no_duplicates(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('duplicate JSON key')
        result[key]=value
    return result


def parse_json(raw):
    return json.loads(raw.decode('utf-8'),object_pairs_hook=no_duplicates,
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite JSON')))


def npy_header(raw,shape):
    if len(raw)<10 or raw[:6]!=b'\x93NUMPY' or raw[6:8] not in (b'\x01\x00',b'\x02\x00'):
        raise ValueError('NPY v1/v2 required')
    width=2 if raw[6]==1 else 4;start=8+width
    if len(raw)<start:raise ValueError('truncated NPY header length')
    length=int.from_bytes(raw[8:start],'little')
    if not 1<=length<=4096 or start+length>len(raw):raise ValueError('bounded NPY header')
    try:
        node=ast.parse(raw[start:start+length].decode('latin1').strip(),mode='eval').body
        if not isinstance(node,ast.Dict) or len(node.keys)!=3:raise ValueError('exact header keys')
        keys=[ast.literal_eval(key) for key in node.keys]
        if len(set(keys))!=3:raise ValueError('duplicate NPY header key')
        header=ast.literal_eval(node)
    except (SyntaxError,ValueError,UnicodeError,TypeError) as error:raise ValueError('NPY literal header') from error
    if type(header)!=dict or set(header)!={'descr','fortran_order','shape'} or header['descr'] not in ('<f4','<f8') or header['fortran_order'] is not False:
        raise ValueError('little-endian float32/64 C-order required')
    if type(header['shape'])!=tuple or any(type(n)!=int for n in header['shape']) or header['shape']!=tuple(shape):
        raise ValueError('exact embedding shape required')
    offset=start+length;itemsize=int(header['descr'][-1])
    if len(raw)!=offset+math.prod(shape)*itemsize:raise ValueError('exact payload extent required')
    unpack='<f' if itemsize==4 else '<d'
    for (value,) in struct.iter_unpack(unpack,memoryview(raw)[offset:]):
        if not math.isfinite(value):raise ValueError('nonfinite embedding')
    return {'dtype':header['descr'],'shape':shape,'offset':offset}


def shapes(spec):
    return {f'{condition}-{row["rat"]}-{split}-d{dim}.npy':(row[f'{split}_rows'],dim)
        for condition in spec['conditions'] for row in spec['rats'] for split in spec['splits'] for dim in spec['embedding_dimensions']}


def admit(root,spec,access_view,method):
    if access_view not in ('A','B') or method not in METHODS:raise ValueError('operator context')
    directory_fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        expected=shapes(spec)
        if set(os.listdir(directory_fd))!=set(expected)|{'submission.json'}:raise ValueError('exact artifact file roster')
        raw,digest=captured_at(directory_fd,'submission.json',16384);document=parse_json(raw)
        if type(document)!=dict or set(document)!={'schema','protocol_id','access_view','method','method_name'}:
            raise ValueError('exact submission metadata keys')
        if document['schema']!='marble_embedding_submission_v1' or document['protocol_id']!=spec['protocol_id'] or document['access_view']!=access_view or document['method']!=method:
            raise ValueError('artifact protocol/view/method mismatch')
        if type(document['method_name'])!=str or not 1<=len(document['method_name'])<=160:raise ValueError('method name')
        files={};pins={'submission.json':digest};total=len(raw)
        for name,shape in expected.items():
            raw,digest=captured_at(directory_fd,name,MAX_FILE_BYTES);total+=len(raw)
            if total>MAX_ARTIFACT_BYTES:raise ValueError('total artifact budget')
            header=npy_header(raw,shape);files[name]=(raw,header);pins[name]=digest
        return document,files,pins
    finally:os.close(directory_fd)
