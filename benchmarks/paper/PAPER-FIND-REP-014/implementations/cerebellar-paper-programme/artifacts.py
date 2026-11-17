"""Concrete bounded JSON/primitive-NPY artifact store and model admission."""
import hashlib
import math
from pathlib import Path
import re
import time
from core import need, encoded, descriptor
from safe_io import capture, child, strict, pin, durable_new, array, write_array


class Store:
    def __init__(self,root,limits,deadline):
        self.root=Path(root);self.limits=dict(limits);self.deadline=deadline
        need(self.root.is_dir() and set(limits)=={'read_bytes','write_bytes','file_bytes','metadata_bytes','files'}, 'Exact bounded preprovisioned store')
        need(all(type(x) is int and x>0 for x in limits.values()), 'Positive artifact limits')
        self.reads=self.writes=0;self.files={}
    def tick(self):need(time.monotonic()<self.deadline,'Original phase deadline')
    def read(self,name,p,metadata=False):
        descriptor(p,True);self.tick();cap=self.limits['metadata_bytes'] if metadata else self.limits['file_bytes']
        need(p['bytes']<=cap and self.reads+p['bytes']<=self.limits['read_bytes'],'Reserve exact complete artifact read')
        self.reads+=p['bytes'];return capture(child(self.root,name),max(1,cap),p)
    def json(self,name,p):return strict(self.read(name,p,True))
    def numeric(self,desc):
        self.tick();need(desc['bytes']<=self.limits['file_bytes'] and self.reads+desc['bytes']<=self.limits['read_bytes'],'Reserve complete primitive array read')
        self.reads+=desc['bytes'];return array(self.root,desc,self.limits['file_bytes'])
    def put(self,name,raw):
        self.tick();need(type(raw) is bytes and len(raw)<=self.limits['file_bytes'] and self.writes+len(raw)<=self.limits['write_bytes'],'Complete file write allocation')
        need(name not in self.files and len(self.files)<self.limits['files'],'Fresh bounded artifact membership')
        target=child(self.root,name);target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.writes+=len(raw);p=durable_new(target,raw);self.files[name]=p;return p
    def put_json(self,name,value):
        raw=encoded(value);need(len(raw)<=self.limits['metadata_bytes'],'Full metadata cap; never trim');return self.put(name,raw)
    def put_numeric(self,name,value):
        import io
        import numpy as np
        self.tick();x=np.asarray(value)
        need(x.dtype.str in ('<f8','<f4','<i8','|i1') and x.flags.c_contiguous,'Primitive C-order numeric payload')
        s=io.BytesIO();np.lib.format.write_array_header_1_0(s,np.lib.format.header_data_from_array_1_0(x));header=s.getvalue()
        need(len(header)<=65545 and len(header)+x.nbytes<=self.limits['file_bytes'] and self.writes+len(header)+x.nbytes<=self.limits['write_bytes'],'Reserve exact primitive header and complete body before encoding')
        raw=header+x.tobytes(order='C')
        p=self.put(name,raw);return {'path':name,**p,'shape':list(x.shape),'dtype':x.dtype.str}
    def envelope(self,phase_id,request_pin,result):
        self.put_json('RESULT.json',result)
        value={'schema':'osl_transport_output_manifest_v1','phase_id':phase_id,'request_sha256':request_pin['sha256'],'files':dict(self.files)}
        self.put_json('OUTPUTS.json',value)
        return value


def save_model(store,model,cell_tokens,profile):
    import numpy as np
    need(type(model) is dict and set(model)=={'metadata','arrays'} and type(model['metadata']) is dict and type(model['arrays']) is dict,'Strict primitive model ABI')
    need(type(cell_tokens) is list and cell_tokens and len(set(cell_tokens))==len(cell_tokens),'Complete ordered opaque model cell axis')
    arrays={}
    for name,value in sorted(model['arrays'].items()):
        need(type(name) is str and re.fullmatch('[A-Za-z0-9_]{1,64}',name),'Bounded model array key')
        x=np.ascontiguousarray(value);need(x.dtype.str in ('<f8','<f4','<i8','|i1'),'No object, pickle or executable model bodies')
        if x.dtype.kind=='f':need(np.isfinite(x).all(),'Finite required numeric model state')
        arrays[name]=store.put_numeric('model/'+name+'.npy',x)
    value={'schema':'paper_i_primitive_model_v1','profile':profile,'cell_tokens':cell_tokens,'metadata':model['metadata'],'arrays':arrays}
    p=store.put_json('MODEL.json',value);return value,p


def load_model(store,name,p,profile,cell_tokens):
    import numpy as np
    m=store.json(name,p)
    need(type(m) is dict and set(m)=={'schema','profile','cell_tokens','metadata','arrays'} and m['schema']=='paper_i_primitive_model_v1','Exact model manifest')
    need(m['profile']==profile and m['cell_tokens']==cell_tokens and type(m['metadata']) is dict and type(m['arrays']) is dict,'Fit profile/cell-axis provenance')
    arrays={}
    for k,d in m['arrays'].items():
        need(re.fullmatch('[A-Za-z0-9_]{1,64}',k),'Safe model key')
        prefix=Path(name).parent
        bound={**d,'path':str(prefix/d['path'])}
        a=store.numeric(bound)
        if a.dtype.kind=='f':need(np.isfinite(a).all(),'Finite model numeric state')
        arrays[k]=a
    return {'metadata':m['metadata'],'arrays':arrays}
