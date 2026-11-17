"""Frozen33-trained state reused for every reserved query; no model is refitted here."""
import base64
import hashlib
from custody import parse
from protocol import TARGETS, ARMS, canonical, digest, exact_keys, finite, need
from investigation import Investigation

class _StateTicket:
    __slots__=()

class ModelVault:
    """Strong source-issued tickets; no mutable descriptor can authorize replacement state."""
    def __init__(self,custody,recipe,training_fingerprint,seeds):
        self._custody=custody;self._recipe=recipe;self._training=training_fingerprint
        self._seeds=tuple(sorted(seeds.items()));self._issued={};self._by_mode={}

    def publish(self,mode,artifact):
        need(mode in ('reference','frozen_program','adaptive_investigation') and mode not in self._by_mode,'one_issued_model_per_mode')
        seed=None if mode=='reference' else dict(self._seeds)[mode]
        need(artifact['training_fingerprint']==self._training and artifact['candidate_seed']==seed,'issued_model_training_seed')
        body=artifact['body'];need(type(body) is bytes and len(body)==artifact['bytes'] and
            hashlib.sha256(body).hexdigest()==artifact['sha256'],'creator_model_identity')
        name='FROZEN_REFERENCE_MODEL.json' if mode=='reference' else 'FROZEN_'+mode+'_MODEL.bin'
        receipt=self._custody.write_bytes(name,body)
        need(receipt['bytes']==len(body) and receipt['sha256']==artifact['sha256'],'actual_freeze_publication')
        token=_StateTicket()
        # All authoritative fields are immutable builtins in a tuple; actual token is strongly retained.
        record=(mode,self._recipe,seed,self._training,body,len(body),artifact['sha256'],artifact['format'],
                (receipt['path'],receipt['bytes'],receipt['sha256']))
        self._issued[token]=record;self._by_mode[mode]=token
        return token

    def resolve(self,token,mode,recipe,seed,training_fingerprint):
        need(type(token) is _StateTicket and token in self._issued,'original_issued_state_ticket_required')
        record=self._issued[token]
        need(self._by_mode.get(mode) is token and record[:4]==(mode,recipe,seed,training_fingerprint),
             'original_frozen_state_lineage')
        need(type(record[4]) is bytes and len(record[4])==record[5] and
             hashlib.sha256(record[4]).hexdigest()==record[6],'original_frozen_state_bytes')
        return record

    def describe(self,token,mode):
        seed=None if mode=='reference' else dict(self._seeds)[mode]
        row=self.resolve(token,mode,self._recipe,seed,self._training)
        return {'mode':row[0],'recipe_sha256':row[1],'candidate_seed':row[2],
            'training_fingerprint':row[3],'bytes':row[5],'sha256':row[6],'format':row[7],
            'publication':{'path':row[8][0],'bytes':row[8][1],'sha256':row[8][2]}}

def freeze_reference(reference,training):
    need(reference['status']=='complete','complete_reference_before_freeze')
    model=parse(canonical(reference));model.pop('source_rows');model['participant']='frozen_training33'
    for target in TARGETS:
        for arm in ARMS:model['results'][target]['arms'][arm].pop('prediction')
    model['training_fingerprint']=digest(training);model['schema']='neural006-frozen-reference-model-v1'
    body=canonical(model)
    return {'body':body,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),
        'format':'neural006-reference-json-v1','candidate_seed':None,'training_fingerprint':digest(training)}

def reference_view(vault,frozen,case,recipe,training_fingerprint):
    record=vault.resolve(frozen,'reference',recipe,None,training_fingerprint);body=record[4]
    model=parse(body);model['schema']='neural006-reference-v1';model['participant']=case['participant']
    model['source_rows']=[row['source_row'] for row in case['query']]
    for target in TARGETS:
        entry=model['results'][target]
        entry['arms']['mean']['prediction']=[entry['normalizer']['training_equal_person_mean'] for _ in case['query']]
        for arm in ('N','R','V','J'):
            coefficients=entry['arms'][arm]['diagnostic']['coefficients'];predictions=[]
            for row in case['query']:
                value=coefficients['(Intercept)']
                for name,coefficient in coefficients.items():
                    if name=='(Intercept)':continue
                    scale=model['scaling'][name];value+=coefficient*(row[name]-scale['center'])/scale['scale']
                need(finite(value),'frozen_prediction_finite');predictions.append(value)
            entry['arms'][arm]['prediction']=predictions
    model['frozen_model_sha256']=record[6]
    model['frozen_training_fit_calls']=model['actual_fit_calls'];model['actual_fit_calls']=0
    return model

class CandidateSession:
    native=False
    def __init__(self,case,reference,cap,seed,model=None,training_context=None):
        self.session=Investigation(case,reference,cap,training_context=training_context)
        self.finished=False;self.value=None
        self.initial={'event':'predict' if model else 'case','case':case,'available_tools':
            ['training_summary','reference_prediction','predictive_coefficients'],'tool_call_cap':cap,'candidate_seed':seed}
        if model:
            self.initial['frozen_model']={'path':'/input/model.bin','bytes':model['bytes'],'sha256':model['sha256'],'format':model['format']}
    def exchange(self,message):
        if type(message) is dict and 'submit' in message:
            prediction,report=self.session.finish(message);self.finished=True
            self.value={'predictions':prediction,'investigation':report,'tool_history':self.session.history}
            return {'event':'submission_received','admission':'pending_target_free_validation','feedback':None}
        return self.session.request(message)

class TrainingSession:
    native=False
    def __init__(self,training,reference_model,vault,recipe,cap,seed,artifact_cap):
        self.training=training;self.model=reference_model;self.vault=vault;self.recipe=recipe;self.cap=cap;self.artifact_cap=artifact_cap
        self.calls=0;self.history=[];self.finished=False;self.value=None;self.seed=seed
        self.initial={'event':'train_once','training':training,'training_fingerprint':digest(training),
            'available_tools':['training_summary','reference_model'],'tool_call_cap':cap,
            'model_artifact_bytes_cap':artifact_cap,'reserved_queries_available':False,'candidate_seed':seed}
    def exchange(self,message):
        need(not self.finished,'training_after_freeze')
        if type(message) is dict and 'trained' in message:
            exact_keys(message,('trained',),'trained_envelope');value=message['trained']
            exact_keys(value,('training_fingerprint','format','artifact_base64','candidate_seed'),'trained_fields')
            need(value['training_fingerprint']==digest(self.training),'training_artifact_lineage')
            need(type(value['candidate_seed']) is int and value['candidate_seed']==self.seed,'training_seed_binding')
            need(type(value['format']) is str and 0<len(value['format'])<=128,'model_format')
            encoded=value['artifact_base64'];need(type(encoded) is str and len(encoded)<=4*((self.artifact_cap+2)//3),'artifact_encoded_cap')
            body=base64.b64decode(encoded,validate=True);need(0<len(body)<=self.artifact_cap,'artifact_cap')
            self.value={'body':body,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),
                'format':value['format'],'training_fingerprint':value['training_fingerprint'],'tool_history':self.history,'candidate_seed':self.seed}
            self.finished=True;return {'event':'model_received','sha256':self.value['sha256'],'freeze':'pending_durable_publication'}
        exact_keys(message,('tool','arguments'),'training_tool_request');exact_keys(message['arguments'],(),'training_tool_arguments')
        self.calls+=1;need(self.calls<=self.cap,'training_tool_cap')
        if message['tool']=='reference_model':
            reply=parse(self.vault.resolve(self.model,'reference',self.recipe,None,digest(self.training))[4])
        elif message['tool']=='training_summary':
            helper=Investigation(self.training,{},1);reply=helper.request({'tool':'training_summary','arguments':{}})['response']
        else:raise ValueError('unknown_training_tool')
        result={'sequence':self.calls,'response':reply,'response_sha256':digest(reply)}
        self.history.append({'request':message,**result});return result
