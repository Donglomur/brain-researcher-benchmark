"""Actual native dispatch and fixed two-file output transport."""
from pathlib import Path
from core import need, encoded, pin, publish
from bundle import pack


def run(request,budget,frozen):
    need(request.get('schema')=='neural058_native_envelope_v1' and request.get('task')=='NEURAL-058','fixed native envelope')
    need(request['source']==frozen['pin'],'native exact captured source')
    from native_reader import versions
    versions({'numpy':'2.2.6','scipy':'1.15.3','scikit-learn':'1.7.2','torch':'2.10.0','torch-brain':'0.2.0a0'})
    inner=request['request']
    need(inner['output_root']=='/scratch/result','fixed native scratch product namespace')
    if request['producer']=='reference':
        from reference_worker import run as produce
    elif request['producer']=='candidate':
        from candidate_worker import run as produce
    else: raise ValueError('literal native producer')
    result=produce(inner,budget)
    need(result['path']=='RESULT.json','complete actual native result')
    archive=pack('/scratch/result','/output/RESULT.n058',budget,request['bundle_limits'])
    terminal={'schema':'neural058_native_terminal_v1','task':'NEURAL-058','request':pin(encoded(request)),
              'producer':request['producer'],'result':result,'bundle':archive,
              'source':frozen['pin'],'budget_before_publication':budget.record()}
    out=publish('/output/TERMINAL.json',encoded(terminal),budget,readonly=True)
    budget.tick();return {'bundle':archive,'terminal':out}
