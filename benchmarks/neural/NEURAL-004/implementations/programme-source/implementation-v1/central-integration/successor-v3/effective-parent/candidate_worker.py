"""Standalone fixed worker for an independently isolated generated-code job.

Never run this in the protected controller. It has no private original targets,
reference outputs or cross-context history. Namespace/cgroup deployment is an
external qualification gate; Python exec itself supplies no sandbox.
"""
import hashlib,json,math,os,sys
from pathlib import Path

def need(ok,message):
    if not ok:raise ValueError(message)
class Cleanup:
    def __init__(self):self.actions=[]
    def __enter__(self):return self
    def defer(self,name,action):self.actions.append((name,action))
    def __exit__(self,typ,primary,tb):
        first=primary;secondary=[]
        while self.actions:
            name,action=self.actions.pop()
            try:action()
            except BaseException as error:
                if first is None:first=error
                else:secondary.append({'operation':name,'type':type(error).__name__})
        if first is not None and secondary:first.neural004_cleanup_errors=secondary
        if primary is None and first is not None:raise first
        return False
def encode(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
def pin(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def decode(raw):
    def pairs(rows):
        d={}
        for k,v in rows:need(k not in d,'duplicate JSON key');d[k]=v
        return d
    def bad(value):raise ValueError('nonfinite JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)
def read(path,expected,cap):
    need(expected['bytes']<=cap,'preventive input extent')
    with Cleanup() as cleanup:
        f=open(path,'rb');cleanup.defer('close mounted input',f.close);raw=f.read(expected['bytes']+1)
    need(pin(raw)==expected,'exact mounted input');return raw
def write(name,raw,cap):
    need(type(name) is str and '/' not in name and len(raw)<=cap,'bounded flat output')
    with Cleanup() as cleanup:
        fd=os.open('/output/'+name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
        cleanup.defer('close candidate output',lambda:os.close(fd))
        view=memoryview(raw)
        while view:
            n=os.write(fd,view);need(n>0,'complete output write');view=view[n:]
        os.fsync(fd)
    return {'path':name,**pin(raw)}
def main():
    request_path=sys.argv[1];cap=int(sys.argv[2]);need(cap>0,'explicit request cap')
    with Cleanup() as cleanup:
        f=open(request_path,'rb');cleanup.defer('close candidate request',f.close);raw=f.read(cap+1)
    need(len(raw)<=cap,'request cap');q=decode(raw)
    need(set(q)=={'schema','job_id','action','code_pin','training_pin','query_pin','state_pin','limits'},'fixed request schema')
    need(q['schema']=='neural004_candidate_job_v1','candidate job schema');limits=q['limits']
    for n in limits.values():need(type(n) is int and n>0,'finite selected worker limits')
    source=read('/program/generated.py',q['code_pin'],limits['source_bytes'])
    train=decode(read('/training/view.json',q['training_pin'],limits['view_bytes']))
    query=None if q['query_pin'] is None else decode(read('/query/view.json',q['query_pin'],limits['view_bytes']))
    state=None if q['state_pin'] is None else decode(read('/sealed/state.json',q['state_pin'],limits['state_bytes']))
    action=q['action'];need(action in ('analyze','train','predict','reconstruct','explain'),'fixed actual computation action')
    ns={'__name__':'neural004_generated_method'};outputs={};error=None
    try:
        exec(compile(source,'/program/generated.py','exec'),ns)
        method=ns.get(action);need(callable(method),'generated source must define requested method')
        if action=='train':result=method(train,query)
        elif action=='predict':result=method(state,query)
        else:result=method(train,query,state)
        body=encode(result);need(len(body)<=limits['output_bytes'],'complete generated artifact extent')
        # Result is a computed artifact, never a claim of scientific success.
        outputs['RESULT.json']=write('RESULT.json',body,limits['output_bytes'])
    except BaseException as e:error={'type':type(e).__name__,'message':str(e)[:1024]}
    execution={'schema':'neural004_execution_v1','job_id':q['job_id'],'action':action,'request_pin':pin(raw),
        'code_pin':q['code_pin'],'training_pin':q['training_pin'],'query_pin':q['query_pin'],'state_pin':q['state_pin'],
        'candidate_status':'failed' if error else 'returned','error':error,'result_pin':outputs.get('RESULT.json'),
        'physical_qualification':False}
    outputs['EXECUTION.json']=write('EXECUTION.json',encode(execution),limits['output_bytes'])
    write('RESULT_INDEX.json',encode({'schema':'neural004_job_index_v1','job_id':q['job_id'],'outputs':outputs}),limits['output_bytes'])
    with Cleanup() as cleanup:
        fd=os.open('/output',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        cleanup.defer('close candidate output parent',lambda:os.close(fd));os.fsync(fd)
if __name__=='__main__':main()
