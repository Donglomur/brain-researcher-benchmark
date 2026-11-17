"""Task-local BrainWide commit gate:96 simultaneous means, then one count row."""
import hashlib
import json
import math
import re

PROTOCOL='NEURAL024-causal-v1'
ROUNDS=22100
WARMUP=10
CHANNELS=96
FIRST_BIN=3000
COMMIT_CAP=4608


def need(ok,message):
    if not ok:raise ValueError(message)


def unique(pairs):
    result={}
    for key,value in pairs:
        need(key not in result,'Duplicate response key');result[key]=value
    return result


def real(token):
    value=float(token);need(math.isfinite(value),'Nonfinite response number')
    if value==0:
        need(not any(c in '123456789' for c in token.lower().split('e')[0]),'Nonzero underflow')
    return value


def decode(body,cap=4096):
    need(type(body) is bytes and 0<len(body)<=cap,'Bounded complete JSON frame')
    return json.loads(body,object_pairs_hook=unique,parse_float=real,
                      parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite constant')))


def wire(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode('ascii')


def answer(body,request):
    value=decode(body)
    need(type(value) is dict and set(value)=={'sequence','nonce','mean_counts'},'Exact response keys')
    need(type(value['sequence']) is int and value['sequence']==request['sequence']
         and type(value['nonce']) is str and value['nonce']==request['nonce'],'Exact current sequence/nonce')
    means=value['mean_counts']
    need(type(means) is list and len(means)==CHANNELS,'All96 simultaneous predictions')
    admitted=[]
    for x in means:
        need(type(x) in (int,float),'Nonboolean numeric expected counts')
        try:x=float(x)
        except (OverflowError,ValueError):raise ValueError('Float64-compatible mean') from None
        need(math.isfinite(x) and x>0,'Strictly positive finite expected count; no clipping')
        admitted.append(x)
    return {'sequence':value['sequence'],'nonce':value['nonce'],'mean_counts':admitted}


def wrapped(request,observation):
    """Insert one trusted canonical row opaquely; no host count-vector parsing."""
    need(request['observation'] is None,'Private observation placeholder')
    if observation is None:body=wire(request)
    else:
        need(type(observation) is bytes and 0<len(observation)<=2048 and observation[:1]==b'{'
             and observation[-2:]==b'}\n','Bounded canonical count-row fragment')
        template=wire(request);marker=b'"observation":null'
        need(template.count(marker)==1,'One observation slot')
        body=template.replace(marker,b'"observation":'+observation[:-1],1)
    need(len(body)<=4096,'Bounded request envelope')
    return body


class Gate:
    def __init__(self,intervals):
        need(type(intervals) is list and len(intervals)==ROUNDS,'All22100 chronological intervals')
        previous=None
        for pair in intervals:
            need(type(pair) is list and len(pair)==2 and all(type(x) in (int,float) and math.isfinite(x) for x in pair)
                 and pair[1]>pair[0] and abs(pair[1]-pair[0]-.02)<=1e-7,'Native20ms interval support')
            need(previous is None or pair[0]==previous,'Contiguous native interval joins');previous=pair[1]
        need(abs(intervals[0][0]-60)<=1e-7 and abs(intervals[-1][1]-502)<=1e-7,'Exact calibration-to-final support')
        self.intervals=intervals;self.position=0;self.feedback_released=0;self.pending=None;self.previous=None
        self.nonces=set()

    def reveal(self,nonce):
        need(self.pending is None and self.position<ROUNDS and self.feedback_released==self.position,
             'Prior durable commit and feedback authorization before next prediction')
        need(type(nonce) is str and re.fullmatch('[a-f0-9]{32}',nonce),'Fresh nonce shape')
        need(nonce not in self.nonces,'Nonce never reused in this stream');self.nonces.add(nonce)
        self.pending={'protocol':PROTOCOL,'status':'predict','sequence':self.position,
                      'target_bin':FIRST_BIN+self.position,'interval':self.intervals[self.position],
                      'scored':self.position>=WARMUP,'nonce':nonce,'observation':None}
        return dict(self.pending)

    def commit(self,response,record_bytes,acknowledged_pin,fsync_completed):
        need(self.pending is not None and fsync_completed is True and type(record_bytes) is bytes
             and 0<len(record_bytes)<=COMMIT_CAP,'Exact durable complete-vector acknowledgement')
        expected={'bytes':len(record_bytes),'sha256':hashlib.sha256(record_bytes).hexdigest()}
        need(type(acknowledged_pin) is dict and set(acknowledged_pin)=={'bytes','sha256'}
             and type(acknowledged_pin['bytes']) is int and acknowledged_pin==expected,'Exact written commit pin')
        record=decode(record_bytes,COMMIT_CAP)
        need(wire(record)==record_bytes and set(record)=={'sequence','target_bin','scored','nonce','request_sha256',
             'mean_counts','previous_commit','revealed','received'},'Exact canonical commit schema')
        need(type(record['sequence']) is int and type(record['target_bin']) is int and type(record['scored']) is bool
             and record['sequence']==self.position and record['target_bin']==FIRST_BIN+self.position
             and record['scored'] is (self.position>=WARMUP) and record['nonce']==self.pending['nonce']
             and record['nonce']==response['nonce'] and response['sequence']==self.position
             and record['mean_counts']==response['mean_counts'] and record['previous_commit']==self.previous,
             'Commit binds all96 means and this exact round')
        need(type(record['request_sha256']) is str and re.fullmatch('[a-f0-9]{64}',record['request_sha256'])
             and all(type(record[k]) in (int,float) and math.isfinite(record[k]) and record[k]>=0 for k in ('revealed','received'))
             and record['received']>=record['revealed'],'Bounded request identity and monotone timing metadata')
        self.previous=expected;self.position+=1;self.pending=None
        return expected

    def feedback(self,sequence):
        need(type(sequence) is int and self.pending is None and self.position==sequence+1
             and self.feedback_released==sequence,'Count row remains private until its complete vector is committed')
        self.feedback_released+=1
