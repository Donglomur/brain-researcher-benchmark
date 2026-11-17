"""Real submitted-program analysis/fit/inference in the qualified native sandbox.

Candidate functions are the methods under evaluation, not host result callbacks.
No candidate source or state is imported/deserialized in the operator host.
"""
import contextlib
from pathlib import Path
from core import need, capture, encoded, pin, fresh
from corpus import load_session
from state_io import load,save
from arrays import write_json,write_array
from candidate_tools import Tools


class BoundedText:
    def __init__(self,limit): self.limit=limit;self.parts=[];self.count=0
    def write(self,text):
        need(type(text)is str,'text stdout');raw=text.encode();self.count+=len(raw)
        need(self.count<=self.limit,'analysis stdout byte cap; no silent truncation')
        self.parts.append(text);return len(text)
    def flush(self): return None
    def value(self):return ''.join(self.parts)


def context(request,budget):
    need(request['mode'] in ('F','I') and request['role'] in ('C','J'),'selected workflow/access')
    training=[];evaluation=[]
    for name,target in (('training',training),('evaluation',evaluation)):
        for row in request[name]:
            s=load_session(request['input_root'],row['view'],request['role'],name=='training',budget,request['limits'])
            need(s['session']==row['session'] and s['animal']==row['animal'],'complete assigned session identity')
            target.append(s)
    if request['stage'] in ('analysis','fit'):
        need(len(training)==423 and len({s['animal'] for s in training})==126,'full source corpus for every candidate author/fit context')
    else:
        need(not training,'retired training mount; permitted training examples may remain in this condition’s sealed model')
    need(not {s['animal'] for s in training}&{s['animal'] for s in evaluation},'strict cross-animal task')
    if request['stage'] in ('analysis','fit') and request['mode']=='F': need(not evaluation,'global F construction cannot access evaluation data')
    if evaluation:
        need({s['animal'] for s in evaluation}=={request['animal']},'one assigned evaluation animal only')
        need([s['session'] for s in evaluation]==request['animal_sessions'],'all sessions of that animal, no cross-animal cache')
    tools=Tools(request,budget)
    return {'training':training,'evaluation':evaluation,'tools':tools,'role':request['role'],
            'animal':request['animal'],'current_session':request.get('current_session'),
            'clock':budget.tick,'resource_limits':request['limits']}


def source(request,budget):
    raw,_=capture(request['program']['path'],request['program']['pin'],request['limits']['source_bytes'],budget,readonly=True)
    text=raw.decode('utf-8');budget.tick();code=compile(text,'submitted-neural058-method.py','exec');budget.tick()
    namespace={'__name__':'neural058_submitted_method'}
    exec(code,namespace);budget.tick()
    return namespace


def run(request,budget):
    need(request.get('schema')=='neural058_candidate_request_v1' and request.get('task')=='NEURAL-058','native task request')
    stage=request['stage'];need(stage in ('analysis','fit','numeric_features','infer'),'literal native candidate stage')
    output=fresh(request['output_root'],budget);ctx=context(request,budget)
    sink=BoundedText(request['limits']['stdout_bytes'])
    with contextlib.redirect_stdout(sink),contextlib.redirect_stderr(sink):
        code=source(request,budget)
        if stage=='analysis':
            need(callable(code.get('analyze')),'analysis must define analyze(context)')
            result=code['analyze'](ctx);budget.tick()
            # Only bounded strict JSON returns to the host/provider; numerical
            # analyses can report their results, but no private roots are mounted.
            body=encoded(result);need(len(body)<=request['limits']['analysis_result_bytes'],'bounded actual analysis result')
            record={'analysis':result,'stdout':sink.value()}
        elif stage=='fit':
            need(callable(code.get('fit')),'submitted actual fit(context)')
            state=code['fit'](ctx);budget.tick()
            record={'state':save(output,state,budget,request['limits']),'stdout':sink.value()}
        else:
            state=load(request['state_root'],request['state']['metadata'],budget,request['limits'])
            if stage=='numeric_features':
                need(callable(code.get('numeric_features')),'sealed numerical feature method')
                features=code['numeric_features'](ctx,state);budget.tick()
                need(type(features)is list and len(features)==len(request['recipe']['numeric_slots']),'exact frozen numerical slots')
                from core import finite
                clean=[]
                for row in features:
                    need(type(row)is list and 0<len(row)<=4096,'bounded numerical slot features')
                    clean.append([finite(x) for x in row])
                record={'features':clean,'stdout':sink.value()}
            else:
                import numpy as np
                need(callable(code.get('infer')),'submitted actual infer(context,state,provider_values)')
                result=code['infer'](ctx,state,request['provider_values']);budget.tick()
                session=next(s for s in ctx['evaluation'] if s['session']==request['current_session'])
                expected=[w['query'] for w in session['windows']]
                need(type(result)is dict and set(result)==set(expected),'all original query occurrences for current session')
                values=[];offsets=[0]
                for window in session['windows']:
                    p=np.asarray(result[window['query']])
                    need(p.dtype.kind in 'fiu' and p.shape==(len(window['times']),2) and np.isfinite(p).all(),
                         'two complete finite prediction heads')
                    values.append(p.astype('<f8'));offsets.append(offsets[-1]+len(p))
                record={'session':session['session'],'animal':session['animal'],'queries':expected,
                        'values':write_array(output,'predictions.npy',np.concatenate(values),budget,request['limits']['expanded_bytes']),
                        'offsets':write_array(output,'offsets.npy',np.asarray(offsets,dtype='<i8'),budget,request['limits']['expanded_bytes']),
                        'state':request['state'],'stdout':sink.value()}
    record.update(schema='neural058_candidate_result_v1',task='NEURAL-058',stage=stage,
                  request=pin(encoded(request)),program=request['program']['pin'],role=request['role'],
                  panel=request['panel'],animal=request['animal'],budget_before_publication=budget.record())
    descriptor=write_json(output,'RESULT.json',record,budget,request['limits']['metadata_bytes'])
    budget.tick();return descriptor
