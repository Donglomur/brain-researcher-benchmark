"""Bounded concrete array/profile/state transport used by the real entry.

Raw scientific bodies are opened only by explicit consumer calls. This source
implements ordinary file identity and complete byte capture, not an OS sandbox
or independent original-process attestation.
"""
from pathlib import Path
import hashlib
import json
import math
from .artifact_io import Store, Pin, strict_json, json_bytes, relative
from .nomad_math import need, closed, integer, identity, Budget, state_identity


def descriptor(value):
    closed(value,['path','bytes','sha256'],'closed captured artifact descriptor')
    relative(value['path']);return Pin.parse({k:value[k] for k in ('bytes','sha256')})


class Catalog:
    def __init__(self,root,artifacts,store,max_member_bytes,max_array_elements):
        self.root=Path(root);self.store=store
        self.member_cap=integer(max_member_bytes,1)
        self.array_cap=integer(max_array_elements,1)
        need(type(artifacts) is dict,'complete named artifact map')
        self.artifacts=json.loads(json.dumps(artifacts,allow_nan=False));self.captures=[]
        for name,row in artifacts.items():
            need(type(name) is str and name,'named source artifact')
            p=descriptor(row);need(p.bytes<=self.member_cap,'preventive artifact extent')

    def raw(self,name):
        need(name in self.artifacts,'selected exact artifact name')
        row=self.artifacts[name];pin=descriptor(row)
        b=self.store.read(self.root/row['path'],max(pin.bytes,1),pin)
        self.captures.append({'name':name,'descriptor':dict(row)})
        return b

    def document(self,name):
        return strict_json(self.raw(name))

    def array(self,name,shape,numpy_version):
        need(type(shape) is list and shape and all(type(n) is int and n>=0 for n in shape),
             'complete exact tensor shape')
        count=math.prod(shape)
        need(count<=self.array_cap,'full array extent before capture/import/allocation')
        need(name in self.artifacts and self.artifacts[name]['bytes']==8*count,
             'raw little-endian float64 byte/shape identity')
        raw=self.raw(name)
        import numpy as np
        need(np.__version__==numpy_version,'selected basic numerical runtime')
        return np.frombuffer(raw,dtype='<f8').reshape(tuple(shape))


class Output:
    def __init__(self,root,store,max_array_elements,numeric_budget):
        self.root=Path(root);need(not self.root.exists(),'new exclusive operator output root')
        self.root.mkdir(mode=0o700);self.store=store;self.files={};self.numeric_budget=numeric_budget
        self.array_cap=integer(max_array_elements,1)

    def raw(self,name,value):
        relative(name);need('/' not in name and name not in self.files,'flat exclusive product name')
        pin=self.store.write(self.root/name,value)
        d={'path':name,**pin};self.files[name]=d;return d

    def document(self,name,value):
        return self.raw(name,json_bytes(value))

    def array(self,name,value):
        need(value.size<=self.array_cap,'preventive output serialization extent')
        need(value.dtype.str in ('<f8','=f8'),'binary64 numerical product')
        self.numeric_budget.reserve('serialize.'+name,{'raw_float64_byte_copy':value.size})
        d=self.raw(name,value.astype('<f8',copy=False).tobytes(order='C'))
        return {'artifact':d,'shape':list(value.shape),'dtype':'<f8'}

    def state(self,name,state):
        need(state['identity']==state_identity(state),'computed fitted state identity')
        arrays={}
        for i,(key,value) in enumerate(sorted(state['arrays'].items())):
            arrays[key]=self.array(name+'.array'+str(i)+'.f64',value)
        m={k:v for k,v in state.items() if k!='arrays'};m['arrays']=arrays
        return self.document(name+'.json',m)


def read_state(catalog,name,numpy_version):
    m=catalog.document(name)
    closed(m,['kind','profile','support','support_pin','input_data_pins','arrays','diagnostics','identity'],
           'complete fitted state artifact')
    need(identity(m['support'])==m['support_pin'],'full fitted support pin')
    arrays={}
    for key,row in m['arrays'].items():
        closed(row,['artifact','shape','dtype'],'fitted array descriptor')
        need(row['dtype']=='<f8','exact state dtype')
        candidates=[n for n,d in catalog.artifacts.items() if d==row['artifact']]
        need(len(candidates)==1,'state array joins one independently selected complete artifact')
        arrays[key]=catalog.array(candidates[0],row['shape'],numpy_version)
    m['arrays']=arrays
    need(m['identity']==state_identity(m),'captured complete numerical state content')
    return m


def pointer(document,path):
    need(type(path) is list,'closed explicit JSON pointer components')
    value=document
    for key in path:
        need(type(key) in (str,int),'literal field/index')
        if type(value) is dict:need(type(key) is str and key in value,'source profile field exists')
        elif type(value) is list:need(type(key) is int and 0<=key<len(value),'source profile index exists')
        else:raise ValueError('source profile path enters a scalar')
        value=value[key]
    return value


def resolve_profile(catalog,selection,required):
    """Join every value to separately selected ordinary source-decision bytes.

    This establishes source custody and declared values, not the truth of an
    experimental recipe. The independently owned request selection is the trust
    boundary. Outputs always retain original qualification holds.
    """
    need(type(selection) is dict and set(selection)==set(required),'no missing/default scientific parameter')
    docs={};profile={};lineage={}
    for name,row in selection.items():
        closed(row,['document','pointer'],'source-selected parameter locator')
        if row['document'] not in docs:docs[row['document']]=catalog.document(row['document'])
        value=pointer(docs[row['document']],row['pointer'])
        need(value is not None,'unresolved original profile fact: '+name)
        profile[name]=value
        lineage[name]={'document':catalog.artifacts[row['document']],'pointer':row['pointer']}
    return profile,lineage


def read_trials(catalog,selection,version):
    closed(selection,['support','trial_arrays'],'closed complete trajectory selection')
    support=catalog.document(selection['support'])
    closed(support,['trial_ids','trial_conditions','condition_ids','time_coordinates','feature_ids'],
           'complete actual trajectory support')
    need(type(selection['trial_arrays']) is dict and
         set(selection['trial_arrays'])==set(support['trial_ids']),'every native trial array selected')
    shape=[len(support['time_coordinates']),len(support['feature_ids'])]
    arrays={k:catalog.array(selection['trial_arrays'][k],shape,version) for k in support['trial_ids']}
    return arrays,support


def full_main_roster(document):
    """Metadata-only complete existing biological scope, no inferred empirical IDs."""
    closed(document,['isometric','reaching','source_roster_pins'],'full two-task paper roster')
    ids=[];pairs=[]
    for task,n in [('isometric',20),('reaching',12)]:
        sessions=document[task]
        need(type(sessions) is list and len(sessions)==n and
             all(type(s) is str and s for s in sessions) and len(set(sessions))==n,
             'full source-declared session roster')
        ids+=sessions;pairs.extend((task,a,b) for a in sessions for b in sessions if a!=b)
    need(len(set(ids))==32 and len(pairs)==512,'all32 independent session identities/all512pairs')
    return {'sessions':tuple(ids),'pairs':tuple(pairs),'existing_method_predictions':2560,
        'existing_anchor_slots':160,'prospective_S12_predictions':1024,
        'prospective_S12_unique_anchors':32,'source_roster_pins':document['source_roster_pins'],
        'empirical_membership_independently_verified':False}
