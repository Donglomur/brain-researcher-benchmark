"""Generic bounded N170 artifact IO; no scientific estimator or mask policy.

Adapted from reviewed PR185 io_contract.py SHA256
b263b8a176a51a2db2cafa74beab9e44895a4ae94d24b6263a5102d4b3e82db2.
Optional flat regular files, CSV columns, JSON keys and NPZ arrays are accepted
within the declared limits; floats remain finite even under false masks.
"""
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
import re
import zipfile
import numpy as np

FILES = ('annotations.csv','trials.csv','erp_evidence.npz','per_subject.csv',
         'n170.json','run_metadata.json','findings.md')
LIMIT = 32 * 1024**2
AGGREGATE_LIMIT = 128 * 1024**2
MAX_OUTPUT_FILES, MAX_NPZ_MEMBERS = 128, 32
MAX_NPY_HEADER, MAX_CSV_FIELD, MAX_JSON_DEPTH = 65536, 1024**2, 64


def need(ok, message):
    if not ok: raise ValueError(message)


def safe_path(value):
    raw = os.fspath(value)
    need(isinstance(raw,str) and raw.startswith('/') and '\0' not in raw, 'absolute_path')
    need(not any(x in ('.','..') for x in raw.split('/')), 'path_traversal')
    p = Path(raw)
    for q in (*reversed(p.parents),p):
        if os.path.lexists(q):
            mode=q.lstat().st_mode
            need(not stat.S_ISLNK(mode),'symlink_path')
            if q!=p:need(stat.S_ISDIR(mode),'non_directory_ancestor')
    return p


def read_bytes(path, limit=LIMIT, size=None, sha256=None):
    need(type(limit) is int and 0 <= limit <= LIMIT,'invalid_read_bound')
    need(size is None or type(size) is int and 0 <= size <= limit,'invalid_expected_size')
    need(sha256 is None or type(sha256) is str and re.fullmatch('[0-9a-f]{64}',sha256),'invalid_expected_sha')
    p=safe_path(path); before=p.lstat()
    identity=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    need(stat.S_ISREG(before.st_mode) and before.st_size<=limit,'regular_file_bound')
    need(size is None or before.st_size==size,'size_mismatch')
    with os.fdopen(os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as f:
        need(identity(os.fstat(f.fileno()))==identity(before),'file_replaced')
        raw=f.read(before.st_size+1)
        need(len(raw)==before.st_size and identity(os.fstat(f.fileno()))==identity(before),'file_changed')
        # Detect same-size changes even if a filesystem timestamp has coarse precision.
        f.seek(0); check=hashlib.sha256(); count=0
        while chunk:=f.read(min(65536,before.st_size-count+1)):
            count+=len(chunk);need(count<=before.st_size,'file_changed');check.update(chunk)
        need(count==len(raw) and check.digest()==hashlib.sha256(raw).digest()
             and identity(os.fstat(f.fileno()))==identity(before),'file_changed')
    need(identity(p.lstat())==identity(before),'file_changed')
    if sha256 is not None:need(hashlib.sha256(raw).hexdigest()==sha256,'sha256_mismatch')
    return raw


def finite_tree(v, depth=0):
    need(depth<=MAX_JSON_DEPTH,'json_depth_bound')
    if isinstance(v,float):need(math.isfinite(v),'nonfinite_json')
    elif isinstance(v,dict):
        for x in v.values():finite_tree(x,depth+1)
    elif isinstance(v,list):
        for x in v:finite_tree(x,depth+1)


def json_bytes(raw):
    def pairs(items):
        d={}
        for k,v in items:need(k not in d,'duplicate_json_key');d[k]=v
        return d
    def invalid(_):raise ValueError('nonfinite_json')
    need(isinstance(raw,bytes) and len(raw)<=LIMIT,'json_byte_bound')
    try:out=json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid)
    except RecursionError:raise ValueError('json_depth_bound') from None
    finite_tree(out);return out


def integer(v):
    need(not isinstance(v,(bool,np.bool_)),'boolean_integer')
    try:d=Decimal(str(v))
    except (InvalidOperation,ValueError):raise ValueError('integer_token') from None
    need(d.is_finite() and d==d.to_integral_value() and -2**63<=d<2**63,'integer_domain')
    return int(d)


def number(v, json_mode=False):
    need(not isinstance(v,(bool,np.bool_)),'boolean_number')
    if json_mode:need(type(v) in (int,float),'json_number_type')
    try:x=float(v)
    except (ValueError,TypeError,OverflowError):raise ValueError('numeric_token') from None
    need(math.isfinite(x),'finite_number');return x


def boolean(v):
    if isinstance(v,bool):return v
    need(isinstance(v,str) and v.lower() in ('0','1','true','false'),'boolean_token')
    return v.lower() in ('1','true')


def exact_json(observed, expected):
    if expected is None:need(observed is None,'json_null')
    elif type(expected) is bool:need(type(observed) is bool and observed==expected,'json_bool')
    elif type(expected) is int:
        need(type(observed) in (int,float) and integer(observed)==expected,'json_exact_integer')
    elif type(expected) is float:
        need(number(observed,True)==expected,'json_exact_number')
    elif isinstance(expected,str):need(type(observed) is str and observed==expected,'json_string')
    elif isinstance(expected,list):
        need(isinstance(observed,list) and len(observed)==len(expected),'json_list')
        for a,b in zip(observed,expected):exact_json(a,b)
    elif isinstance(expected,dict):
        need(isinstance(observed,dict) and set(expected)<=set(observed),'json_fields')
        for k,v in expected.items():exact_json(observed[k],v)
    else:raise ValueError('internal_json_type')


def close(a,b,atol=1e-8,rtol=1e-6):
    a=np.asarray(a,dtype=np.float64);b=np.asarray(b,dtype=np.float64)
    need(a.shape==b.shape and np.isfinite(a).all() and np.isfinite(b).all(),'finite_shape')
    need(np.all(np.abs(a-b)<=atol+rtol*np.abs(b)),'numeric_tolerance')


def output_files(path):
    p=safe_path(path);need(p.is_dir(),'output_directory')
    need(not os.path.lexists(p/'failure_report.json'),'failed_run_marker')
    got={};total=0
    for f in p.iterdir():
        info=f.lstat()
        need(stat.S_ISREG(info.st_mode),'nonregular_output')
        need(info.st_size<=LIMIT,'output_file_bound')
        total+=info.st_size;need(total<=AGGREGATE_LIMIT,'aggregate_output_bound')
        need(len(got)<MAX_OUTPUT_FILES,'output_file_count_bound')
        got[f.name]=f
    need(set(FILES)<=set(got),'missing_output')
    return got


def csv_read(path, required, max_rows):
    need(type(max_rows) is int and max_rows>=0,'csv_row_bound')
    need(isinstance(required,(list,tuple,set,frozenset)) and all(type(k) is str and k for k in required)
         and len(required)==len(set(required)),'csv_required_fields')
    raw=read_bytes(path); previous=csv.field_size_limit(MAX_CSV_FIELD)
    try:
        reader=csv.reader(io.StringIO(raw.decode('utf-8-sig'),newline=''),strict=True)
        header=next(reader,None)
        need(header and all(h.strip() for h in header) and len(set(header))==len(header)
             and set(required)<=set(header),'csv_header')
        rows=[]
        for cells in reader:
            need(len(cells)==len(header) and len(rows)<max_rows,'csv_shape_bound')
            row=dict(zip(header,cells))
            for key,val in row.items():
                if key not in required:
                    try:d=Decimal(val)
                    except InvalidOperation:continue
                    need(d.is_finite(),'nonfinite_csv_extra')
            rows.append(row)
        return rows
    except csv.Error:raise ValueError('csv_parse_or_field_bound') from None
    finally:csv.field_size_limit(previous)


def npz_read(path):
    raw=read_bytes(path)
    arrays={};expanded=0
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        members=z.infolist()
        need(len(members)<=MAX_NPZ_MEMBERS and len({m.filename for m in members})==len(members),'npz_member_count_or_duplicate')
        for m in members:
            need(m.filename.endswith('.npy') and m.filename[:-4] not in ('','.','..')
                 and all(c not in m.orig_filename for c in ('/','\\','\0',':'))
                 and not m.is_dir() and not m.flag_bits&1,'npz_member_name')
            need(stat.S_IFMT(m.external_attr>>16) in (0,stat.S_IFREG),'npz_nonregular_member')
            need(m.compress_type in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED),'npz_compression')
            need(0<m.file_size<=LIMIT,'npz_member_bound')
            expanded+=m.file_size;need(expanded<=AGGREGATE_LIMIT,'npz_expanded_bound')
            with z.open(m) as f:
                version=np.lib.format.read_magic(f)
                need(version in ((1,0),(2,0),(3,0)),'npy_version')
                shape,fort,dtype=np.lib.format._read_array_header(f,version,max_header_size=MAX_NPY_HEADER)
                need(len(shape)<=3 and all(type(n) is int and n>=0 for n in shape)
                     and type(fort) is bool and dtype.kind in 'biufUS' and not dtype.hasobject,'npy_dtype_shape')
                need(math.prod(shape)*dtype.itemsize+f.tell()==m.file_size,'npy_claimed_size')
            value=np.load(io.BytesIO(z.read(m)),allow_pickle=False,max_header_size=MAX_NPY_HEADER)
            if value.dtype.kind in 'f':need(np.isfinite(value).all(),'npz_nonfinite')
            arrays[m.filename[:-4]]=value
    return arrays


def key_rows(rows, keys):
    # Callers explicitly normalize typed keys first; this layer invents no aliases.
    need(isinstance(keys,(list,tuple)) and keys and len(keys)==len(set(keys)),'row_key_fields')
    result={}
    for row in rows:
        need(isinstance(row,dict) and all(k in row for k in keys),'missing_row_key')
        key=tuple(row[k] for k in keys)
        need(key not in result,'duplicate_scientific_key');result[key]=row
    return result
