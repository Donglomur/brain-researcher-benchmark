"""Strict, bounded trial-feature artifact boundary; never parses pickle."""
import hashlib
import io
from pathlib import Path
import re
import zipfile
import numpy as np
from core import need, PEOPLE,ROIS,FAMILIES,UNITS,VERSION,matched_indices
from io_utils import ordinary_bytes

CAP=24*1024*1024


def public_contract(d):
    need(type(d) is dict and set(d)=={'schema','people','unit_ids','source_design_sha256'}, 'Exact public manifest fields')
    need(type(d['source_design_sha256']) is str and re.fullmatch('[a-f0-9]{64}',d['source_design_sha256']), 'Source design fingerprint')
    need(d['schema']==VERSION and set(d['people'])==set(PEOPLE) and set(d['unit_ids'])==set(FAMILIES), 'Full fixed panel')
    all_ids=[]
    for person in PEOPLE:
        row=d['people'][person]
        need(type(row) is dict and set(row)=={'imagery_ids','perception_ids'}, 'Only blind condition IDs')
        for phase,n in [('imagery',500),('perception',1750)]:
            ids=row[phase+'_ids']
            need(type(ids) is list and len(ids)==n and len(set(ids))==n and all(type(x) is str and re.fullmatch(r'q[a-f0-9]{24}',x) for x in ids), 'Full unique opaque IDs')
            all_ids.extend(ids)
    need(len(set(all_ids))==len(all_ids), 'Globally unique trial IDs')
    for family in FAMILIES:
        u=d['unit_ids'][family]
        need(type(u) is list and len(u)==UNITS and all(type(x) is int and 0<=x<(1024 if family=='gist' else 1000) for x in u) and u==sorted(set(u)), 'Fixed ordered1000 feature indices')
        need(u==matched_indices(family,1024 if family=='gist' else 1000).tolist(),'Exact identity-only matched unit selection')
    return d


def part_keys():return [f'{p}/{r}/{f}' for p in PEOPLE for r in ROIS for f in FAMILIES]


def validate_submission(d):
    need(type(d) is dict and set(d)=={'schema','parts','source_design_sha256'} and d['schema']=='neural076_predictions_v1', 'Exact submission fields')
    need(type(d['source_design_sha256']) is str and re.fullmatch('[a-f0-9]{64}',d['source_design_sha256']), 'Submission source fingerprint')
    need(type(d['parts']) is list and len(d['parts'])==650, 'All650 fixed blocks required')
    paths=[]
    for row,key in zip(d['parts'],part_keys()):
        need(type(row) is dict and set(row)=={'key','path'} and row['key']==key, 'Canonical complete block order')
        need(type(row['path']) is str and re.fullmatch(r'[A-Za-z0-9_-]+\.npz',row['path']), 'Flat ordinary archive filename')
        paths.append(row['path'])
    need(len(set(paths))==650,'No aliased submission path')
    return d['parts']


def load(path,ids,unit_ids,expected_sha=None):
    body=ordinary_bytes(path,CAP);sha=hashlib.sha256(body).hexdigest()
    need(expected_sha is None or sha==expected_sha,'Submission changed after complete public validation')
    shapes={'trial_ids':(len(ids),),'unit_ids':(len(unit_ids),),'features':(len(ids),len(unit_ids))}
    with zipfile.ZipFile(io.BytesIO(body)) as z:
        entries=z.infolist()
        need(len(entries)==3 and {x.filename for x in entries}=={k+'.npy' for k in shapes},'Exact three NumPy members')
        need(sum(e.file_size for e in entries)<=CAP and all(e.compress_type in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED) and not e.flag_bits&1 for e in entries),'Bounded archive expansion')
        for e in entries:
            with z.open(e) as stream:
                version=np.lib.format.read_magic(stream)
                need(version in ((1,0),(2,0)), 'NPY version1/2 only')
                shape,fortran,dtype=(np.lib.format.read_array_header_1_0(stream,max_header_size=65536) if version==(1,0) else np.lib.format.read_array_header_2_0(stream,max_header_size=65536))
                name=e.filename[:-4]
                need(shape==shapes[name] and not fortran and not dtype.hasobject,'Exact C-order nonobject shape')
                if name=='features':need(dtype.kind=='f' and dtype.itemsize in (4,8),'Float32/64 predictions')
                elif name=='trial_ids':need(dtype==np.dtype('<U25'),'Fixed U25 trial IDs')
                else:need(dtype.kind in 'iu' and dtype.itemsize<=8,'Integer unit IDs')
                need(e.file_size==stream.tell()+int(np.prod(shape))*dtype.itemsize,'Exact NPY payload length')
        with np.load(io.BytesIO(body),allow_pickle=False) as f:
            need(f['trial_ids'].tolist()==ids and f['unit_ids'].tolist()==unit_ids,'Exact trial and unit alignment')
            a=f['features']
            need(np.isfinite(a).all(),'All feature predictions finite')
    return a,sha
