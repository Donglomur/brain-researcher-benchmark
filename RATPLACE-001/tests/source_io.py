"""Generic authenticated bytes/HDF5 guard; no scientific reconstruction."""
import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat

PINS={'source_manifest_sha256':'0bc1ef69627c18177f8a15c76bd8dbe003a6bdaf75ba33a9e0aaa5be652ab722',
      'method_contract_sha256':'c39f977f8a6d5c179107693d41c5312d37c00ce03a0ea2eebd0d00e3c4aa858a',
      'output_schema_sha256':'2a0ade879084d8e23b23fe62698718d048c663b414d1a36adf010f721b5e779b'}
FILENAMES=('source_manifest.json','method_contract.json','output_schema.json')
SOURCE_SHA='323e99a1ec1b028a35da8cd955f2671a1f9e1853b46622c19863424943c962db'
SOURCE_SIZE=61347328


def need(ok,reason):
    if not ok: raise ValueError(reason)
def sha(raw): return hashlib.sha256(raw).hexdigest()
def signature(s): return s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns


def safe_path(value):
    raw=os.fspath(value)
    need(raw.startswith('/') and '\0' not in raw and not any(p in ('.','..') for p in raw.split('/')),'unsafe_path')
    path=Path(raw)
    for p in (*reversed(path.parents),path):
        if os.path.lexists(p):
            info=p.lstat(); need(not stat.S_ISLNK(info.st_mode),'symlink_path')
            if p!=path: need(stat.S_ISDIR(info.st_mode),'nondirectory_ancestor')
    return path


def read_bytes(path,cap,*,digest=None,size=None):
    path=safe_path(path); before=path.lstat()
    need(stat.S_ISREG(before.st_mode) and 0<=before.st_size<=cap,'bounded_regular_file')
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as f:
        need(signature(os.fstat(f.fileno()))==signature(before),'open_changed')
        raw=f.read(cap+1)
        need(signature(os.fstat(f.fileno()))==signature(before)==signature(path.lstat()),'source_changed')
    need(len(raw)==before.st_size and (size is None or len(raw)==size),'byte_size')
    need(digest is None or sha(raw)==digest,'sha256')
    return raw


def strict_json(raw):
    def pairs(items):
        out={}
        for key,value in items:
            need(key not in out,'duplicate_json_key'); out[key]=value
        return out
    def bad(_): raise ValueError('nonfinite_json')
    result=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=bad)
    def finite(value):
        if isinstance(value,float):need(math.isfinite(value),'nonfinite_json')
        elif isinstance(value,dict):
            for item in value.values():finite(item)
        elif isinstance(value,list):
            for item in value:finite(item)
    finite(result)
    return result


def authenticate(data_dir='/app/data/ratplace',documents='/app',*,pins=PINS):
    root=safe_path(data_dir); docs=safe_path(documents)
    need(root.is_dir(),'data_directory')
    raws={}; parsed={}
    for filename,key in zip(FILENAMES,PINS):
        need(isinstance(pins.get(key),str) and len(pins[key])==64,'unfrozen_document_pin')
        raws[filename]=read_bytes(docs/filename,1024**2,digest=pins[key])
        parsed[filename]=strict_json(raws[filename])
    manifest=parsed['source_manifest.json']
    need(manifest['task_id']=='RATPLACE-001' and manifest['schema_version']=='ratplace-source-v2','source_schema')
    need(len(manifest['files'])==1,'source_inventory')
    row=manifest['files'][0]; name=row['path']
    need(isinstance(name,str) and name==Path(name).name and name not in ('','.','..'),'source_filename')
    need(row['sha256']==SOURCE_SHA and row['size_bytes']==SOURCE_SIZE,'source_public_identity')
    expected={name,'source_manifest.json'}
    need(set(p.name for p in root.iterdir())==expected,'closed_source_inventory')
    need(read_bytes(root/'source_manifest.json',1024**2)==raws['source_manifest.json'],'internal_manifest')
    raw=read_bytes(root/name,64*1024**2,digest=row['sha256'],size=row['size_bytes'])
    return dict(raw=raw,root=root,documents=docs,manifest=manifest,method=parsed['method_contract.json'],
                schema=parsed['output_schema.json'],pins=dict(pins),document_bytes=raws)


def recheck(context):
    other=authenticate(context['root'],context['documents'],pins=context['pins'])
    need(other['raw']==context['raw'] and other['document_bytes']==context['document_bytes'],'late_source_change')


def open_h5(raw):
    import h5py
    need(h5py.__version__=='3.16.0','h5py_version')
    f=h5py.File(io.BytesIO(raw),'r')
    try:
        seen=set(); count=0
        def visit(obj):
            nonlocal count
            address=h5py.h5o.get_info(obj.id).addr
            if address in seen:return
            seen.add(address); count+=1; need(count<=4096,'hdf5_object_cap')
            if isinstance(obj,h5py.Dataset):
                need(not obj.is_virtual and not obj.external,'external_dataset')
                props=obj.id.get_create_plist()
                need(all(props.get_filter(i)[0] in (1,2,3) for i in range(props.get_nfilters())),'unreviewed_filter')
            else:
                for name in obj:
                    link=obj.get(name,getlink=True)
                    need(not isinstance(link,h5py.ExternalLink),'external_link')
                    if isinstance(link,h5py.HardLink):visit(obj[name])
        visit(f)
        return f
    except BaseException:
        f.close(); raise


def direct(f,path):
    import h5py
    current=f
    for part in path.strip('/').split('/'):
        need(isinstance(current.get(part,getlink=True),h5py.HardLink),'selected_nondirect_link')
        current=current[part]
    need(isinstance(current,h5py.Dataset),'selected_dataset')
    return current


def text(value):
    if isinstance(value,bytes):value=value.decode('utf-8','strict')
    need(isinstance(value,str) and '\0' not in value and len(value.encode())<=65536,'text_value')
    return value
