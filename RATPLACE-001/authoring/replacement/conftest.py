"""Manufactured-only helpers; never locate or read an original NWB."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import h5py
import numpy as np
import pytest

TASK=Path(__file__).resolve().parents[2]

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module

@pytest.fixture
def modules(monkeypatch):
    names=('source_io','information_kernel','artifact_reader','source_reader','source_reference','proof_v2','writer_v2')
    old={n:sys.modules.get(n) for n in names}
    result={}
    try:
        for name,folder in [('source_io','solution'),('information_kernel','solution'),('artifact_reader','tests'),
                            ('source_reader','solution'),('source_reference','tests'),
                            ('proof_v2','tests'),('writer_v2','solution')]:
            result[name]=load(name,TASK/folder/(name+'.py'))
        yield result
    finally:
        for n,v in old.items():
            if v is None:sys.modules.pop(n,None)
            else:sys.modules[n]=v

@pytest.fixture
def manufactured(tmp_path,monkeypatch,modules):
    docs=tmp_path/'documents';root=tmp_path/'data';docs.mkdir();root.mkdir()
    m=json.loads((TASK/'environment/method_contract.json').read_bytes())
    s=json.loads((TASK/'environment/output_schema.json').read_bytes())
    times=np.linspace(0,100,2501)
    x=np.arange(len(times))%4;y=(np.arange(len(times))//4)%5
    position=np.column_stack((x,y)).astype('f8')
    spikes=[np.arange(.2,99.3,1.),np.arange(.3,79.4,1.),np.arange(.7,59.8,1.),np.arange(.1,4.2,1.)]
    values=np.concatenate(spikes)
    buffer=io.BytesIO()
    with h5py.File(buffer,'w') as f:
        f.attrs['nwb_version']='2.9.0'
        p=f.create_group('/processing/behavior/AnimalPosition/Position')
        data=p.create_dataset('data',data=position)
        data.attrs.update(unit='centimeters',conversion=.01,offset=0.)
        clock=p.create_dataset('timestamps',data=times);clock.attrs['unit']='seconds'
        p.create_dataset('reference_frame',data='Synthetic coordinates; no original values.')
        u=f.create_group('units');u.create_dataset('id',data=np.array([9,2,1,11],dtype='i4'))
        u.create_dataset('cell_area',data=['CA1','CA1','DG','CA1'])
        u.create_dataset('cell_type',data=['unclassified']*4)
        sp=u.create_dataset('spike_times',data=values)
        index=u.create_dataset('spike_times_index',data=np.cumsum([len(x) for x in spikes],dtype='u4'))
        index.attrs['target']=sp.ref
    raw=buffer.getvalue();digest=hashlib.sha256(raw).hexdigest()
    m['source'].update(n_positions=len(times),n_units=4,n_spikes=len(values),window_seconds=[0.,100.])
    manifest={'task_id':'RATPLACE-001','schema_version':'ratplace-source-v2',
              'files':[{'path':'manufactured.nwb','size_bytes':len(raw),'sha256':digest}]}
    pins={}
    for name,key,value in zip(('source_manifest.json','method_contract.json','output_schema.json'),
                              modules['source_io'].PINS,(manifest,m,s)):
        b=(json.dumps(value,sort_keys=True)+'\n').encode();(docs/name).write_bytes(b)
        pins[key]=hashlib.sha256(b).hexdigest()
        if name=='source_manifest.json':(root/name).write_bytes(b)
    (root/'manufactured.nwb').write_bytes(raw)
    guard=modules['source_io'];monkeypatch.setattr(guard,'SOURCE_SHA',digest);monkeypatch.setattr(guard,'SOURCE_SIZE',len(raw))
    auth=guard.authenticate
    def authenticate(*a,**kw):
        kw['pins']=pins;return auth(*a,**kw)
    monkeypatch.setattr(guard,'authenticate',authenticate)
    return dict(data=root,documents=docs,raw=raw,pins=pins,method=m,times=times,xy=position,spikes=spikes)

