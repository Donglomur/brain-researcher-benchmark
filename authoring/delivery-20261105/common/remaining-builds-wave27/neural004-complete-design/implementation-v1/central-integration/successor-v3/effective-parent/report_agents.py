"""Fresh post-prediction reconstruction and explanation actor contexts."""
from .common import need,fields,encode,decode,pin,body_pin
from .execution import minimized_view
from .physical.investigator_wire import build_request,send_https
from .failures import describe

REPORT_TOOLS=[{'type':'function','function':{'name':'revise','description':'Write Python defining analyze(training,query,state), train(training,query), and reconstruct(training,query,state). P must seal before held data; I may inspect full admitted reconstruction data.','parameters':{'type':'object','properties':{'source':{'type':'string'}},'required':['source'],'additionalProperties':False}}},
 {'type':'function','function':{'name':'execute','description':'Run actual source analysis/training/reconstruction; private reference reports are unavailable.','parameters':{'type':'object','properties':{'action':{'enum':['analyze','train','reconstruct']}},'required':['action'],'additionalProperties':False}}},
 {'type':'function','function':{'name':'seal','description':'Seal P source/state before held access and execute reconstruction, or close I executed reconstruction result.','parameters':{'type':'object','properties':{},'additionalProperties':False}}}]

def reconstruction(engine,context,mode,held_person,training_body,query_body,policy,global_source,deployment_path,deployment_pin,credential,exposure_pin,release):
    need(release is not None,'all prediction contexts closed before reconstruction evidence')
    need(body_pin(global_source)=={k:policy['source'][k] for k in ('bytes','sha256')},'committed reconstruction policy')
    limits=policy['limits'];ledger=engine.ledger;traces=[];source=None;state=None;returned=None;calls=0;tools=0;held_open=mode=='I';sealed_method=None
    training=engine.bodies.put(context+'-training.json',training_body);query=engine.bodies.put(context+'-query.json',query_body)
    messages=[{'role':'system','content':global_source.decode()}, {'role':'user','content':encode({'question':policy['question'],'task':'reconstruction','mode':mode,'held_person':held_person,
        'status':'retrospective declared extension, not whole-paper replication','expected_output':'one original protocol person record with all114 metrics; retain complete numerical support and fitted state'},limits['request_bytes']).decode()}]
    def execute(action):
        nonlocal state,returned,tools
        need(source is not None and tools<limits['tools'],'retained source and tool bound');tools+=1
        need(not(mode=='P' and held_open) or action=='reconstruct','P no authoring/training after held')
        job=context+'-tool-'+str(tools)
        request={'schema':'neural004_candidate_job_v1','job_id':job,'action':action,'code_pin':body_pin(source),
            'training_pin':body_pin(training_body),'query_pin':body_pin(query_body) if held_open else None,
            'state_pin':None if state is None else {k:state[k] for k in ('bytes','sha256')},
            'limits':{'source_bytes':limits['source_bytes'],'view_bytes':limits['view_bytes'],'state_bytes':limits['state_bytes'],'output_bytes':limits['output_bytes']}}
        mounts={'/training/view.json':training}
        if held_open:mounts['/query/view.json']=query
        if state is not None:mounts['/sealed/state.json']=state
        files={'/source/candidate_worker.py':engine.worker_source,'/program/generated.py':source,'/request/job.json':encode(request,limits['request_bytes'])}
        result=engine.transport.run(job,job,files,minimized_view(mounts,exposure_pin),[engine.python,'-I','-B','/source/candidate_worker.py','/request/job.json',str(limits['request_bytes'])],action)
        execution=decode(result['outputs']['EXECUTION.json'],limits['output_bytes'])
        need(execution['request_pin']==body_pin(files['/request/job.json']) and execution['code_pin']==body_pin(source),'actual reconstruction computation source')
        traces.append({'action':action,'execution':execution,'process':result['record']})
        if execution['candidate_status']=='failed':return {'status':'failed','error':execution['error']}
        raw=result['outputs']['RESULT.json'];value=decode(raw,limits['output_bytes'])
        descriptor=engine.bodies.put(job+'-result.json',raw)
        if action=='train':need(len(raw)<=limits['state_bytes'],'state extent');state=descriptor;returned=None
        if action=='reconstruct':
            need(held_open and value['person']==held_person,'same full held reconstruction person');returned={'value':value,'descriptor':descriptor,'process':result['record']}
        return {'status':'returned','value':value if action=='analyze' else None,'artifact':descriptor}
    try:
        while calls<limits['provider_calls']:
            need(not(mode=='P' and held_open),'P no post-held provider access');calls+=1
            wire=dict(policy['wire_limits']);wire['max_calls']=ledger.limits['provider_calls']
            request=build_request(policy['provider'],messages,REPORT_TOOLS,wire)
            rq=engine.bodies.put(context+'-request-'+str(calls)+'.json',request['body']);traces.append({'provider_request':rq,'status':'attempted'})
            response=send_https(request,policy['provider'],deployment_path,deployment_pin,ledger,credential)
            rp=engine.bodies.put(context+'-response-'+str(calls)+'.json',response['raw_response'])
            traces.append({'provider_request':rq,'provider_response':rp,'usage':response['usage']})
            messages.append(decode(response['raw_response'],wire['max_response_bytes'])['choices'][0]['message'])
            need(response['actions'],'reconstruction context lacks complete seal')
            for action_index,action in enumerate(response['actions']):
                args=action['arguments']
                if action['name']=='revise':
                    fields(args,('source',));need(type(args['source']) is str,'source text');source=args['source'].encode();need(0<len(source)<=limits['source_bytes'],'source extent')
                    ledger.reserve({'generated_source_bytes':len(source)},'cumulative reconstruction source revisions')
                    descriptor=engine.bodies.put(context+'-source-'+str(len(traces))+'.py',source);traces.append({'revision':descriptor});state=None;returned=None;answer={'source':descriptor}
                elif action['name']=='execute':fields(args,('action',));need(args['action'] in ('analyze','train','reconstruct'),'fixed report action');answer=execute(args['action'])
                else:
                    need(action['name']=='seal' and not args and action_index==len(response['actions'])-1,'seal must be final report action')
                    if mode=='P':
                        need(source is not None and state is not None,'pre-held P method/state required');sealed_method=pin({'source':body_pin(source),'state':state,'history':traces},8*1048576);held_open=True;execute('reconstruct')
                    need(returned is not None,'actual complete returned reconstruction')
                    return {'context':context,'mode':mode,'held':held_person,'status':'sealed','person_record':returned['value'],
                        'seal':pin({'artifact':returned['descriptor'],'source':body_pin(source),'state':state,'method':sealed_method,'history':traces},8*1048576),
                        'traces':traces,'execution_qualified':False}
                messages.append({'role':'tool','tool_call_id':action['id'],'content':encode(answer,limits['output_bytes']).decode()})
        raise ValueError('reconstruction provider-call limit exhausted')
    except BaseException as error:
        error.neural004_report_failure={'context':context,'mode':mode,'held':held_person,'status':'failed','traces':traces,
            'failure':describe(error,policy['wire_limits']['max_response_bytes'])};raise

def explanation(engine,context,policy,evidence,global_source,deployment_path,deployment_pin,credential,release):
    need(release is not None,'postseal explanation only');limits=policy['limits']
    need(body_pin(global_source)=={k:policy['source'][k] for k in ('bytes','sha256')},'same policy source for fresh explanation context')
    messages=[{'role':'system','content':global_source.decode()}, {'role':'user','content':encode({'task':'scientific reasoning','rubric_dimensions':6,
        'instructions':'Use this identical completed evidence packet. Link claims to artifact, field, support and units. Distinguish observed contrast, RT-conditioned evidence and latent model assumptions. Propose a discriminating next analysis; do not revise sealed results.',
        'evidence':evidence},limits['request_bytes']).decode()}]
    wire=dict(policy['wire_limits']);wire['max_calls']=engine.ledger.limits['provider_calls']
    request=build_request(policy['provider'],messages,[],wire)
    rq=engine.bodies.put(context+'-request.json',request['body'])
    response=send_https(request,policy['provider'],deployment_path,deployment_pin,engine.ledger,credential)
    need(response['finished']=='stop' and not response['actions'] and response['analysis'],'complete literal scientific report')
    rp=engine.bodies.put(context+'-response.json',response['raw_response'])
    report={'text':response['analysis'],'evidence_pin':pin(evidence,limits['request_bytes']),'provider_request':rq,'provider_response':rp,
        'usage':response['usage'],'scientific_judgment_qualified':False}
    return {'context':context,'status':'sealed','report':report,'report_pin':pin(report,limits['output_bytes'])}
