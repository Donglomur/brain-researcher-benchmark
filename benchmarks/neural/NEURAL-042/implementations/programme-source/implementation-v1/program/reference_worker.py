"""One independently authored private reference, durable evidence before next()."""
import importlib,hashlib,os
from pathlib import Path
from core import need,capture,parse,encoded,pin,publish
from worker_common import start,case,out,finish
from contracts import person_rows,report
from journal import Journal

def run(request,context):
    b=start(request,context);name=request['reference'];need(name in('R1','R2'),'one selected independent reference')
    module=importlib.import_module('references.'+name.lower())
    rb=module.Budget(b.origin,b.deadline,request['reference_limits'])
    journal=None;events=0;result=None;failure=None
    try:
        journal=Journal('/output/EVIDENCE.jsonl',b,request['output_caps']['EVIDENCE.jsonl'],request['event_bytes'])
        if request['worker']=='reference_person':
            packet,_=case(request,b);packet['schema']='neural042_reference_person_v1'
            stream=module.evaluate_person(packet,rb)
        else:
            need(request['worker']=='reference_group','concrete complete reference endpoint')
            people=[]
            for row in request['person_results']:
                raw,_=capture('/inputs/people/'+row['person']+'.json',row['pin'],request['output_caps']['REPORT.json'],b,readonly=True)
                obj=parse(raw);people.append(obj)
            stream=module.aggregate_world(people,request['people'],request['world'],rb)
        try:
            for event in stream:
                b.tick();need(type(event)is dict and event.get('reference')==name,'independent producer event identity')
                journal.append(event);events+=1 # fsync completes BEFORE next(generator)
                if event['kind']=='person_result':result=event['payload'];person_event=event
                elif event['kind']=='world_result':result=event['payload']
        finally:
            close=getattr(stream,'close',None)
            if close is not None:close()
        need(result is not None,'complete reference terminal result required')
        if request['worker']=='reference_person':
            person_rows(result['rows'],request['case']['person']);outputs={'RESULT.json':out('RESULT.json',result,request,b),'PERSON_EVENT.json':out('PERSON_EVENT.json',person_event,request,b)}
        else:
            value=result.get('report',result);report(value,request['people']);outputs={'REPORT.json':out('REPORT.json',value,request,b)}
        journal.close();journal=None
        from core import describe_sealed
        outputs['EVIDENCE.jsonl']=describe_sealed('/output/EVIDENCE.jsonl',request['output_caps']['EVIDENCE.jsonl'],b)
        return finish(request,context,b,outputs,{'reference':name,'events':events,'reference_budget':rb.snapshot() if hasattr(rb,'snapshot') else rb.record()})
    except BaseException as error:
        failure={'error':type(error).__name__,'events_durable':events,'source':context['source_manifest'],'budget':rb.snapshot(),'unknown_unpublished_tail':True}
        error.reference_failure=failure;raise
    finally:
        if journal is not None:
            from core import cleanup_preserving
            cleanup_preserving(journal.close)
