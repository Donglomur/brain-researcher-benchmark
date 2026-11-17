"""Complete released-position MATLAB-v7.3 reader with bounded channel caching."""
from __future__ import annotations
import os
from .contract import CONDITIONS, SHAPE, metadata, open_pinned, require
from .slab import ChannelSlab

class Derivative:
    def __init__(self, path, identity, budget, *, metadata_read_reservation):
        metadata(identity)
        require(type(metadata_read_reservation) is int and metadata_read_reservation>0, 'explicit HDF5 metadata reservation')
        self.identity=identity; self.budget=budget; self.fd=None; self.file=None; self.stream=None
        self.slab=ChannelSlab(budget)
        # The dependency is imported only in the future authorized derivative operation.
        import h5py
        self.h5py=h5py
        try:
            self.fd=open_pinned(path,identity['source'],budget)
            budget.charge(read=metadata_read_reservation)
            self.stream=os.fdopen(self.fd,'rb',closefd=False)
            self.file=h5py.File(self.stream,'r')
            root=self.member(self.file,'mTFR')
            self.datasets={}
            for cond in CONDITIONS:
                node=root
                for component in cond.split('.'): node=self.member(node,component)
                power=self.member(node,'powspctrm')
                require(isinstance(power,h5py.Dataset) and list(power.shape)==list(reversed(SHAPE)), 'exact reversed MATLAB array geometry')
                require(power.dtype.kind=='f' and power.dtype.itemsize==8, 'double source only; no implicit single promotion')
                require(power.attrs.get('MATLAB_class',b'')==b'double','MATLAB double class')
                for key in ['freq','time']:
                    axis=self.numeric(self.member(node,key)).reshape(-1).tolist()
                    require(axis==identity['frequency' if key=='freq' else 'time'], 'actual axis identity')
                labels=self.labels(self.member(node,'label'))
                require(labels==identity['labels'],'actual label order')
                self.datasets[cond]=power
        except BaseException:
            self.close(); raise
    def resident(self,value):
        if isinstance(value,self.h5py.Dataset):
            require(not value.is_virtual and not value.external,'no virtual or external HDF5 dataset storage')
        return value
    def member(self,node,name):
        require(isinstance(node,(self.h5py.Group,self.h5py.File)), 'expected MATLAB structure')
        link=node.get(name,getlink=True)
        require(isinstance(link,self.h5py.HardLink),'no external or soft HDF5 links')
        value=self.resident(node[name])
        seen=set()
        for _ in range(8):
            if isinstance(value,self.h5py.Dataset) and self.h5py.check_dtype(ref=value.dtype) is not None and value.size==1:
                require(value.size==1 and value.name not in seen,'scalar bounded structure reference')
                seen.add(value.name); self.budget.charge(read=value.dtype.itemsize)
                ref=value[()].reshape(-1)[0]
                require(bool(ref),'null MATLAB reference'); value=self.resident(self.file[ref])
            else:return value
        raise ValueError('reference depth')
    def numeric(self,ds):
        self.resident(ds)
        require(isinstance(ds,self.h5py.Dataset) and ds.dtype.kind=='f' and ds.dtype.itemsize==8 and ds.size<=200 and ds.attrs.get('MATLAB_class',b'')==b'double','bounded MATLAB double numeric axis; no character/logical/coercion')
        self.budget.charge(read=ds.size*ds.dtype.itemsize*2)
        return ds[()]
    def labels(self,ds):
        self.resident(ds)
        require(isinstance(ds,self.h5py.Dataset) and ds.size==62 and self.h5py.check_dtype(ref=ds.dtype) is not None,'complete MATLAB label cell')
        self.budget.charge(read=ds.size*ds.dtype.itemsize)
        out=[]
        for ref in ds[()].reshape(-1):
            require(bool(ref),'null label'); chars=self.resident(self.file[ref])
            require(isinstance(chars,self.h5py.Dataset) and chars.dtype.kind=='u' and chars.dtype.itemsize==2 and 0<chars.size<=64 and chars.attrs.get('MATLAB_class',b'')==b'char','bounded MATLAB character label')
            self.budget.charge(read=chars.size*4)
            values=chars[()].reshape(-1).tolist()
            out.append(b''.join(int(x).to_bytes(2,'little') for x in values).decode('utf-16-le'))
        return out
    def stored_position_values(self,condition,channel,frequency,time):
        require(condition in CONDITIONS and type(channel) is int and 0<=channel<62 and type(frequency) is int and 0<=frequency<53 and type(time) is int and 0<=time<200,'full-source cell address')
        return self.slab.values(self.datasets[condition],condition,channel,frequency,time)
    def close(self):
        self.slab.close()
        if self.file is not None:self.file.close();self.file=None
        if self.stream is not None:self.stream.close();self.stream=None
        if self.fd is not None:os.close(self.fd);self.fd=None
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
