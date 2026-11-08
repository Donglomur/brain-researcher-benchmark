"""Actual research-agent loop: source revisions, analysis, fits and predictions."""
import base64
from .common import (need,fields,encode,decode,pin,body_pin,check_pin,integer,
    probability,same_roster)
from .policies import History
from .execution import JobTransport,minimized_view
from .physical.investigator_wire import build_request,send_https,image_part
from .failures import describe,safe

TOOLS=[{'type':'function','function':{'name':'revise','description':'Write a complete Python module with train(training, query), predict(state, query), and optional analyze(training, query, state). Training rows have contrast labels. P training query is None. All source and fitted state are retained.','parameters':{'type':'object','properties':{'source':{'type':'string'}},'required':['source'],'additionalProperties':False}}},
 {'type':'function','function':{'name':'execute','description':'Execute the current source in an isolated process. analyze returns evidence; train creates safe JSON state; predict uses the current state. No reference or held-target feedback is available.','parameters':{'type':'object','properties':{'action':{'enum':['analyze','train','predict']}},'required':['action'],'additionalProperties':False}}},
 {'type':'function','function':{'name':'seal','description':'P seals its source/state before held access and automatically predicts with that procedure. I seals its last complete executed forecast. No result may be revised after sealing.','parameters':{'type':'object','properties':{},'additionalProperties':False}}}]

def forecast_rows(value,expected):
    need(type(value) is list,'complete forecast list');out=[]
    for row in value:
        fields(row,('id','prediction'));out.append({'id':row['id'],'prediction':probability(row['prediction'])})
    same_roster([r['id'] for r in out],expected)
    by_id={r['id']:r for r in out};return [by_id[k] for k in expected]

class Investigator:
    def __init__(self,transport,bodies,ledger,worker_source,worker_pin,python_path,source_pin):
        need(type(transport) is JobTransport,'actual source-owned transport');need(body_pin(worker_source)==worker_pin,'fixed worker source')
        need(type(python_path) is str and python_path.startswith('/'),'admitted fixed runtime Python')
        self.transport=transport;self.bodies=bodies;self.ledger=ledger;self.worker_source=worker_source;self.worker_pin=worker_pin
        self.python=python_path;self.source_pin=source_pin
    def run(self,packet,policy,global_source,deployment_path,deployment_pin,authorization_header,exposure_pin):
        context=packet['private_context'];limits=policy['limits'];mode=context['mode'];view=context['view'];key=context['context']
        need(body_pin(global_source)=={k:policy['source'][k] for k in ('bytes','sha256')},'same committed global policy source')
        history=History(key,mode,view,pin(policy,4*1048576),context['training_pin'],context['held_pin'],self.ledger,limits)
        train_d=self.bodies.put(key+'-training.json',packet['training_body']);held_d=self.bodies.put(key+'-held.json',packet['held_body'])
        code=None;state_d=None;last_prediction=None;traces=[];images={}
        messages=[{'role':'system','content':global_source.decode('utf-8')},
            {'role':'user','content':encode({'question':policy['question'],'mode':mode,'view':view,'context':key,
                'training_rows':len(context['training_ids']),'held_rows':len(context['held_ids']),
                'retrospective':True,'paper_informed':True,'tools':policy['capabilities'],
                'training_schema':'rows:{id,person,rt,instruction,samples,contrast[,waveform]}; hmp only H/EH',
                'held_schema':'same without contrast; original identities/aliases never available',
                'code_entrypoints':{'train':'train(training, query_or_None) -> safe JSON state','predict':'predict(state, query) -> [{id,prediction}]','analyze':'analyze(training,query_or_None,state_or_None) -> safe JSON evidence'},
                'reference_feedback':False},limits['request_bytes']).decode('ascii')}]
        if mode=='I':history.open_held()
        def execute(action):
            nonlocal state_d,last_prediction
            history.tool(action);serial=history.tools;job=key+'-tool-'+str(serial)
            query_d=held_d if history.held_open else None
            request={'schema':'neural004_candidate_job_v1','job_id':job,'action':action,
                'code_pin':history.current,'training_pin':context['training_pin'],
                'query_pin':context['held_pin'] if query_d else None,'state_pin':None if state_d is None else {k:state_d[k] for k in ('bytes','sha256')},
                'limits':{'source_bytes':limits['source_bytes'],'view_bytes':limits['view_bytes'],'state_bytes':limits['state_bytes'],'output_bytes':limits['output_bytes']}}
            materials={'/training/view.json':train_d}
            if query_d is not None:materials['/query/view.json']=query_d
            if state_d is not None:materials['/sealed/state.json']=state_d
            files={'/source/candidate_worker.py':self.worker_source,'/program/generated.py':code,
                '/request/job.json':encode(request,limits['request_bytes'])}
            result=self.transport.run(job,job,files,minimized_view(materials,exposure_pin),
                [self.python,'-I','-B','/source/candidate_worker.py','/request/job.json',str(limits['request_bytes'])],action)
            execution=decode(result['outputs']['EXECUTION.json'],limits['output_bytes'])
            need(execution['job_id']==job and execution['action']==action and execution['code_pin']==history.current and
                 execution['training_pin']==context['training_pin'] and execution['query_pin']==request['query_pin'] and execution['state_pin']==request['state_pin'] and
                 execution['request_pin']==body_pin(files['/request/job.json']),'same source/state/view returned computation')
            traces.append({'execution':execution,'process':result['record']})
            history.record('tool_closure',{'execution_pin':pin(execution),'process_pin':pin(result['record'])})
            if execution['candidate_status']=='failed':
                return {'status':'failed','error':execution['error']}
            need(execution['candidate_status']=='returned' and 'RESULT.json' in result['outputs'],'actual returned artifact')
            raw=result['outputs']['RESULT.json'];value=decode(raw,limits['output_bytes'])
            if action=='train':
                need(len(raw)<=limits['state_bytes'],'complete fitted state cap');state_d=self.bodies.put(job+'-state.json',raw)
                history.fitted(body_pin(raw),result['record']);last_prediction=None
                return {'status':'fitted','state_pin':body_pin(raw),'bytes':len(raw)}
            if action=='predict':
                rows=forecast_rows(value,context['held_ids']);raw=encode(rows,limits['output_bytes'])
                descriptor=self.bodies.put(job+'-forecast.json',raw)
                last_prediction={'rows':rows,'descriptor':descriptor,'record':result['record'],'source_pin':history.current,'state_pin':history.state['pin']}
                return {'status':'forecast_sealed_pending_finish','rows':len(rows)}
            return {'status':'analysis','evidence':value,'provenance_pin':pin(result['record'])}
        try:
            while not history.closed:
                history.provider_call()
                wire_limits=dict(policy['wire_limits']);wire_limits['max_calls']=self.ledger.limits['provider_calls']
                # Per-context cap is enforced above; wire sees whole-study cap.
                request=build_request(policy['provider'],messages,TOOLS,wire_limits,image_sources=images)
                request_d=self.bodies.put(key+'-provider-request-'+str(history.calls)+'.json',request['body'])
                history.record('provider_request_retained',request_d)
                response=send_https(request,policy['provider'],deployment_path,deployment_pin,self.ledger,authorization_header)
                response_d=self.bodies.put(key+'-provider-response-'+str(history.calls)+'.json',response['raw_response'])
                history.record('provider_closure',{'request':request_d,'response':response_d,'usage':response['usage']})
                raw_reply=decode(response['raw_response'],wire_limits['max_response_bytes']);message=raw_reply['choices'][0]['message']
                messages.append(message)
                need(response['actions'],'provider stopped before complete source/fit/forecast seal')
                for action_index,action in enumerate(response['actions']):
                    need(not history.closed,'no extra action after seal');name=action['name'];args=action['arguments']
                    if name=='revise':
                        fields(args,('source',));need(type(args['source']) is str,'literal generated Python source')
                        code=args['source'].encode('utf-8');need(0<len(code)<=limits['source_bytes'],'complete generated source cap')
                        self.ledger.reserve({'generated_source_bytes':len(code)},'cumulative generated method revisions')
                        descriptor=self.bodies.put(key+'-revision-'+str(len(history.revisions))+'.py',code)
                        history.revise(body_pin(code));state_d=None;last_prediction=None
                        answer={'status':'source_retained','source_pin':body_pin(code)}
                    elif name=='execute':fields(args,('action',));answer=execute(args['action'])
                    else:
                        need(name=='seal' and not args and action_index==len(response['actions'])-1,'seal must be the final provider action')
                        if mode=='P':
                            history.seal_method();history.open_held();answer=execute('predict')
                        need(last_prediction is not None and last_prediction['source_pin']==history.current and last_prediction['state_pin']==history.state['pin'],'last executed forecast joins current fitted revision')
                        seal=history.seal_prediction({k:last_prediction['descriptor'][k] for k in ('bytes','sha256')},last_prediction['record'])
                        return {'schema':'neural004_actor_seal_v1','context':context,'policy_pin':pin(policy,4*1048576),
                            'seal':seal,'forecasts':last_prediction['rows'],'history':history.actions,'revisions':history.revisions,
                            'traces':traces,'status':'sealed','execution_qualified':False}
                    # Analysis can include admitted local figures without remote URLs.
                    if name=='execute' and answer.get('status')=='analysis' and type(answer.get('evidence')) is dict and 'images' in answer['evidence']:
                        image_rows=answer['evidence']['images'];need(type(image_rows) is list,'bounded actual analysis images')
                        parts=[{'type':'text','text':encode({k:v for k,v in answer.items() if k!='evidence'},limits['output_bytes']).decode()}]
                        for item in image_rows:
                            fields(item,('mime','base64'));need(len(item['base64'])<=4*((wire_limits['max_image_bytes']+2)//3),'image encoded extent')
                            raw=base64.b64decode(item['base64'],validate=True);source=body_pin(raw)
                            converted=image_part(raw,item['mime'],source,wire_limits)
                            images[source['sha256']]={'source_pin':source,'provenance_pin':answer['provenance_pin']};parts.append(converted['part'])
                        messages.append({'role':'tool','tool_call_id':action['id'],'content':parts})
                    else:messages.append({'role':'tool','tool_call_id':action['id'],'content':encode(answer,limits['output_bytes']).decode('ascii')})
            raise ValueError('unreachable actor closure')
        except BaseException as error:
            self.ledger.fail(key+'/actor',error)
            error.neural004_actor_failure={'context':context,'policy_pin':pin(policy,4*1048576),'history':history.actions,
                'revisions':history.revisions,'traces':traces,'status':'failed','type':type(error).__name__,
                'message':str(error)[:1024],'provider_failure':describe(error,policy['wire_limits']['max_response_bytes'])}
            raise
