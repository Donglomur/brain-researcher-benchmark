"""Deferred full native reader. No native import or file open at module import."""
from contextlib import contextmanager
import hashlib
import io
import os
import stat
from owner.io import Artifact, ContractError, identity, ordinary
from .algorithm import combine, validate_clock


class MeteredFile(io.BufferedIOBase):
    def __init__(self, stream, meter, size):
        self.stream, self.meter, self.size = stream, meter, size
    def readable(self): return True
    def seekable(self): return True
    def writable(self): return False
    def tell(self): return self.stream.tell()
    def seek(self, offset, whence=0): return self.stream.seek(offset,whence)
    def read(self, size=-1):
        remaining = max(0, self.size-self.tell())
        count = remaining if size < 0 else min(size,remaining)
        self.meter.read(count)
        body = self.stream.read(count)
        if len(body) != count: raise ContractError('short authenticated native read')
        return body
    def readinto(self, buffer):
        body = self.read(len(buffer)); buffer[:len(body)] = body; return len(body)
    def flush(self): return None


@contextmanager
def authenticated(ctx, descriptor, expected_blake):
    ctx.require_scientific()
    ref = descriptor if isinstance(descriptor, Artifact) else Artifact.parse(descriptor)
    if ref.role != 'native_source' or ref.visibility != 'operator':
        raise ContractError('operator native-source descriptor required')
    path = ordinary(ref.path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size != ref.bytes or before.st_nlink != 1 or before.st_mode & 0o222:
            raise ContractError('native object must be ordinary, immutable and exact sized')
        sha, blake, remaining = hashlib.sha256(), hashlib.blake2b(), ref.bytes
        while remaining:
            count = min(8*1024*1024, remaining); ctx.store.meter.read(count)
            body = stream.read(count)
            if len(body) != count: raise ContractError('short source authentication')
            sha.update(body); blake.update(body); remaining -= count
        if stream.read(1) or sha.hexdigest() != ref.sha256 or blake.hexdigest() != expected_blake:
            raise ContractError('same-FD full source checksum mismatch')
        if identity(before) != identity(os.fstat(fd)):
            raise ContractError('source changed during authentication')
        stream.seek(0)
        try:
            yield MeteredFile(stream, ctx.store.meter, ref.bytes)
        finally:
            if identity(before) != identity(os.fstat(fd)):
                raise ContractError('source changed during native consumption')


@contextmanager
def opened(ctx, descriptor, expected_blake):
    ctx.require_scientific()
    import h5py  # deferred until signed native stage authorization
    with authenticated(ctx,descriptor,expected_blake) as stream:
        with h5py.File(stream,'r') as file:
            yield file


def internal(file,path):
    import h5py
    obj = file
    for part in path.strip('/').split('/'):
        if not isinstance(obj,h5py.Group) or not isinstance(obj.get(part,getlink=True),h5py.HardLink):
            raise ContractError('missing/soft/external native link')
        obj = obj[part]
    if isinstance(obj,h5py.Dataset) and (obj.is_virtual or obj.external):
        raise ContractError('virtual/external native dataset')
    return obj


def vector(file,path,length=None,kind=None,cap=2_000_000):
    import h5py
    ds = internal(file,path)
    if (not isinstance(ds,h5py.Dataset) or ds.ndim != 1 or len(ds)>cap
            or (length is not None and len(ds)!=length) or (kind and ds.dtype.kind not in kind)):
        raise ContractError('unsupported complete metadata vector: '+path)
    return ds[:].tolist()


def neural_metadata(file,row):
    import h5py
    prefix='processing/ophys/dff/traces/'
    table_path='processing/ophys/image_segmentation/cell_specimen_table'
    ds=internal(file,prefix+'data')
    if not isinstance(ds,h5py.Dataset) or ds.ndim!=2 or ds.dtype.kind!='f' or not 0<ds.shape[0]<=2_000_000 or not 0<ds.shape[1]<=20_000:
        raise ContractError('unsupported full time by ROI native dF/F shape')
    if ds.attrs.get('unit') not in ('NA',b'NA') or float(ds.attrs.get('conversion',1))!=1 or float(ds.attrs.get('offset',0))!=0:
        raise ContractError('unqualified native dF/F unit/conversion/offset')
    clock=vector(file,prefix+'timestamps',ds.shape[0],'f')
    if internal(file,prefix+'timestamps').attrs.get('unit') not in ('seconds',b'seconds'):
        raise ContractError('native clock unit must be seconds')
    validate_clock(clock)
    region_ds=internal(file,prefix+'rois')
    if region_ds.attrs.get('neurodata_type') not in ('DynamicTableRegion',b'DynamicTableRegion'):
        raise ContractError('explicit DynamicTableRegion required')
    region=vector(file,prefix+'rois',ds.shape[1],'iu',20_000)
    table=internal(file,table_path); reference=region_ds.attrs.get('table')
    if reference is None or not reference or file[reference].id!=table.id:
        raise ContractError('ROI region must reference exact native ROI table')
    ids=vector(file,table_path+'/id',kind='iu',cap=20_000)
    specimen=vector(file,table_path+'/cell_specimen_id',len(ids),'iuf',20_000)
    valid=vector(file,table_path+'/valid_roi',len(ids),'b',20_000)
    if len(set(ids))!=len(ids) or len(set(region))!=len(region) or any(i<0 or i>=len(ids) for i in region):
        raise ContractError('invalid native region identity/index mapping')
    expected={int(r['cell_roi_id']):int(r['cell_specimen_id']) for r in row['rois']}
    # Valid ROI in the table but absent from the fluorescence region is a
    # missing published cell, not permission to narrow the population.
    actual={ids[i] for i in range(len(ids)) if valid[i]}
    represented={ids[i] for i in region if valid[i]}
    if not expected or actual!=set(expected) or represented!=set(expected):
        raise ContractError('full published valid ROI census differs from table/region')
    mapped={ids[index]:(column,index) for column,index in enumerate(region)}
    columns=[]; joins=[]
    for rid,cid in sorted(expected.items()):
        column,index=mapped[rid]
        if specimen[index]!=cid:
            raise ContractError('native published ROI/specimen lineage mismatch')
        columns.append(column); joins.append({'cell_roi_id':str(rid),'cell_specimen_id':str(cid),'column':column,'table_index':index})
    return ds,{'shape':list(ds.shape),'dtype':str(ds.dtype),'unit':'NA','conversion':1,'offset':0,
               'clock_unit':'seconds','clock':clock,'columns':columns,'roi_joins':joins,
               'roi_table_rows':len(ids),'valid_roi_count':len(columns),'region_table_path':table_path}


def presentations(file):
    import h5py
    root=internal(file,'intervals'); tables=[]; required={'id','start_time','image_name','omitted'}
    if not isinstance(root,h5py.Group): raise ContractError('native intervals group absent')
    for name in sorted(root.keys()):
        group=internal(file,'intervals/'+name)
        if not isinstance(group,h5py.Group): continue
        keys=set(group.keys())
        if not {'image_name','omitted'} & keys: continue
        if not required<=keys: raise ContractError('incomplete native image/omission presentation table')
        base='intervals/'+name+'/'
        ids=vector(file,base+'id',kind='iu',cap=200_000)
        starts=vector(file,base+'start_time',len(ids),'f',200_000)
        omitted=vector(file,base+'omitted',len(ids),'bif',200_000)
        names_ds=internal(file,base+'image_name')
        if not isinstance(names_ds,h5py.Dataset) or names_ds.ndim!=1 or len(names_ds)!=len(ids) or h5py.check_string_dtype(names_ds.dtype) is None:
            raise ContractError('native image-name vector schema mismatch')
        tables.append({'group':name,'ids':ids,'starts':starts,'omitted':omitted,'image_names':names_ds.asstr()[:].tolist()})
    return combine(tables)
