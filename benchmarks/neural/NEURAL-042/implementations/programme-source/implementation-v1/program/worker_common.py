"""Shared numerical worker admission, independent bounded output and receipt."""
from pathlib import Path
import hashlib,random
from core import need,integer,finite,encoded,pin,parse,capture,publish,Budget
from contracts import exact,CLAIM

def start(request,context):
    need(request['schema']=='neural042_worker_request_v1','exact worker schema')
    need(request['source_manifest']==context['source_manifest'],'captured worker source closure')
    need(request['original_origin']==context['original_origin']and request['deadline']==context['deadline'],'same original clocks')
    b=Budget(request['original_origin'],request['deadline'],request['read_bytes'],request['write_bytes'])
    need(context['source_read_reserved']<=b.read_cap,'worker source reservations included')
    b.read_bytes=context['source_read_reserved'];b.reserve_write(65536);context['worker_budget']=b;b.tick()
    seed=integer(request['seed'],0,2**32-1);random.seed(seed)
    import numpy as np
    need(np.__version__=='2.2.6','qualified worker NumPy seed/array environment');np.random.seed(seed)
    need(request['rng_contract']=='python_random_and_numpy_legacy_global_explicit_seed_v2','explicit supported RNG contract')
    return b

def recipe(value):
    exact(value,('provider_slots',),'frozen positive recipe')
    slots=value['provider_slots'];need(type(slots)is dict and len(slots)<=16,'bounded frozen slots')
    for name,row in slots.items():
        need(type(name)is str and name.isidentifier()and len(name)<=64,'fixed slot name')
        exact(row,('instruction','feature_count','output_count'),'no executable provider grammar')
        need(type(row['instruction'])is str and len(row['instruction'].encode())<=8192,'fixed bounded literal prompt')
        integer(row['feature_count'],1,4096);integer(row['output_count'],1,4096)
    return value

def case(request,b):
    from views import admit_view
    from numeric_io import load_case
    row=request['case'];raw,_=capture('/inputs/case/VIEW.json',row['pin'],request['limits']['metadata_bytes'],b,readonly=True)
    view=admit_view(parse(raw),row['world'],row['person'])
    return {'schema':'neural042_actor_packet_v1','world':view['world'],'person':view['person'],'sessions':view['sessions'],
            'channels':load_case(view,'/inputs/case',b,request['limits']),'lineage':request['lineage']},view

def tools(request,b):
    need(request['tool']in('T0','T1'),'tool condition')
    if request['tool']=='T0':return None
    import pac_tool
    return pac_tool.Tool(b,request['tool_elements'])

def source(request,b):
    raw,_=capture('/inputs/method.py',request['method']['source'],request['source_bytes'],b,readonly=True)
    code=compile(raw,'/inputs/method.py','exec',dont_inherit=True);b.tick()
    ns={'__name__':'_neural042_admitted_method','__file__':'/inputs/method.py'};exec(code,ns);b.tick();return ns

def out(name,value,request,b):
    raw=encoded(value);need(len(raw)<=request['output_caps'][name],'complete bounded output')
    return publish(Path('/output')/name,raw,b,readonly=True)

def finish(request,context,b,outputs,extra=None):
    value={'schema':'neural042_worker_receipt_v1','operation':request['operation'],'request':context['request'],
           'worker':request['worker'],'source_manifest':context['source_manifest'],'original_origin':b.origin,
           'deadline':b.deadline,'outputs':outputs,'observed_end':b.tick(),'logical_budget_before_receipt':b.record(),
           'source_accounting':context['source_read_reserved'],'rng':{'seed':request['seed'],'identity':request['seed_identity'],'contract':request['rng_contract']},'extra':extra}
    out('RECEIPT.json',value,request,b);b.tick();return value
