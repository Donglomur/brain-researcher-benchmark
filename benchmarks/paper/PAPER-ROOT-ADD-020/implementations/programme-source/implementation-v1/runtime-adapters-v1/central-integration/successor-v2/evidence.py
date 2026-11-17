"""Actual private primitive evidence and independent metadata partition replay.

Only the already constructed host accountant transport is observed. Its concrete
delegate still performs every command. Worker payload bytes remain in their
original private artifacts; this journal retains their exact observed byte pin.
"""
import base64
import dataclasses

COUNTERS=('read_bytes','write_bytes','retained_bytes','live_bytes','cpu_ns','memory_peak_bytes')
LIFETIME=('read_bytes','write_bytes','retained_bytes','cpu_ns')

class Commands:
    def __init__(self,delegate,limit):self.delegate=delegate;self.limit=limit;self.rows=[];self.bytes=0
    def begin(self):self.rows=[];self.bytes=0
    def run(self,argv,**kwargs):
        try:result=self.delegate.run(argv,**kwargs)
        except BaseException as error:
            self.rows.append({'argv':list(argv),'transport_error':type(error).__name__});raise
        row=dataclasses.asdict(result)
        for name in ('stdout','stderr'):
            raw=row.pop(name);u.need(type(raw)is bytes,'typed actual accountant output')
            row[name+'_base64']=base64.b64encode(raw).decode()
        row['argv']=list(row['argv']);self.rows.append(row);self.bytes+=len(u.canonical(row))
        u.need(self.bytes<=self.limit,'complete actual phase accountant evidence bound exceeded')
        return result

def worker_value(context,phase_id,operation,e):
    value=dataclasses.asdict(e);payload=value.pop('payload')
    return {'context':context,'phase_id':phase_id,'operation':operation,'closure':value,'payload_pin':u.pin(payload)}

def capture(bound,phase,commands,compact_start):
    host=bound.monitor.host;record=host.records.get(phase['id'],{})
    close=record.get('close');whole=bound.monitor.whole_observation if phase['kind']=='independent_full_process_and_resource_closure'else None
    return {'schema':'paper020_actual_phase_evidence_v2','host_identity':dict(host.identity),
      'phase_nonce':record.get('nonce'),'open':record.get('open'),
      'host_close':dataclasses.asdict(close)if close is not None else None,
      'whole_close':dataclasses.asdict(whole)if whole is not None else None,
      'commands':list(commands.rows),'compact_commands':list(host.commands[compact_start:]),
      'workers':[worker_value(*job)for job in bound.runtime.jobs if job[1]==phase['id']],
      'pending':[{'context':context,'operation':value['operation'],'input_digest':value['input_digest'],
                  'source_digest':value['source_digest'],'actual_model_digest':value.get('actual_model_digest'),
                  'worker_closure_digest':worker_commitment(dataclasses.asdict(value['closure']))}
                 for (context,pid),value in bound.runtime.pending.items()if pid==phase['id']],
      'known_failure_types':list(host.failures),'runtime_failed':bound.runtime.failure,
      'known_last_host_counters':dict(host.last_counters)}

def worker_commitment(e):
    keys=('container_id','nonce','binding_digest','origin_ns','deadline_ns','finished_ns','payload_digest',
          'source_digest','input_digest','model_digest','evidence_digests','natural_complete','all_descendants_closed','exit_code','failures')
    return u.sha(u.canonical({k:e[k]for k in keys}))

def compact_command(row):
    stdout=base64.b64decode(row['stdout_base64'],validate=True);stderr=base64.b64decode(row['stderr_base64'],validate=True)
    return {'action':row['argv'][1],'argv_digest':u.sha(u.canonical(row['argv'])),'stdout_sha256':u.sha(stdout),'stdout_bytes':len(stdout),
            'stderr_sha256':u.sha(stderr),'stderr_bytes':len(stderr),**{k:row[k]for k in
             ('started_ns','finished_ns','returncode','timed_out','interrupted','forced','truncated')}}

def _workers(items,phase,binding,document):
    found={}
    for item in items:
        e=item['closure'];cid=e['container_id']
        u.need(type(item)is dict and set(item)=={'context','phase_id','operation','closure','payload_pin'}
               and item['phase_id']==phase['id']==e['phase_id'] and e['binding_digest']==binding
               and e['implementation_digest']==document['scientific_source_digest'] and cid not in found,
               'exact distinct actual worker/source/phase closure')
        u.need(e['origin_ns']==document['origin_ns'] and e['deadline_ns']==document['deadline_ns']
               and type(e['finished_ns'])is int and document['origin_ns']<=e['finished_ns']<document['deadline_ns']
               and e['natural_complete']is True and e['all_descendants_closed']is True
               and type(e['exit_code'])is int and e['exit_code']==0 and not e['failures']
               and e['view_isolation_verified']is True and e['source_seal_unchanged']is True,'actual worker closure failed')
        for key in ('container_id','source_digest','input_digest','payload_digest'):u.only_pin({'bytes':0,'sha256':e[key]})
        role='native'if item['operation']=='literal_native'else'reference'if phase['actor']=='reference'else'candidate'
        u.need(e['source_digest']==document['images'][role]['source_digest'],'actual qualified image/source differs')
        u.need(u.only_pin(item['payload_pin'])['sha256']==e['payload_digest'],'observed raw output pin differs')
        found[cid]={'closure':e,'commitment':worker_commitment(e),'context':item['context'],'operation':item['operation']}
    if phase['kind']in ('fit','predict','reproduction'):u.need(found,'scientific phase has no actual isolated worker')
    else:u.need(not found,'unplanned scientific worker')
    return found

def _partition(response,workers,trace_cap):
    records=response.get('excluded_workers');u.need(type(records)is list and len(records)==len(workers),'complete exact raw worker partition')
    resources={};commits={}
    for item in records:
        u.need(type(item)is dict and set(item)=={'container_id','worker_closure_digest','counter_record_base64'},'exact worker partition record')
        cid=item['container_id'];u.need(cid in workers and cid not in resources,'unknown/repeated worker partition')
        worker=workers[cid];e=worker['closure'];raw=base64.b64decode(item['counter_record_base64'],validate=True)
        u.need(len(raw)<=trace_cap and item['worker_closure_digest']==worker['commitment']
               and u.sha(raw)==e['evidence_digests']['counters'],'actual worker raw counter/source commitment')
        value=u.parse(raw)
        u.need(value.get('container_id')==cid and value.get('nonce')==e['nonce']
               and value.get('accounting_complete')is True and value.get('all_tasks_exited')is True
               and value.get('trace_lost')is False and value.get('forced_termination')is False,'complete actual worker accounting required')
        resources[cid]={k:value[k]for k in COUNTERS}
        for v in resources[cid].values():u.need(type(v)is int and v>=0,'typed worker counters')
        commits[cid]=worker['commitment']
    return resources,commits

class Replay:
    def __init__(self,document,host_identity):
        self.d=document;self.host_identity=host_identity;self.consumed={k:0 for k in COUNTERS};self.high={k:0 for k in COUNTERS}
        self.accounted=document['origin_ns'];self.workers={};self.phase_nonces={};self.phase_observations={};self.commands=[]
        self.phase_count=0;self.whole=None
        self.context_outputs={};self.fit_contexts={}
    def phase(self,row):
        p=row['phase'];b=row['binding'];actual=row['actual_evidence'];compact=row['observation'];artifact=row['result']['artifact'];d=self.d
        u.need(type(actual)is dict and set(actual)=={'schema','host_identity','phase_nonce','open','host_close','whole_close','commands','compact_commands',
                   'workers','pending','known_failure_types','runtime_failed','known_last_host_counters'}
               and actual['schema']=='paper020_actual_phase_evidence_v2' and actual['host_identity']==self.host_identity
               and not actual['known_failure_types'] and actual['runtime_failed']is False,'complete actual private phase evidence required')
        u.need(p['id']not in self.phase_nonces and actual['phase_nonce']not in self.phase_nonces.values(),'unique actual phase nonce')
        self.phase_nonces[p['id']]=actual['phase_nonce'];workers=_workers(actual['workers'],p,b,d)
        u.need(not(set(workers)&set(self.workers)),'a worker was reused across phases')
        actions=['host-phase-open','host-whole-close','host-phase-seal']if p['kind']=='independent_full_process_and_resource_closure'else['host-phase-open','host-phase-seal']
        commands=actual['commands'];u.need(len(commands)==len(actions),'exact complete actual host command sequence')
        derived=[compact_command(c)for c in commands]
        u.need(derived==actual['compact_commands'],'compact accountant command commitments differ')
        closes={}
        for command,action,command_meta in zip(commands,actions,derived):
            response=self._command(command,action,p,b,actual,workers)
            self.commands.append(command_meta)
            if action=='host-phase-open':
                u.need(actual['open']=={'sha256':command_meta['stdout_sha256'],'finished_ns':command['finished_ns']}
                       and response.get('output_seals')=={} and response.get('excluded_workers')==[],'actual open snapshot differs')
            else:
                expected_workers=self.workers if action=='host-whole-close'else workers
                observed=actual['whole_close']if action=='host-whole-close'else actual['host_close']
                self._close(observed,response,command_meta,expected_workers,action,p,b,artifact)
                closes[action]=observed
        host=closes['host-phase-seal'];u.need(u.sha(u.canonical(host))==compact['host_observation_digest'],'unchanged actual host commitment differs')
        u.need(host['finished_ns']==compact['finished_ns'] and actual['known_last_host_counters']==self.consumed,'exact actual phase clock/counter high-water mark')
        for key in ('read_bytes','write_bytes','retained_bytes','live_bytes'):
            values=[r[key]for r in host['worker_resources'].values()]
            combined=host['resources'][key]+(max(values,default=0)if key=='live_bytes'else sum(values))
            u.need(compact[key]==combined,'compact resource amount does not derive from actual distinct partitions')
        for worker in workers.values():
            e=worker['closure']
            if p['kind']=='fit':u.need(e['input_digest']==artifact['input_digest'],'actual fit source input differs')
            if p['kind']=='predict':u.need(e['model_digest']==artifact['model_digest'],'actual inference changed fitted model')
        if workers:
            u.need(type(actual['pending'])is list and len(actual['pending'])==1,'one actual final scientific operation per phase')
            pending=actual['pending'][0];last=actual['workers'][-1];w=last['closure']
            u.need(pending['context']==last['context'] and pending['operation']==last['operation']
                   and pending['input_digest']==w['input_digest'] and pending['worker_closure_digest']==worker_commitment(w),
                   'actual final runtime operation/input/worker join differs')
            u.only_pin({'bytes':0,'sha256':pending['source_digest']})
            if p['kind']in ('fit','reproduction'):
                u.need(pending['context']==self.context_outputs.get(p['dependencies'][0]),'actual worker crossed the fresh scientific context')
            if p['kind']=='predict':
                u.need(pending['context']==artifact['context']==self.fit_contexts.get(p['id'].replace('predict/','fit/',1)),
                       'actual prediction crossed its independently closed fit context')
            if p['kind']=='reproduction':u.need(pending['context']==artifact['context'],'actual native output context differs')
            if p['actor']=='reference':u.need(pending['source_digest']==d['scientific_source_digest'],'actual fixed reference source differs')
            if p['kind']=='fit':
                u.need(pending['operation']==('nested_reference_fit'if p['actor']=='reference'else'fit'),'actual final fit operation differs')
                if p['actor']!='reference':u.need(pending['actual_model_digest']==artifact['model_digest'],'actual candidate frozen model differs')
                receipt={'natural_complete':True,'all_descendants_closed':True,'exit_code':0,'model_digest':artifact['model_digest'],
                         'input_digest':artifact['input_digest'],'binding_digest':b,'container_id':w['container_id'],
                         'output_digest':w['payload_digest'],'source_digest':pending['source_digest'],'finished_ns':w['finished_ns'],
                         'evidence_digests':w['evidence_digests']}
                u.need(u.scientific_digest(receipt)==artifact['fit_receipt_digest'],'actual source/input/output fit closure receipt differs')
                self.fit_contexts[p['id']]=pending['context']
        else:u.need(actual['pending']==[],'unplanned pending scientific operation')
        if p['kind']in ('fresh_native_context','fresh_training_context'):self.context_outputs[p['id']]=artifact['context']
        self.workers.update(workers);self.phase_observations[p['id']]=host;self.phase_count+=1
    def _command(self,c,action,p,b,actual,phase_workers):
        d=self.d;q=d['host_accounting'];origin,deadline=d['origin_ns'],d['deadline_ns'];argv=c.get('argv')
        u.need(type(c)is dict and set(c)=={'argv','returncode','stdout_base64','stderr_base64','started_ns','finished_ns','timed_out','interrupted','forced','truncated'}
               and type(argv)is list and len(argv)==4 and argv[:3]==[q['process']['accountant']['path'],action,'--request-base64'],
               'exact actual accountant argv and command result')
        reqraw=base64.b64decode(argv[3],validate=True);u.need(len(argv[3])<=120000,'accountant argv bound');request=u.parse(reqraw)
        raw=base64.b64decode(c['stdout_base64'],validate=True);err=base64.b64decode(c['stderr_base64'],validate=True)
        u.need(len(raw)<=q['trace_bytes'] and len(err)<=min(q['trace_bytes'],65536)
               and type(c['returncode'])is int and c['returncode']==0
               and all(c[k]is False for k in ('timed_out','interrupted','forced','truncated'))
               and type(c['started_ns'])is int and type(c['finished_ns'])is int and origin<=c['started_ns']<=c['finished_ns']<deadline,
               'actual command failed/unknown/late')
        response=u.parse(raw)
        u.need(response.get('schema')=='paper020_host_primitive_snapshot_v1' and response.get('action')==action
               and request.get('schema')=='paper020_host_account_request_v1'
               and response.get('request_digest')==u.sha(u.canonical(request)),'actual primitive/request digest differs')
        for key,value in {'host_identity':self.host_identity,'origin_ns':origin,'deadline_ns':deadline,
                          'accounting_scope_digest':q['accounting_scope_digest']}.items():
            u.need(request.get(key)==response.get(key)==value,'actual primitive identity/original clock/scope differs')
        u.need(request.get('implementation_digest')==d['scientific_source_digest'] and request.get('programme_digest')==d['programme_digest']
               and request.get('binding_digest')==b,'actual source/programme/binding request differs')
        nonce=request.get('nonce');u.need(type(nonce)is str and len(nonce)==48 and response.get('nonce')==nonce,'actual nonce join')
        if action!='host-whole-close':u.need(request.get('phase_id')==p['id'] and nonce==actual['phase_nonce'],'actual phase nonce differs')
        else:
            u.need(request.get('phase_id')=='whole-host-close' and nonce not in self.phase_nonces.values()
                   and request.get('owned_phases_digest')==u.sha(u.canonical(self.phase_nonces))
                   and request.get('owned_phase_count')==len(self.phase_nonces)
                   and request.get('expected_worker_count')==len(self.workers)
                   and request.get('expected_worker_closures_digest')==u.sha(u.canonical({k:v['commitment']for k,v in self.workers.items()})),
                   'actual whole-host phase/worker registry differs')
        u.need(response.get('scope')=='owned_host_tree_excluding_exact_worker_container_cgroups' and response.get('host_alive')is True
               and response.get('coverage_complete')is True and response.get('trace_lost')is False
               and type(response.get('coverage_started_ns'))is int and 0<=response['coverage_started_ns']<=origin
               and type(response.get('accounted_through_ns'))is int and self.accounted<=response['accounted_through_ns']<deadline,
               'actual original lifetime accounting coverage absent')
        self.accounted=response['accounted_through_ns'];counters=response['counters']
        u.need(type(counters)is dict and set(counters)==set(COUNTERS),'complete actual host counters')
        for key,value in counters.items():
            u.need(type(value)is int and self.high[key]<=value<=q['profile'][key],'actual counter regressed/exceeded');self.high[key]=value
        u.need(response.get('child_ledger_complete')is True and type(response.get('unknown_children'))is int
               and response['unknown_children']==0 and type(response.get('children'))is list
               and len(response['children'])<=q['child_record_limit'],'actual complete child ledger')
        seen=set()
        for child in response['children']:
            u.need(type(child)is dict and set(child)=={'identity','owner_nonce','started_ns','finished_ns','exit_code','natural'},'exact actual child record')
            identity=u.sha(u.canonical(child['identity']));allowed=set(self.phase_nonces.values())|{nonce}if action=='host-whole-close'else{nonce}
            u.need(identity not in seen and child['identity']!=self.host_identity and child['owner_nonce']in allowed
                   and type(child['exit_code'])is int and child['exit_code']==0 and child['natural']is True
                   and type(child['started_ns'])is int and type(child['finished_ns'])is int
                   and origin<=child['started_ns']<=child['finished_ns']<=self.accounted,'failed/repeated/unowned actual child')
            seen.add(identity)
        if action=='host-phase-seal':
            u.need(request.get('expected_worker_closures')=={k:v['commitment']for k,v in phase_workers.items()},'actual expected phase worker set')
        if action!='host-phase-open':u.need(request.get('expected_output_seals')==response.get('output_seals'),'actual requested output seals differ')
        return response
    def _close(self,h,r,command,workers,action,p,b,artifact):
        d=self.d;q=d['host_accounting'];whole=action=='host-whole-close';counters=r['counters']
        u.need(type(h)is dict and h.get('scope')=='live_host_phase_children' and h.get('host_identity')==self.host_identity
               and h.get('phase_id')==('whole-host-close'if whole else p['id']) and h.get('binding_digest')==b
               and h.get('origin_ns')==d['origin_ns'] and h.get('deadline_ns')==d['deadline_ns']
               and all(h.get(k)is True for k in ('host_alive','phase_observation_complete','owned_children_closed','external_host_natural_exit_required'))
               and not h.get('failures') and h.get('primitive_evidence_digest')==command['stdout_sha256']
               and h.get('child_ledger_digest')==u.sha(u.canonical(r['children']))
               and h.get('accounted_through_ns')==r['accounted_through_ns']
               and type(h.get('finished_ns'))is int and max(command['finished_ns'],h['accounted_through_ns'])<=h['finished_ns']<d['deadline_ns'],
               'actual unchanged HostObservation fields differ')
        seals=r.get('output_seals');u.need(type(seals)is dict and h['output_bundle_digests']==seals and r.get('unclosed_children')==[],
                                       'actual output/child closure differs')
        if whole:
            u.need(self.whole is None,'one whole-host cumulative checkpoint')
            expected={k:artifact[k]for k in ('native_bundle_digest','prediction_bundle_digest','expected_bundle_digest','native_schema_digest')}
            # Current outer-close is open; previous phases are fully observed.
            records={k:u.sha(u.canonical(v))for k,v in self.phase_observations.items()}
            records[p['id']]=self._current_open
            expected['host_phase_observations_digest']=u.sha(u.canonical(records))
            u.need(seals==expected,'whole output and exact phase observation registry seal')
        else:u.need(seals=={'artifact':u.scientific_digest(artifact)} and h['artifact_digest']==seals['artifact'],'actual phase artifact seal')
        resources,commits=_partition(r,workers,q['trace_bytes'])
        u.need(resources==h['worker_resources'] and commits==h['worker_closure_digests'],'actual distinct worker counter/closure partitions differ')
        for key in COUNTERS:
            expected=counters[key]if whole or key not in LIFETIME else counters[key]-self.consumed[key]
            u.need(type(h['resources'].get(key))is int and h['resources'][key]==expected,'actual absolute/delta host counter differs')
        u.need(h['resources'].get('observed_cumulative_counters')==counters and h['resources'].get('unobserved_quantities')==[]
               and h['resources'].get('unobserved_worker_ids')==[]
               and h['resources'].get('observed_accountant_pin_read_bytes')==len(self.commands)*q['process']['accountant']['bytes']
               and h['resources'].get('retained_host_command_trace_bytes')==len(u.canonical(self.commands)),
               'known actual counter and retained command evidence differs')
        if whole:
            for key in ('read_bytes','write_bytes','retained_bytes','live_bytes'):
                parts=[v[key]for v in resources.values()];total=counters[key]+(max(parts,default=0)if key=='live_bytes'else sum(parts))
                u.need(total<=d['profile'][key],'whole cumulative actual profile exceeded; no prior-total double count')
            self.whole=h
        else:self.consumed={k:max(self.consumed[k],counters[k])for k in COUNTERS}

def validate(rows,document,host_identity):
    replay=Replay(document,host_identity)
    for row in rows:
        replay._current_open=row['actual_evidence']['open'];replay.phase(row)
    u.need(replay.phase_count==23786 and replay.whole is not None,'complete actual original phase/accountant proof')
    return {'actual_phase_count':replay.phase_count,'distinct_workers':len(replay.workers),
            'actual_command_count':len(replay.commands),'whole_observation_digest':u.sha(u.canonical(replay.whole)),
            'phase_observations_digest':u.sha(u.canonical(replay.phase_observations))}
