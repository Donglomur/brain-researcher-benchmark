"""Fixed worker entry; no host scientific fallback, no target-mounted actor."""
import importlib.util,pickle
from pathlib import Path
from core import Budget,need,encoded,pin,parse,capture,publish
from actor_api import TrainingAPI,PredictionAPI
from schema import validate_prediction

def selected_module(request,budget):
    method=request['method'];raw,_=capture('/inputs/METHOD.py',method,request['limits']['source_bytes'],budget,readonly=True)
    # Executed only in the owned actor capsule. Module is not imported on host.
    import types
    module=types.ModuleType('participant_method');module.__file__='/inputs/METHOD.py'
    import sys
    sys.modules[module.__name__]=module
    exec(compile(raw,module.__file__,'exec',dont_inherit=True),module.__dict__)
    return module

def run(request):
    b=Budget(request['origin'],request['deadline'],request['limits']['read_bytes'],request['limits']['write_bytes'])
    raw,_=capture('/inputs/VIEW.json',request['view'],request['limits']['metadata_bytes'],b,readonly=True);view=parse(raw)
    need(view['protocol']==request['protocol'],'same frozen task protocol')
    module=selected_module(request,b);outputs={};stage=request['stage']
    if stage=='investigate':
        need(request['mode']=='case_adaptive_equal_inputs_tools_compute','case-adaptive authoring only')
        api=TrainingAPI(view,b,request['limits'],request['tool'],request['mode'])
        proposal=module.build(api,request['recipe']);b.tick()
        from schema import exact
        exact(proposal,('source','recipe','rationale'),'complete case-authored method')
        need(type(proposal['source'])is str and type(proposal['rationale'])is str,'source and rationale text')
        body=proposal['source'].encode();need(len(body)<=request['limits']['source_bytes'],'bounded case-authored code')
        import ast
        ast.parse(body,filename='METHOD.py')
        outputs['METHOD.py']=publish('/output/METHOD.py',body,b)
        outputs['RECIPE.json']=publish('/output/RECIPE.json',encoded(proposal['recipe']),b)
        outputs['RATIONALE.json']=publish('/output/RATIONALE.json',encoded({'rationale':proposal['rationale'],'training_events':api.events}),b)
    elif stage=='fit':
        api=TrainingAPI(view,b,request['limits'],request['tool'],request['mode'])
        state=module.fit(api,request['recipe']);b.tick()
        # Model objects stay inside the same untrusted capsule namespace. The
        # host only hashes opaque bytes and never imports/unpickles this state.
        raw=pickle.dumps(state,protocol=5);need(len(raw)<=request['limits']['model_bytes'],'bounded fitted model output')
        outputs['MODEL.bin']=publish('/output/MODEL.bin',raw,b)
        from reasoning import check
        explanation=check(module.describe(request['recipe']),request['method'],outputs['MODEL.bin'])
        outputs['REASONING.json']=publish('/output/REASONING.json',encoded(explanation),b)
        outputs['TRAINING.json']=publish('/output/TRAINING.json',encoded({'events':api.events,'tool_calls':api.calls,'held_inputs_present':False}),b)
    elif stage=='predict':
        raw,_=capture('/inputs/MODEL.bin',request['model'],request['limits']['model_bytes'],b,readonly=True)
        state=pickle.loads(raw);b.tick()
        api=PredictionAPI(view,b,request['limits'],request['tool']);result=module.predict(state,api,request['recipe']);b.tick()
        validate_prediction(result,[r['id'] for r in view['query']])
        outputs['PREDICTIONS.json']=publish('/output/PREDICTIONS.json',encoded(result),b)
    else:raise ValueError('unselected worker stage')
    end=b.tick();receipt={'schema':'n041_worker_receipt_v1','operation':request['operation'],'stage':stage,
        'source':request['source'],'request':request['request_identity'],'outputs':outputs,'origin':b.origin,'deadline':b.deadline,
        'observed_end':end,'logical_read_reserved':b.read_bytes,'logical_write_reserved':b.write_bytes,
        'native_costs_are_external':True}
    publish('/output/RECEIPT.json',encoded(receipt),b);return receipt
