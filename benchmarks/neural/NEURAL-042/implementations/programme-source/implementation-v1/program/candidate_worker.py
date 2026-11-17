"""Actual arbitrary authored Python solve; postseal provider inputs are numeric."""
from core import need,finite
from contracts import exact,person_rows
from worker_common import start,case,tools,source,recipe,out,finish

def run(request,context):
    b=start(request,context);packet,view=case(request,b);packet['rng_seed']=request['seed'];tool=tools(request,b)
    rec=recipe(request['recipe']);ns=source(request,b);outputs={}
    if request['worker']=='candidate_features':
        value=ns['prepare_provider'](packet,tool);need(type(value)is dict and set(value)==set(rec['provider_slots']),'exact frozen slots')
        for name,items in value.items():
            need(type(items)is list and len(items)<=rec['provider_slots'][name]['feature_count'],'bounded finite feature vectors')
            value[name]=[finite(x)for x in items]
        outputs['FEATURES.json']=out('FEATURES.json',value,request,b)
    else:
        need(request['worker']=='candidate','exact source-owned method endpoint')
        vals=request['provider_values'];need(type(vals)is dict and set(vals)==set(rec['provider_slots']),'all fixed responses')
        for name,items in vals.items():
            need(type(items)is list and len(items)==rec['provider_slots'][name]['output_count'],'fixed response axis');vals[name]=[finite(x)for x in items]
        value=ns['solve'](packet,tool,vals);exact(value,('rows','reasoning'),'full canonical solve result')
        person_rows(value['rows'],packet['person']);need(type(value['reasoning'])is dict,'structured ungraded scientific reasoning')
        outputs['RESULT.json']=out('RESULT.json',value,request,b)
    b.tick();return finish(request,context,b,outputs,{'case':request['case'],'method':request['method'],'tool_trace_is_candidate_influenced':True})
