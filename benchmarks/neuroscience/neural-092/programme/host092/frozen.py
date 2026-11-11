"""All-panel immutable prediction files, parent-published after worker stop."""
from array import array
from dataclasses import asdict
from .storage import encode,decode,digest
from .packet import array_bytes,prediction_plane
from gain.constants import MODELS
from gain.host import FrozenPredictions
from gain.reference import ReferenceSession
from gain.scoring import admit_prediction

def plain(value):
    # This deterministic diagnostic projection is not an exception identity.
    # Original exceptions stay in the caller's Attempt until child termination.
    if isinstance(value,BaseException):return {'exception_type':type(value).__module__+'.'+type(value).__qualname__,'raw_object_transferred':False}
    if type(value)is array:return {'typecode':value.typecode,'values':list(value)}
    if type(value)is tuple:return {'tuple':[plain(v)for v in value]}
    if type(value)is list:return [plain(v)for v in value]
    if type(value)is dict:return {'mapping':[[plain(k),plain(v)]for k,v in value.items()]}
    if value is None or type(value)in (str,int,float,bool):return value
    raise TypeError('unsupported complete diagnostic value')
def restore(value):
    if type(value)is list:return [restore(v)for v in value]
    if type(value)is dict:
        if set(value)=={'tuple'}:return tuple(restore(v)for v in value['tuple'])
        if set(value)=={'mapping'}:return {restore(k):restore(v)for k,v in value['mapping']}
        if set(value)=={'typecode','values'}:return array(value['typecode'],value['values'])
        if 'exception_type'in value:return value
    return value

class Frozen(FrozenPredictions):
    def __init__(self,store,metadata,infos,references,candidates):
        self.store=store;self.metadata=metadata;self.infos=infos;self.closed=False;self.references={};self.candidates={};self.pins={};self.ready=False
        for sid in metadata:
            r=references[sid]
            if not r.complete or r.output_failures or any(x['status']!='success'for x in r.slots):raise ValueError('complete independent reference required')
            # Full coefficients/selection/slots, not only the five mean planes.
            record={k:v for k,v in r.__dict__.items()if k!='predictions'}
            self.pins[sid+'/record.json']=store.put(sid+'/record.json',encode(plain(record)))
            for model in MODELS:
                admit_prediction({'session_id':sid,'unit_ids':list(infos[sid]['unit_ids']),'query_ids':[q['id']for q in infos[sid]['rows']['QUERY']],'means':r.predictions[model]},metadata[sid],infos[sid])
                name=sid+'/'+model+'.f64';self.pins[name]=store.put(name,array_bytes(r.predictions[model]))
            admit_prediction(candidates[sid],metadata[sid],infos[sid]);name=sid+'/candidate.f64'
            self.pins[name]=store.put(name,array_bytes(candidates[sid]['means']))
        self.manifest_pin=store.put('MANIFEST.json',encode({'schema':'neural092_parent_prediction_freeze_v1','members':self.pins,'session_order':list(metadata)}))
        # Read every original published byte back before granting target access.
        for name,p in self.pins.items():store.read(name,p,p['bytes'])
        store.read('MANIFEST.json',self.manifest_pin,self.manifest_pin['bytes'])
        self.ready=True
    def _shape(self,sid):return len(self.infos[sid]['rows']['QUERY']),len(self.infos[sid]['unit_ids'])
    def read_reference(self,sid):
        if not self.ready or self.closed:raise RuntimeError('closed/unread freeze')
        name=sid+'/record.json';p=self.pins[name];r=restore(decode(self.store.read(name,p,p['bytes'])))
        pred={}
        for model in MODELS:
            name=sid+'/'+model+'.f64';p=self.pins[name];pred[model]=prediction_plane(self.store.read(name,p,p['bytes']),*self._shape(sid))
        return ReferenceSession(predictions=pred,**r)
    def read_candidate(self,sid):
        if not self.ready or self.closed:raise RuntimeError('closed/unread freeze')
        name=sid+'/candidate.f64';p=self.pins[name]
        return {'session_id':sid,'unit_ids':list(self.infos[sid]['unit_ids']),'query_ids':[r['id']for r in self.infos[sid]['rows']['QUERY']],'means':prediction_plane(self.store.read(name,p,p['bytes']),*self._shape(sid))}
    def close(self):
        if not self.closed:self.closed=True;self.store.close()
