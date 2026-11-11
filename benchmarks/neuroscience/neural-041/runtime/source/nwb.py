"""Same-open authenticated NWB reads, bounded slices and explicit native custody.

HDF5 internal allocations/IO are not fully visible to this logical meter. The
selected external native host memory/CPU and source-format qualifications remain
required. No HDF5/numerical import or original input read occurs at import.
"""
import hashlib
import math
import os
import stat
from pathlib import Path
from core import need,integer,finite,descriptor,parent_chain,stamp,close_preserving,cleanup_preserving


class Native:
    def __init__(self,path,expected,budget,limits):
        self.path=parent_chain(path);self.expected=descriptor(expected);self.budget=budget;self.limits=limits
        self.fd=None;self.handle=None;self.file=None;self.before=None;self.read_elements=0;self.read_operations=0
    def __enter__(self):
        self.budget.tick()
        import h5py
        need(h5py.__version__=='3.13.0','exact qualified native HDF5/Python environment')
        self.h5py=h5py;self.budget.reserve_read(self.expected['bytes']+1)
        try:
            self.fd=os.open(self.path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);self.before=os.fstat(self.fd)
            need(stat.S_ISREG(self.before.st_mode)and self.before.st_nlink==1 and self.before.st_size==self.expected['bytes'],'exact ordinary original asset')
            digest=hashlib.sha256();left=self.before.st_size
            while left:
                self.budget.tick();chunk=os.read(self.fd,min(1<<20,left));need(chunk,'short original asset');left-=len(chunk);digest.update(chunk)
            need(not os.read(self.fd,1)and digest.hexdigest()==self.expected['sha256'],'complete original asset SHA')
            self.check();os.lseek(self.fd,0,os.SEEK_SET)
            self.handle=os.fdopen(self.fd,'rb',closefd=False)
            self.file=self.h5py.File(self.handle,'r');self.budget.tick();self.check()
            return self
        except BaseException as error:
            try:self.close()
            except BaseException as later:raise BaseExceptionGroup('native enter and independent cleanup',[error,later])from None
            raise
    def check(self):
        self.budget.tick();need(self.fd is not None and stamp(self.before)==stamp(os.fstat(self.fd))==stamp(os.lstat(self.path)),
                               'same open original inode/name throughout native access')
    def close(self):
        errors=[]
        for attr in ('file','handle'):
            obj=getattr(self,attr);setattr(self,attr,None)
            if obj is not None:
                try:obj.close()
                except BaseException as e:errors.append(e)
        fd=self.fd;self.fd=None
        if fd is not None:
            try:
                need(stamp(self.before)==stamp(os.fstat(fd))==stamp(os.lstat(self.path)),'final original name/FD custody')
            except BaseException as e:errors.append(e)
            try:os.close(fd)
            except BaseException as e:errors.append(e)
        try:self.budget.tick()
        except BaseException as e:errors.append(e)
        if errors:raise BaseExceptionGroup('independent native close/custody/clock failures',errors)
    def __exit__(self,typ,error,tb):
        try:self.close()
        except BaseException as later:
            if error is not None:raise BaseExceptionGroup('native operation and close',[error,later])from None
            raise
        return False
    def object(self,name,kind='dataset'):
        self.check();parts=name.split('/');need(parts and all(x not in ('','.','..')for x in parts),'exact native path')
        obj=self.file
        for part in parts:
            link=obj.get(part,getlink=True);need(type(link)is self.h5py.HardLink,'no external/soft native link')
            obj=obj[part]
        if kind=='group':need(isinstance(obj,self.h5py.Group),'native group required')
        else:
            need(isinstance(obj,self.h5py.Dataset)and not obj.is_virtual and not obj.external,'ordinary internal native dataset')
            need(obj.ndim<=2 and all(type(x)is int and 0<=x<=self.limits['max_axis']for x in obj.shape),'bounded declared native axes')
            if obj.chunks is not None:
                chunk=math.prod(obj.chunks)*max(1,obj.dtype.itemsize)
                need(chunk<=self.limits['max_chunk_bytes'],'admitted native decompression chunk')
        self.budget.tick();return obj
    def read(self,name,index=Ellipsis,*,shape=None,kinds='fiu',text=False):
        data=self.object(name)
        if index is Ellipsis:expected=data.shape
        elif index==()and data.ndim==0:expected=()
        elif type(index)is int:
            need(data.ndim==1 and 0<=index<data.shape[0],'nonnegative bounded scalar index');expected=()
        elif type(index)is tuple and len(index)==2 and type(index[0])is slice and type(index[1])is int:
            start,stop,step=index[0].indices(data.shape[0]);need(step==1 and 0<=index[1]<data.shape[1],'bounded unit-stride channel slice');expected=(max(0,stop-start),)
        elif type(index)is slice:
            need(data.ndim==1,'one-dimensional slice');start,stop,step=index.indices(data.shape[0]);need(step==1,'unit stride');expected=(max(0,stop-start),)
        else:raise ValueError('unselected native indexing')
        if shape is not None:need(tuple(expected)==tuple(shape),'exact native read shape before allocation')
        elements=math.prod(expected)if expected else 1
        integer(elements,0,self.limits['max_array_elements']);need(self.read_elements+elements<=self.limits['total_elements'],'complete native element allowance')
        need(text or data.dtype.kind in kinds,'primitive native numeric dtype before allocation')
        if text:need(expected==()and (data.dtype.kind in 'SUO'),'one bounded qualified source text scalar')
        size=elements*(self.limits['max_text_bytes']if text else max(8,data.dtype.itemsize))
        need(size<=self.limits['max_array_bytes'],'prospective native allocation bound')
        self.budget.reserve_read(max(size,0 if data.chunks is None else math.prod(data.chunks)*max(1,data.dtype.itemsize)))
        self.read_elements+=elements;self.read_operations+=1;self.check()
        value=data[index];self.check()
        if text:
            if isinstance(value,bytes):value=value.decode('utf-8')
            need(type(value)is str and len(value.encode())<=self.limits['max_text_bytes'],'bounded exact native text')
        else:
            import numpy as np
            need(np.shape(value)==expected and np.asarray(value).dtype.kind in kinds and np.isfinite(value).all(),'finite primitive returned shape')
        return value
    def attribute(self,name,key,*,text=False):
        data=self.object(name);self.budget.reserve_read(self.limits['max_text_bytes']if text else 8);self.check()
        aid=data.attrs.get_id(key)
        try:
            need(aid.shape==(),'scalar native attribute before read');value=data.attrs[key];self.check()
        finally:cleanup_preserving(aid.close)
        if text:
            if isinstance(value,bytes):value=value.decode('utf-8')
            need(type(value)is str and len(value.encode())<=self.limits['max_text_bytes'],'bounded text attribute')
            return value
        # numpy scalar conversion occurs only after scalar shape admission.
        return finite(value.item()if hasattr(value,'item')else value)
    def record(self):
        return {'source':self.expected,'read_elements_reserved':self.read_elements,'native_read_operations':self.read_operations,
                'physical_hdf5_io_internal_allocations_unmeasured':True}
