"""Complete source-owned 36-person/44-session study; no finished-result callback."""
from pathlib import Path
from core import need,encoded,pin,parse,publish,fresh,capture,describe_sealed,cleanup_preserving
from contracts import projection,person_rows,report,CELLS
from artifacts import Artifacts
from engine import Engine
from journal import Journal
from provider import GlobalQuota
from transport import Transport
from investigator import Investigator
from schedule import schedule,disposition,cell_id

def raw_budget(b):
    return {'origin':b.origin,'deadline':b.deadline,'read_reserved':b.read_bytes,'write_reserved':b.write_bytes,'clock_snapshot_may_be_expired':True}

def run(a,captured,b):
    root=Path(a['roots']['output']);private=Path(a['roots']['private']);journal=None;events=[];current=None;results={};error_record=None
    pub=Artifacts(b,[a['roots']['source'],a['roots']['packet'],root],private,[a['roots']['secrets'],a['roots']['raw'],a['roots']['operator']])
    prv=Artifacts(b,[a['roots']['source'],a['roots']['packet'],private],a['roots']['secrets'],[a['roots']['raw'],a['roots']['operator']])
    proj=projection(pub.json(Path(a['roots']['packet'])/'PROJECTION.json',a['projection'],a['resources']['projection_bytes']))
    planned=schedule(proj['people']);authors={};case_results={};ref_results={};groups={};ref_groups={};operations=[]
    quota=GlobalQuota(a['resources']['whole_provider_calls'],a['resources']['whole_provider_tokens'],a['resources']['whole_provider_money'])
    engines={};t=None
    def record(value):
        need(journal is not None,'journal acquired before operational effects');journal.append(value);events.append(value)
    try:
        fresh(root,b)
        for parent in (root/'operations',root/'methods',Path(a['native_public']['output_root']),private/'operations',Path(a['native_private']['output_root'])):fresh(parent,b)
        journal=Journal(root/'JOURNAL.jsonl',b,a['resources']['journal_bytes'],a['resources']['journal_event_bytes'])
        record({'kind':'study_entered','source':captured['pin'],'selection':captured['authority_pin'],'projection':a['projection'],'original_origin':b.origin})
        engines={False:Engine(a['native_public'],b,record),True:Engine(a['native_private'],b,record)}
        t=Transport(a,captured,b,record,engines[False],engines[True],pub,prv)
        protocol=captured['files']['protocol/ACTOR_PROTOCOL.md'];need(pin(protocol)==a['preparation']['protocol'],'exact actor/source protocol')
        inv=Investigator(a,b,record,t,quota,protocol.decode())
        for phase in planned:
            current=phase['identity'];kind=phase['kind'];profile='author'if kind=='author'else('reference'if kind=='reference'else'group'if kind.endswith('group')else'f_case'if phase['cell'][0]=='F'else'i_case')
            start=b.tick();cutoff=min(b.deadline,start+a['phase_limits'][profile]['wall_seconds']);private_phase=kind.startswith('reference')
            eng=engines[private_phase];record({**phase,'kind':'phase_entered','phase_kind':phase['kind'],'entered_at':start,'cutoff':cutoff,'profile':profile});eng.begin_scope(current,cutoff,a['phase_limits'][profile])
            phase_ops=[]
            if kind=='author':
                method,analysis,_=inv.loop(current,phase['mode'],phase['tool'],profile,cutoff)
                # I source is a data-free instruction policy; it is never executed.
                if phase['mode']=='I':need(method['recipe_value']=={'provider_slots':{}},'I global policy has no frozen query slots')
                authors[(phase['mode'],phase['tool'])]=method;value={'method':method};phase_ops=analysis
            elif kind=='case':
                mode,world,tool=phase['cell'];p=phase['person']
                from views import case
                view=case(proj,world,p,a,pub);method=authors[(mode,tool)];provider=None
                if mode=='I':
                    policy=pub.capture(method['source']['path'],method['source']['pin'],a['resources']['candidate_source_bytes']).decode()
                    method,analysis,provider=inv.loop(current,mode,tool,profile,cutoff,view,policy);phase_ops.extend(analysis)
                row,ops=inv.solve(current,method,view,profile,cutoff,provider);phase_ops.extend(ops)
                result=t.json(row,'RESULT.json');person_rows(result['rows'],p);case_results[(cell_id(phase['cell']),p)]={**t.result(row,'RESULT.json'),'person':p}
                value={'method':method,'result':case_results[(cell_id(phase['cell']),p)],'view':view['pin']}
            elif kind=='reference':
                from views import case
                view=case(proj,phase['world'],phase['person'],a,prv)
                row=t.invoke(current+'/compute','reference_person',profile,cutoff,case=view,reference=phase['reference']);phase_ops=[row]
                # Never open numerical reference targets in the public host collector.
                ref_results[(phase['reference'],phase['world'],phase['person'])]={**t.result(row,'PERSON_EVENT.json'),'person':phase['person']}
                value={'person_event':ref_results[(phase['reference'],phase['world'],phase['person'])],'view':view['pin']}
            elif kind=='reference_group':
                persons=[ref_results[(phase['reference'],phase['world'],p)]for p in proj['people']]
                row=t.invoke(current+'/aggregate','reference_group',profile,cutoff,reference=phase['reference'],person_results=persons,people=proj['people'],world=phase['world']);phase_ops=[row]
                target=t.result(row,'REPORT.json');ref_groups[(phase['reference'],phase['world'])]=target;value={'target':target}
            else:
                key=cell_id(phase['cell']);persons=[case_results[(key,p)]for p in proj['people']]
                row=t.invoke(current+'/aggregate','aggregate',profile,cutoff,person_results=persons,people=proj['people']);phase_ops=[row]
                output=t.result(row,'REPORT.json');report(t.json(row,'REPORT.json'),proj['people']);groups[key]=output;value={'report':output}
            for row in phase_ops:operations.append(row)
            scope=eng.end_scope(current);results[current]={'phase':phase,'cutoff':cutoff,'value':value,'operations':[x['operation']for x in phase_ops],'scope':scope}
            record({'kind':'phase_completed','identity':current,'result':results[current],'observed_end':b.tick(cutoff)});current=None
        need(len(operations)==len(t.operations)and len(set(x['operation']for x in operations))==len(operations),'all actual operations retained')
        producer={'schema':'neural042_full_producer_v1','source':captured['pin'],'authority':captured['authority_pin'],'projection':a['projection'],
                  'original_origin':b.origin,'people':proj['people'],'phases':results,'operations':operations,
                  'reports':groups,'reference_targets':{r+'/'+w:d for(r,w),d in ref_groups.items()},
                  'provider_costs':quota.record(),'host_costs_before_final_publications':raw_budget(b),'disposition':disposition(planned,events)}
        record({'kind':'study_completed','phase_count':len(results),'native_count':len(operations),'observed_end':b.tick()})
        journal.close();journal=None
        jpin=describe_sealed(root/'JOURNAL.jsonl',a['resources']['journal_bytes'],b);producer['journal']={'path':str(root/'JOURNAL.jsonl'),'pin':jpin}
        raw=encoded(producer);need(len(raw)<=a['resources']['producer_bytes'],'complete producer metadata bound')
        p=publish(root/'PRODUCER.json',raw,b,readonly=True);b.tick();return {'status':'collected','producer':{'path':str(root/'PRODUCER.json'),'pin':p},'host_costs':raw_budget(b)}
    except BaseException as error:
        later=[]
        if current:
            try:record({'kind':'phase_failed','identity':current,'error':type(error).__name__})
            except BaseException as secondary:later.append(type(secondary).__name__)
        for eng in engines.values():
            try:eng.abort_scope()
            except BaseException as secondary:later.append(type(secondary).__name__)
        error_record={'status':'failed','error':type(error).__name__,'later':later,'source':captured['pin'],'phase':current,
                      'disposition':disposition(planned,events),'host_costs':raw_budget(b),'provider_costs':quota.record(),
                      'native_costs':{str(k):{'used_cpu':v.used_cpu,'reserved_cpu':v.reserved_cpu,'operations':v.operations}for k,v in engines.items()},
                      'early_setup_or_partial_tail_unknown':True,'no_retry':True}
        error.failure_record=error_record
        try:publish(root/'FAILED.json',encoded(error_record),b,readonly=True)
        except BaseException as secondary:error_record['failure_publication_error']=type(secondary).__name__
        raise
    finally:
        if journal is not None:cleanup_preserving(journal.close)
