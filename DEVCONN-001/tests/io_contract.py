"""Bounded DEVCONN artifact IO, mechanically adapted from qualified PR198 IO.

Prior IO SHA256 ce5614b774fadebd58b557ec9a3bbf23fcaa4e9dc7a13a06b85275080086c78f.

Only artifact parsing; no source reconstruction, scientific estimator or masks.
Every file is parsed from authenticated immutable bytes, with descriptor/path
checks. Scientific field/type/axis checks belong to validator.py.
"""
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import stat
import zipfile

import numpy as np

FILES=('signal_evidence.npz','connectivity_metrics.csv','age_effects.json','run_metadata.json','findings.md')
MIB=1024**2
LIMIT=512*MIB
FILE_CAPS={'signal_evidence.npz':256*MIB,'connectivity_metrics.csv':MIB,
           'age_effects.json':MIB,'run_metadata.json':32*MIB,'findings.md':MIB}
MAX_FILES,MAX_DIRS,MAX_DEPTH=32,64,32
MAX_NPZ_MEMBERS,MAX_NPY_HEADER,MAX_JSON_DEPTH=40,65536,64
CSV_COLUMNS=('subject_id','age','group','mean_fd','n_active_rois',
             'short_range','long_range','segregation',
             'short_range_status','long_range_status','segregation_status',
             'short_range_n_nominal_edges','short_range_n_used_edges',
             'long_range_n_nominal_edges','long_range_n_used_edges')


def need(ok,message):
    if not ok: raise ValueError(message)


def safe_path(value):
    raw=os.fspath(value)
    need(type(raw) is str and raw.startswith('/') and '\0' not in raw,'absolute_path')
    need(not any(part in ('.','..') for part in raw.split('/')),'path_traversal')
    path=Path(raw)
    for node in (*reversed(path.parents),path):
        if os.path.lexists(node):
            mode=node.lstat().st_mode
            need(not stat.S_ISLNK(mode),'symlink_path')
            if node!=path: need(stat.S_ISDIR(mode),'non_directory_ancestor')
    return path


def signature(info):
    return info.st_dev,info.st_ino,info.st_mode,info.st_size,info.st_mtime_ns,info.st_ctime_ns


def read_bytes(path,limit=LIMIT,*,size=None,sha256=None):
    need(type(limit) is int and 0<=limit<=LIMIT,'read_bound')
    need(size is None or type(size) is int and 0<=size<=limit,'expected_size')
    need(sha256 is None or type(sha256) is str and re.fullmatch('[0-9a-f]{64}',sha256),'expected_sha')
    path=safe_path(path); before=path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_size<=limit,'regular_file_bound')
    need(size is None or size==before.st_size,'size_mismatch')
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as stream:
        need(signature(os.fstat(stream.fileno()))==signature(before),'file_replaced')
        raw=stream.read(before.st_size+1)
        need(len(raw)==before.st_size and signature(os.fstat(stream.fileno()))==signature(before),'file_changed')
        stream.seek(0); count=0; second=hashlib.sha256()
        while chunk:=stream.read(min(65536,before.st_size-count+1)):
            count+=len(chunk); need(count<=before.st_size,'file_changed'); second.update(chunk)
        need(count==len(raw) and second.digest()==hashlib.sha256(raw).digest()
             and signature(os.fstat(stream.fileno()))==signature(before),'file_changed')
    need(signature(path.lstat())==signature(before),'file_changed')
    if sha256 is not None: need(hashlib.sha256(raw).hexdigest()==sha256,'sha256_mismatch')
    return raw


def finite_tree(value,depth=0):
    need(depth<=MAX_JSON_DEPTH,'json_depth_bound')
    if type(value) is float: need(math.isfinite(value),'nonfinite_json')
    elif type(value) is dict:
        need(all(type(key) is str for key in value),'json_key_type')
        for child in value.values(): finite_tree(child,depth+1)
    elif type(value) is list:
        for child in value: finite_tree(child,depth+1)
    else: need(value is None or type(value) in (str,int,bool),'json_type')


def json_bytes(raw,limit=32*MIB):
    need(type(raw) is bytes and len(raw)<=limit,'json_byte_bound')
    def pairs(items):
        out={}
        for key,value in items:
            need(key not in out,'duplicate_json_key'); out[key]=value
        return out
    def bad(_): raise ValueError('nonfinite_json')
    try: out=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=pairs,parse_constant=bad)
    except RecursionError: raise ValueError('json_depth_bound') from None
    finite_tree(out); return out


def number(value,*,json_mode=False):
    need(not isinstance(value,(bool,np.bool_)),'boolean_number')
    if json_mode: need(type(value) in (int,float),'json_number_type')
    try: out=float(value)
    except (TypeError,ValueError,OverflowError): raise ValueError('numeric_token') from None
    need(math.isfinite(out),'nonfinite_number'); return out


def csv_bytes(raw,required=CSV_COLUMNS,max_rows=155):
    need(type(raw) is bytes and len(raw)<=MIB,'csv_byte_bound')
    text=raw.decode('utf-8-sig'); need('\0' not in text,'csv_nul')
    previous=csv.field_size_limit(MIB)
    try:
        parsed=csv.reader(io.StringIO(text,newline=''),strict=True)
        columns=next(parsed,None)
        need(columns and all(name.strip() for name in columns) and len(set(columns))==len(columns)
             and set(required)<=set(columns),'csv_header')
        rows=[]
        for cells in parsed:
            need(len(rows)<max_rows and len(cells)==len(columns),'csv_shape_bound')
            row=dict(zip(columns,cells))
            for key,value in row.items():
                if key not in required:
                    try: numeric=Decimal(value)
                    except InvalidOperation: continue
                    need(numeric.is_finite() and math.isfinite(float(numeric)),'nonfinite_csv_extra')
            rows.append(row)
        return rows
    except csv.Error: raise ValueError('csv_parse_or_field_bound') from None
    finally: csv.field_size_limit(previous)


def npz_bytes(raw):
    need(type(raw) is bytes and len(raw)<=FILE_CAPS['signal_evidence.npz'],'npz_byte_bound')
    result={}; expanded=0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members=archive.infolist()
        need(len(members)<=MAX_NPZ_MEMBERS and len({item.filename for item in members})==len(members),
             'npz_member_count_or_duplicate')
        for item in members:
            need(item.filename.endswith('.npy') and item.filename[:-4] not in ('','.','..')
                 and all(char not in item.orig_filename for char in ('/','\\','\0',':'))
                 and not item.is_dir() and not item.flag_bits&1,'npz_member_name')
            need(stat.S_IFMT(item.external_attr>>16) in (0,stat.S_IFREG),'npz_nonregular_member')
            need(item.compress_type in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED),'npz_compression')
            need(0<item.file_size<=LIMIT,'npz_member_bound')
            expanded+=item.file_size; need(expanded<=LIMIT,'npz_expanded_bound')
            with archive.open(item) as stream:
                version=np.lib.format.read_magic(stream)
                need(version in ((1,0),(2,0),(3,0)),'npy_version')
                shape,fort,dtype=np.lib.format._read_array_header(stream,version,max_header_size=MAX_NPY_HEADER)
                need(len(shape)<=32 and all(type(n) is int and n>=0 for n in shape) and type(fort) is bool
                     and dtype.kind in 'biufUS' and not dtype.hasobject and dtype.fields is None,'npy_dtype_shape')
                need(math.prod(shape)*dtype.itemsize+stream.tell()==item.file_size,'npy_claimed_size')
            value=np.load(io.BytesIO(archive.read(item)),allow_pickle=False,max_header_size=MAX_NPY_HEADER)
            if value.dtype.kind=='f': need(np.isfinite(value).all(),'npz_nonfinite')
            result[item.filename[:-4]]=value
    return result


def output_inventory(output):
    root=safe_path(output); need(root.is_dir(),'output_directory')
    need(not os.path.lexists(root/'failure_report.json'),'failed_run_marker')
    found={}; directories={}; total=0
    def walk(directory,depth):
        nonlocal total
        need(depth<=MAX_DEPTH,'directory_depth_bound')
        for path in directory.iterdir():
            relative=path.relative_to(root).as_posix(); info=path.lstat()
            if stat.S_ISDIR(info.st_mode):
                need(len(directories)<MAX_DIRS,'directory_count_bound')
                directories[relative]=signature(info); walk(path,depth+1)
            else:
                need(stat.S_ISREG(info.st_mode),'nonregular_output')
                need(len(found)<MAX_FILES,'file_count_bound')
                need(info.st_size<=FILE_CAPS.get(relative,LIMIT),'file_size_bound')
                total+=info.st_size; need(total<=LIMIT,'output_tree_bound')
                found[relative]=(path,signature(info))
    walk(root,0); need(set(FILES)<=set(found),'missing_output')
    return found,directories


def read_output(output):
    before,dirs=output_inventory(output); result={}
    for name in FILES:
        raw=read_bytes(before[name][0],FILE_CAPS[name])
        if name.endswith('.npz'): result[name]=npz_bytes(raw)
        elif name.endswith('.csv'): result[name]=csv_bytes(raw)
        elif name.endswith('.json'): result[name]=json_bytes(raw,FILE_CAPS[name])
        else:
            text=raw.decode('utf-8'); need(text.strip(),'empty_findings'); result[name]=text
    after,after_dirs=output_inventory(output)
    need(before==after and dirs==after_dirs,'output_changed')
    return result
