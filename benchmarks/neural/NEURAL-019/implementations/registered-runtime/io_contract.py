"""Bounded public-only arbitrary movement submission validation.

NPZ header/CRC preflight adapts the qualified NEURAL-018 scoring-v2 parser.
No candidate code, model, private-target loader or target-dependent threshold.
"""
from pathlib import Path
import hashlib, math, os, stat, zipfile
import numpy as np
FIELDS={'velocity','trial_ids','velocity_left_edges_ms','velocity_axes','velocity_units','panel_fingerprint'}
PUBLIC_FIELDS=FIELDS-{'velocity'}
MAX_BYTES=1048576


def require(ok,message):
    if not ok:raise ValueError(message)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb')as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()


def regular(path,cap=MAX_BYTES):
    p=Path(path).absolute();s=p.lstat()
    require(all(not q.is_symlink()for q in(p,*p.parents))and stat.S_ISREG(s.st_mode)and s.st_nlink==1 and 0<s.st_size<=cap,'Bounded unlinked regular file required')
    return p


def scalar(value):
    a=np.asarray(value);require(a.shape==()and a.dtype.kind=='U'and 0<a.dtype.itemsize<=256,'Bounded Unicode scalar required');return a.item()


def ids(value,n):
    a=np.asarray(value);require(a.shape==(n,)and a.dtype.kind=='U'and 0<a.dtype.itemsize<=256,'Bounded Unicode identities required')
    names=a.tolist();require(all(names)and len(set(names))==n,'Unique nonempty identities required');return names


def candidate_npz(path,n=126):
    require(type(n)is int and 1<=n<=126,'Invalid declared case geometry')
    shapes={'velocity.npy':(n,140,2),'trial_ids.npy':(n,),'velocity_left_edges_ms.npy':(140,),'velocity_axes.npy':(2,),'velocity_units.npy':(),'panel_fingerprint.npy':()}
    path=regular(path);before=path.stat()
    with path.open('rb')as source:
        opened=os.fstat(source.fileno());require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(opened.st_dev,opened.st_ino,opened.st_size,opened.st_mtime_ns)and opened.st_nlink==1,'Input changed before opening')
        with zipfile.ZipFile(source)as archive:
            rows=archive.infolist();require(len(rows)==len(shapes)and {r.filename for r in rows}==set(shapes),'Exact unique NPZ inventory required')
            require(sum(r.file_size for r in rows)<=MAX_BYTES,'Expanded archive cap')
            for row in rows:
                require(not row.is_dir()and stat.S_IFMT(row.external_attr>>16)in(0,stat.S_IFREG)and not row.flag_bits&1 and row.compress_type in(zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED),'Linked/encrypted/unsupported member')
                with archive.open(row)as member:
                    version=np.lib.format.read_magic(member);require(version in((1,0),(2,0)),'Supported NPY header required')
                    reader=np.lib.format.read_array_header_1_0 if version==(1,0)else np.lib.format.read_array_header_2_0
                    shape,order,dtype=reader(member,max_header_size=10000)
                    require(shape==shapes[row.filename]and type(order)is bool and not dtype.hasobject,'Exact shape, bool storage order, no objects')
                    if row.filename=='velocity.npy':require(dtype.kind=='f'and dtype.itemsize in(4,8),'Velocity float32/64 required')
                    elif row.filename=='velocity_left_edges_ms.npy':require(dtype.kind in'ifu'and dtype.itemsize<=8,'Bounded real clock required')
                    else:require(dtype.kind=='U'and 0<dtype.itemsize<=256,'Bounded Unicode metadata required')
                    remaining=math.prod(shape)*dtype.itemsize;require(member.tell()+remaining==row.file_size,'Exact NPY payload size required')
                    while remaining:
                        block=member.read(min(65536,remaining));require(bool(block),'Truncated array');remaining-=len(block)
                    require(member.read(1)==b'','Trailing array bytes')
        source.seek(0)
        with np.load(source,allow_pickle=False)as z:result={k:z[k]for k in z.files}
        after=os.fstat(source.fileno());require((opened.st_size,opened.st_mtime_ns,opened.st_ctime_ns,opened.st_nlink)==(after.st_size,after.st_mtime_ns,after.st_ctime_ns,after.st_nlink),'Input changed during validation')
    return result


def validate_candidate(candidate,public,n=126):
    require(set(candidate)==FIELDS and set(public)==PUBLIC_FIELDS,'Exact candidate/public fields required')
    require(scalar(candidate['velocity_units'])==scalar(public['velocity_units'])=='m/s','Exact physical m/s units')
    fingerprint=scalar(public['panel_fingerprint']);require(len(fingerprint)==64 and all(c in'0123456789abcdef'for c in fingerprint)and scalar(candidate['panel_fingerprint'])==fingerprint,'Exact panel fingerprint required')
    canonical=ids(public['trial_ids'],n);names=ids(candidate['trial_ids'],n);require(set(names)==set(canonical),'All exact assessment case identities required')
    for item in(candidate,public):
        require(np.array_equal(item['velocity_axes'],np.asarray(['x','y']))and np.asarray(item['velocity_axes']).dtype.kind=='U','Exact x,y axis order required')
        clock=np.asarray(item['velocity_left_edges_ms']);require(clock.dtype.kind in'ifu'and clock.dtype.itemsize<=8 and np.isfinite(clock).all()and np.array_equal(clock,np.arange(-150,550,5)),'Exact source-lagged140-bin clock required')
    velocity=np.asarray(candidate['velocity']);require(velocity.shape==(n,140,2)and velocity.dtype.kind=='f'and velocity.dtype.itemsize in(4,8)and np.isfinite(velocity).all(),'All finite signed float32/64 velocity predictions required')
    lookup={name:i for i,name in enumerate(names)}
    return velocity[[lookup[name]for name in canonical]].astype(np.float64,copy=False),{'status':'public_submission_valid','cases':n,'bins':140,'axes':['x','y'],'units':'m/s','trial_reordering':True,'clipping_or_fill':False,'target_loader_invocations':0}


def public_contract(packet):
    return {'trial_ids':packet['assessment_trial_ids'],'velocity_left_edges_ms':packet['velocity_left_edges_ms'],'velocity_axes':packet['velocity_axes'],'velocity_units':packet['velocity_units'],'panel_fingerprint':packet['panel_fingerprint']}


def bundle(prediction,public):return {'velocity':prediction,**public}
