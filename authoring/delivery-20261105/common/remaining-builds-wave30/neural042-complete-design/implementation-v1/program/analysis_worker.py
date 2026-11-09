"""Isolated actual author analysis; public packet only, never a report callback."""
from core import need,encoded
from worker_common import start,case,tools,source,out,finish

def run(request,context):
    b=start(request,context);packet=None
    if request['case']is not None:packet,_=case(request,b);packet['rng_seed']=request['seed']
    tool=tools(request,b);messages=[];used=0
    def emit(value):
        nonlocal used
        raw=encoded(value);need(used+len(raw)<=request['feedback_bytes'],'bounded case-local analysis feedback')
        used+=len(raw);messages.append(value);b.tick()
    # This execution capability is confined to I or data-free authoring, never
    # a postseal F provider-produced body. Container capabilities enforce views.
    from core import capture
    raw,_=capture('/inputs/method.py',request['method']['source'],request['source_bytes'],b,readonly=True)
    ns={'__name__':'_neural042_analysis','packet':packet,'tools':tool,'emit':emit}
    exec(compile(raw,'/inputs/method.py','exec',dont_inherit=True),ns);b.tick()
    outputs={'FEEDBACK.json':out('FEEDBACK.json',{'messages':messages},request,b)}
    return finish(request,context,b,outputs,{'case':request['case'],'candidate_influenced_feedback':True})
