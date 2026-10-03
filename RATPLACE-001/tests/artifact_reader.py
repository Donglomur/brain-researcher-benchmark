"""Bounded output parsing only: no source or scientific-module imports."""
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
import zipfile
import numpy as np

FILES=('spatial_information.csv','spatial_evidence.npz','results.json','run_metadata.json','findings.md')
COLUMNS=('unit_id','n_spikes','mean_rate_hz','raw_bits_per_spike','null_mean_bits_per_spike',
         'shift_adjusted_bits_per_spike','p_upper','status')
MEMBER=32*1024**2
TOTAL=128*1024**2

def need(ok,reason):
    if not ok:raise ValueError(reason)

def path(value):
    raw=os.fspath(value)
    need(isinstance(raw,str) and raw.startswith('/') and '\0' not in raw,'absolute_path')
    need(not any(p in ('.','..') for p in raw.split('/')),'path_traversal')
    result=Path(raw)
    for item in (*reversed(result.parents),result):
        if os.path.lexists(item):
            mode=item.lstat().st_mode
            need(not stat.S_ISLNK(mode),'symlink_path')
            if item!=result:need(stat.S_ISDIR(mode),'nondirectory_ancestor')
    return result

def identity(s):return s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns

def read_bytes(value,cap=MEMBER):
    p=path(value);before=p.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_size<=cap,'regular_file_bound')
    with os.fdopen(os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as f:
        need(identity(os.fstat(f.fileno()))==identity(before),'open_changed')
        raw=f.read(before.st_size+1)
        need(len(raw)==before.st_size and identity(os.fstat(f.fileno()))==identity(before)
             ==identity(p.lstat()),'file_changed')
    return raw

def inventory(value):
    root=path(value);need(root.is_dir(),'output_directory')
    need(not os.path.lexists(root/'failure_report.json'),'failure_marker')
    result={};total=0
    for item in root.iterdir():
        s=item.lstat()
        need(stat.S_ISREG(s.st_mode) and s.st_size<=MEMBER,'nonregular_or_oversized_output')
        total+=s.st_size;need(total<=TOTAL and len(result)<64,'output_total_bound')
        result[item.name]=identity(s)
    need(set(FILES)<=set(result),'missing_output')
    return result

def finite_tree(v):
    if isinstance(v,float):need(math.isfinite(v),'nonfinite_json')
    elif isinstance(v,dict):
        for x in v.values():finite_tree(x)
    elif isinstance(v,list):
        for x in v:finite_tree(x)

def json_bytes(raw):
    def pairs(items):
        out={}
        for k,v in items:
            need(k not in out,'duplicate_json_key');out[k]=v
        return out
    def invalid(_):raise ValueError('nonfinite_json')
    v=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=invalid)
    finite_tree(v);return v

def number(v,json_mode=False):
    need(not isinstance(v,(bool,np.bool_)),'boolean_number')
    if json_mode:need(type(v) in (int,float),'json_numeric_type')
    try:x=float(v)
    except (ValueError,TypeError,OverflowError):raise ValueError('numeric_token') from None
    need(math.isfinite(x),'finite_number');return x

def integer(v,json_mode=False):
    need(not isinstance(v,(bool,np.bool_)),'boolean_integer')
    if json_mode:need(type(v) is int,'json_integer_type')
    try:d=Decimal(str(v))
    except (ValueError,InvalidOperation):raise ValueError('integer_token') from None
    need(d.is_finite() and d==d.to_integral_value() and abs(d)<2**63,'integer_domain')
    return int(d)

def csv_bytes(raw):
    csv.field_size_limit(65536)
    r=csv.reader(io.StringIO(raw.decode('utf-8-sig'),newline=''))
    header=next(r,None)
    need(header and all(header) and len(set(header))==len(header)
         and set(COLUMNS)<=set(header) and len(header)<=128,'csv_header')
    rows=[]
    for cells in r:
        need(len(cells)==len(header) and len(rows)<110,'csv_shape')
        rows.append(dict(zip(header,cells)))
    return rows

def npz_bytes(raw):
    arrays={};expanded=0;elements=0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members=archive.infolist()
        need(len(members)<=64 and len({m.filename for m in members})==len(members),'npz_inventory')
        for member in members:
            name=member.filename
            need(name.endswith('.npy') and name[:-4] and '/' not in name and '\\' not in name
                 and not member.flag_bits&1,'npz_name')
            need(member.compress_type in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED),'npz_compression')
            expanded+=member.file_size;need(expanded<=TOTAL and member.file_size<=MEMBER,'npz_expanded_bound')
            with archive.open(member) as f:
                version=np.lib.format.read_magic(f)
                need(version in ((1,0),(2,0)),'npy_version')
                shape,fortran,dtype=np.lib.format._read_array_header(f,version,max_header_size=65536)
                need(len(shape)<=3 and dtype.kind in 'biufUS' and not dtype.hasobject
                     and dtype.fields is None,'npy_dtype_shape')
                count=math.prod(shape);elements+=count
                need(count<=16*1024**2 and elements<=32*1024**2,'npy_logical_elements')
                need(count*dtype.itemsize+f.tell()==member.file_size,'npy_size')
            arr=np.load(io.BytesIO(archive.read(member)),allow_pickle=False,max_header_size=65536)
            if arr.dtype.kind=='f':need(np.isfinite(arr).all(),'npz_nonfinite')
            arrays[name[:-4]]=arr
    return arrays

def read_output(value):
    root=path(value);before=inventory(root)
    raw={name:read_bytes(root/name) for name in FILES}
    need(inventory(root)==before,'output_changed')
    text=raw['findings.md'].decode('utf-8')
    need(bool(text.strip()) and '\0' not in text,'findings_text')
    return dict(rows=csv_bytes(raw['spatial_information.csv']),
                arrays=npz_bytes(raw['spatial_evidence.npz']),
                results=json_bytes(raw['results.json']),
                metadata=json_bytes(raw['run_metadata.json']),findings=text,
                _root=root,_inventory=before,
                _hashes={name:hashlib.sha256(v).hexdigest() for name,v in raw.items()})

def recheck(actual):
    root=actual['_root']
    need(inventory(root)==actual['_inventory'],'late_output_inventory')
    for name,want in actual['_hashes'].items():
        need(hashlib.sha256(read_bytes(root/name)).hexdigest()==want,'late_output_changed')

