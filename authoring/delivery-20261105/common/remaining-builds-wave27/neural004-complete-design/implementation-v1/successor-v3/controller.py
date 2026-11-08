"""Complete source-owned programme composition. No execution on import.

Independent signed custody/closure artifacts arrive between phases, not through
arbitrary result callbacks. Every numeric endpoint calls the fixed helpers or
closed generated-source process path. Missing admission never means success.
"""
from pathlib import Path
from .common import (PEOPLE,CHANNELS,MODES,VIEWS,PREDICTION_POLICIES,GLOBAL_POLICIES,
    need,fields,integer,pin,body_pin,encode,decode,check_pin,Cleanup)
from .admission import read_original
from .policies import Commitments
from .views import make_view,opaque
from .investigator import Investigator
from .grading import ReleaseBarrier,grade_prediction_panels,compare_reconstruction,validate_reconstruction_reference,score_reasoning
from . import report_agents,spatial
from .failures import describe,safe,retain_primary
from .context_budget import ScopedLedger,bounded_resources
from .workload import expected_counts

class HMPAccounting:
    """Narrow actual-cost/clock adapter; never returns scientific values."""
    def __init__(self,ledger):self.ledger=ledger
    def tick(self):return self.ledger.tick()
    def reserve(self,kind,count,detail):
        name='hmp_'+kind;need(name in self.ledger.limits,'complete HMP profile dimension '+kind)
        self.ledger.reserve({name:count},detail)
    def fail(self,stage,exception_type):self.ledger.fail(stage,RuntimeError(exception_type))

def reference_folds(private_rows,seed,source_pin,environment_pin,reference_source_pin):
    grouped={p:[] for p in PEOPLE}
    for r in private_rows:grouped[r['person']].append(r)
    private_map={};records={}
    for p in PEOPLE:
        rows=sorted(grouped[p],key=lambda r:r['epoch']);pid=opaque(seed,'reference-private','person',p)
        ids=[opaque(seed,'reference-private','trial',[p,r['epoch']]) for r in rows]
        records[p]={'person_id':pid,'trial_ids':ids,'rt_seconds':[r['rt'] for r in rows],
            'instruction':[r['instruction'] for r in rows],'sample_count':[r['samples'] for r in rows],
            'target':[r['contrast'] for r in rows],'waveforms':[r['waveform'] for r in rows]}
        private_map[p]=[{'id':i,'source_id':p+'/'+str(r['epoch'])} for i,r in zip(ids,rows)]
    folds=[]
    for outer,p in enumerate(PEOPLE):
        held={k:v for k,v in records[p].items() if k!='target'}
        folds.append({'outer_index':outer,'training':[records[t] for t in PEOPLE if t!=p],'held':held,'channel_order':list(CHANNELS),
            'lineage':{'source':source_pin,'environment':environment_pin,'reference_source':reference_source_pin,'channel_order':list(CHANNELS),
                'view':pin({'outer':p,'training_people':[records[t]['person_id'] for t in PEOPLE if t!=p],'held':held['person_id']})}})
    return folds,private_map

class Programme:
    def __init__(self,policies,authorities,ledger,bodies,transport,worker_source,worker_pin,python_path,source_pin,seed,profile):
        need(type(seed) is bytes and len(seed)>=32,'prospectively fixed operator opaque seed')
        need(type(ledger) is ScopedLedger,'concrete complete per-context accounting ledger')
        self.authorities=authorities;self.ledger=ledger;self.bodies=bodies;self.transport=transport;self.source_pin=source_pin
        self.seed=seed;self.profile=profile;self.commitments=Commitments(policies,authorities,ledger)
        self.engine=Investigator(transport,bodies,ledger,worker_source,worker_pin,python_path,source_pin)
        self.global_bodies={};self.data=None;self.hmp=None;self.hmp_module=None;self.references=None;self.actors={};self.reconstruction={};self.explanations={}
        self.contexts={(m,v,p):opaque(seed,'context','prediction',[m,v,p]) for m in MODES for v in VIEWS for p in PEOPLE}
        self.reference_contexts={(f,p):opaque(seed,'context','reference',[f,p]) for f in ('B','N') for p in PEOPLE}
        self.barrier=ReleaseBarrier(list(self.contexts.values()),list(self.reference_contexts.values()),authorities,ledger)
        self.private_maps={};self.closed_dispositions={};self.runtime=None;self.prediction_grade=None;self.reconstruction_grade={};self.spatial_records=None
    def admit_runtime(self,envelope):
        need(self.runtime is None,'single complete deployment profile')
        verified=self.authorities.verify(envelope,'environment','runtime_profile',{'source_pin':self.source_pin,'profile_pin':pin(self.profile,8*1048576)})
        f=verified['facts'];fields(f,('environment_pin','dependency_source_pins','namespace_cgroup_admission','hard_caps_admission','private_operator_realm','provider_admission','spend_admission','unknown'))
        need(not f['unknown'],'complete selected execution environment admission')
        for k in ('environment_pin','namespace_cgroup_admission','hard_caps_admission','private_operator_realm','provider_admission','spend_admission'):check_pin(f[k])
        need(type(f['dependency_source_pins']) is dict and f['dependency_source_pins'],'actual imported dependency source identities')
        self.runtime=verified;return verified
    def commit(self,envelope):
        need(self.runtime is not None,'runtime admitted before operation')
        freeze={'programs':{},'contexts':{}}
        for key,policy in self.commitments.policies.items():
            self.global_bodies[key]=self.transport.provider.read_committed_program(policy['source']);freeze['programs'][key]=policy['source'];freeze['contexts'][key]=key
        historical=self.commitments.commit(envelope,self.global_bodies)
        observation=self.transport.observer.commit_all_programs(freeze,self.ledger.origin,self.ledger.scientific)
        self.bodies.put_json('GLOBAL_COMMITMENT.json',{'policies_pin':self.commitments.pin,'historical_authority':historical,'observer_partial_record':observation})
    def prepare(self,root,source_roster,envelope):
        need(self.commitments.committed is not None and self.data is None,'source/policies sealed before numeric preparation')
        try:self.data=read_original(root,source_roster,envelope,self.authorities,self.ledger,self.profile['reader'])
        except BaseException as error:
            self.source_failure={'failure':describe(error,self.bodies.cap),'completed_reader_audit':getattr(error,'neural004_reader_audit',None)}
            retain_primary(self.bodies,'SOURCE_PREPARATION_FAILURE.json',self.source_failure,error,self.bodies.cap);raise
        self.bodies.put_json('SOURCE_ADMISSION.json',self.data['source_admission'])
        self.bodies.put_json('PRIVATE_ALIAS_AUDIT.json',self.data['private_alias_audit'])
        return self.data['source_admission']
    def numerical_hmp(self,repository_root,environment,limits):
        need(self.data is not None and self.hmp is None,'source prepared before one complete HMP programme')
        from . import hmp_core as module
        from .hmp_core.binding import EXPECTED_BINDING
        source_binding=EXPECTED_BINDING;self.hmp_module=module;self.hmp_limits=limits
        admission={'schema':'neural004_hmp_admission_v1','people':list(PEOPLE),'rows':self.data['source_admission']['retained_rows'],
            'dataset_pin':self.data['source_admission']['data_pin'],'channel_order':list(CHANNELS),'offset':5,
            'source_binding':source_binding,'source_root':str(repository_root),'environment':environment}
        try:self.hmp=module.run_complete_hmp(self.data['epoch_data'],admission,limits,HMPAccounting(self.ledger))
        except BaseException as error:
            self.hmp_failure=getattr(error,'record',None)
            cleanup=Cleanup(self.ledger);cleanup.defer('retain HMP failure',lambda:self.bodies.put_json('HMP_FAILURE.json',{'type':type(error).__name__,'record':self.hmp_failure}));cleanup.run(error);raise
        self.bodies.put_json('HMP_RESULT_INDEX.json',self.hmp);return self.hmp
    def numerical_references(self,budget_profile):
        need(self.data is not None and self.references is None,'prepared source and one complete reference programme')
        from . import reference_core as module
        helper_source_pin={'bytes':6858,'sha256':'46f5681aa679c638e90b60f006a138c71cbc44a025f5915bf840c475e70a7a24'}
        # The helper's clock shares the original operation origin/deadline.
        need(budget_profile['original_origin']==self.ledger.origin/1e9 and budget_profile['deadline']==self.ledger.scientific/1e9,'unchanged reference operation clock')
        budget=module.Budget(budget_profile,clock=lambda:self.ledger.clock()/1e9)
        folds,mapping=reference_folds(self.data['private_rows'],self.seed,self.data['source_admission']['data_pin'],self.runtime['facts']['environment_pin'],helper_source_pin)
        index={'events':[],'states':{},'selections':{},'finals':{},'full_closure':None,'qualified':False};self.references=index;self.reference_maps=mapping
        iterator=module.fit_full_reference(folds,budget)
        self.reference_phase={'schema':'neural004_actual_operator_reference_phase_v1','source_pin':self.source_pin,'method':'fixed reference_core.fit_full_reference',
            'origin_ns':self.ledger.origin,'started_ns':self.ledger.clock(),'finished_ns':None,'index_pin':None,'status':'running'}
        primary=None
        try:
            for serial,event in enumerate(iterator):
                self.ledger.tick();raw=encode(event,self.profile['reference_event_bytes'])
                descriptor=self.bodies.put('reference-event-'+str(serial)+'.json',raw)
                # Durable retention above precedes advancing the numerical iterator.
                index['events'].append(descriptor)
                if event.get('schema')!='neural004_reference_event_v1':continue
                kind=event['kind'];outer=event['outer_index'];body=event['body'];held=None if outer is None else PEOPLE[outer]
                if kind in ('inner_state','final_state'):
                    index['states'][body['state_pin']['sha256']]=descriptor
                if kind=='selection':index['selections'][held]={'body':body,'event':descriptor}
                if kind in ('final_completed','final_reused'):
                    record=body['record'] if kind=='final_completed' else body;role=record['final_role']
                    if kind=='final_completed':prediction=body['prediction']
                    else:
                        previous=index['finals'][held+'/'+record['reused_role']]
                        need(previous['record']['state_pin']==record['state_pin'] and previous['record']['prediction_pin']==record['prediction_pin'],'actual final immutable state reuse')
                        prediction=previous['prediction']
                    need(record['state_pin']['sha256'] in index['states'],'final state retained before forecast')
                    index['finals'][held+'/'+role]={'record':record,'prediction':prediction,'event':descriptor}
                if kind=='full_completed':index['full_closure']=descriptor
            need(index['full_closure'] is not None,'actual complete reference generator closure')
        except BaseException as error:
            primary=error;index['failure']={'type':type(error).__name__,'record':getattr(error,'record',None)};raise
        finally:
            cleanup=Cleanup(self.ledger)
            cleanup.defer('retain complete reference partial index',lambda:self.bodies.put_json('REFERENCE_INDEX.json',index))
            cleanup.defer('close numerical reference generator',iterator.close)
            cleanup.run(primary)
            self.reference_phase.update(finished_ns=self.ledger.clock(),index_pin=pin(index,32*1048576),status='failed' if primary else 'complete')
            self.reference_phase['binding_digest']=pin({k:v for k,v in self.reference_phase.items() if k!='binding_digest'})['sha256']
        return index
    def _tool(self,held):
        need(self.hmp is not None,'retained complete HMP computation available')
        return self.hmp_module.export_private_tool(self.hmp,held,self.hmp_limits,HMPAccounting(self.ledger))
    def prediction_actors(self,deployment_path,deployment_pin,credential,exposure_envelopes):
        need(self.data is not None and not self.actors,'one full fresh208-context actor programme')
        for mode in MODES:
            for view in VIEWS:
                for held in PEOPLE:
                    context=self.contexts[(mode,view,held)];policy=self.commitments.open(context,mode+'/'+view)
                    packet=None;primary=None;self.ledger.begin_context(context,policy['limits'])
                    try:
                        exposure=self.authorities.verify(exposure_envelopes[context],'operator','context_exposure',{'context':context,'policy_pin':pin(policy,4*1048576),'held':held,'view':view})
                        fields(exposure['facts'],('exposure_admission','fresh_history','source_views','hard_context_caps_admission','unknown'))
                        need(exposure['facts']['fresh_history'] is True and not exposure['facts']['unknown'],'independent fresh context custody')
                        for k in ('exposure_admission','source_views','hard_context_caps_admission'):check_pin(exposure['facts'][k])
                        # All preparation/serialization and failures belong to the same context profile.
                        scalar_count=sum(32*r['samples'] for r in self.data['private_rows'])
                        self.ledger.reserve({'read_bytes':scalar_count*8},'complete source view validation/projection')
                        with self.ledger.live(scalar_count*40,'complete known source-view representation'):
                            packet=make_view(self.data['private_rows'],held,mode,view,self.seed,context,self.data['source_admission']['data_pin'],self.profile['views'],hmp_tool=self._tool(held) if view in ('H','EH') else None)
                        self.private_maps[context]=[{'id':tid,'source_id':p+'/'+str(e)} for tid,(p,e) in packet['private_ids'].items() if p==held]
                        self.actors[context]=self.engine.run(packet,policy,self.global_bodies[mode+'/'+view],deployment_path,deployment_pin,credential,exposure['facts']['exposure_admission'])
                        self.bodies.put_json('actor-'+context+'.json',self.actors[context])
                    except BaseException as error:
                        primary=error
                        failure=getattr(error,'neural004_actor_failure',{'context':{'context':context,'held':held,'mode':mode,'view':view},'status':'failed','history':[],'traces':[],
                            'failure':describe(error,policy['wire_limits']['max_response_bytes'])})
                        failure['status']='failed';self.actors[context]=safe(failure,policy['wire_limits']['max_response_bytes'])
                        retain_primary(self.bodies,'actor-'+context+'-failure.json',self.actors[context],error,policy['wire_limits']['max_response_bytes'])
                    finally:
                        cleanup=Cleanup(self.ledger)
                        cleanup.defer('close original actor resource context',lambda:self.ledger.end_context(failed=primary is not None))
                        cleanup.run(primary)
        need(len(self.actors)==208,'all actor contexts accounted');return self.actors
    def dispositions(self):
        need(len(self.actors)==208 and self.references is not None,'full actor/reference phase entered')
        dispositions={};self.reference_seals={}
        for context,result in self.actors.items():
            traces=result.get('traces',[]);bindings=[r['binding_digest'] for r in self.transport.records if r['context'].startswith(context+'-tool-')]
            seal=result.get('seal');dispositions[context]={'context':context,'status':result['status'],'seal_pin':None if seal is None else pin(seal,8*1048576),
                'history_pin':pin(result.get('history',[]),8*1048576),'operation_bindings':bindings}
        for role in ('B','N'):
            for held in PEOPLE:
                context=self.reference_contexts[(role,held)];final=self.references['finals'].get(held+'/'+role)
                if final is None:seal=None;status='failed'
                else:
                    prediction=final['prediction'];forecast=[{'id':i,'prediction':y} for i,y in zip(prediction['trial_ids'],prediction['prediction'])]
                    need(len(forecast)==len(self.reference_maps[held]),'complete reference forecast support')
                    seal={'forecast_pin':pin(forecast,8*1048576),'state_pin':final['record']['state_pin'],'selection_event':self.references['selections'][held]['event'],
                        'prediction_event':final['event'],'reference_full_closure':self.references['full_closure']}
                    self.reference_seals[context]={'forecasts':forecast,'seal':seal};status='sealed'
                dispositions[context]={'context':context,'status':status,'seal_pin':None if seal is None else pin(seal,8*1048576),
                    'history_pin':pin({'reference_events':self.references['events']},16*1048576),'operation_bindings':[self.reference_phase['binding_digest']]}
        self.closed_dispositions=dispositions;return dispositions
    def close_predictions(self,closure_envelopes,job_closure_envelopes,reference_phase_envelope):
        need(set(closure_envelopes)==set(self.closed_dispositions),'exact full260 context closure envelopes')
        jobs={r['binding_digest']:r for r in self.transport.records}
        expected_jobs={b for c,d in self.closed_dispositions.items() if c in self.actors for b in d['operation_bindings']}
        need(set(job_closure_envelopes)==expected_jobs,'every attempted actual actor job has independent closure evidence')
        phase=self.reference_phase
        verified=self.authorities.verify(reference_phase_envelope,'observer','operator_phase_closure',pin(phase,32*1048576))
        f=verified['facts'];fields(f,('phase_record_pin','source_pin','no_live_phase_work','private_operator_realm','physical_resources','finished_ns','unknown'))
        need(f['phase_record_pin']==pin(phase,32*1048576) and f['source_pin']==self.source_pin and f['no_live_phase_work'] is True and not f['unknown'],'actual fixed operator reference computation phase closure')
        check_pin(f['private_operator_realm']);need(type(f['finished_ns']) is int and f['finished_ns']==phase['finished_ns'] and self.ledger.origin<=f['finished_ns']<self.ledger.scientific,'same original reference phase completion clock')
        bounded_resources(f['physical_resources'],self.profile['reference_limits'])
        phase_qualification={'qualified_custody':True,'phase_record_pin':f['phase_record_pin'],'authority_pin':verified['envelope_pin'],
            'physical_resources':f['physical_resources'],'shared_once_across_reference_slots':True,'operator_phase_not_future_parent_process_exit':True}
        for context,disposition in self.closed_dispositions.items():
            if context in self.actors:
                result=self.actors[context];meta=result['context'];limits=self.commitments.policies[meta['mode']+'/'+meta['view']]['limits']
                qualified={binding:self.transport.qualify(jobs[binding],job_closure_envelopes[binding],self.authorities,limits,
                    require_success=disposition['status']=='sealed') for binding in disposition['operation_bindings']}
            else:limits=self.profile['reference_limits'];qualified={phase['binding_digest']:phase_qualification}
            self.barrier.register(context,disposition,limits,qualified)
            self.barrier.close(context,disposition,closure_envelopes[context])
    def target_bundle(self):
        need(set(self.barrier.closed)==self.barrier.expected,'targets remain protected until all context closure')
        answers={p:[] for p in PEOPLE}
        for row in self.data['private_rows']:answers[row['person']].append({'id':row['person']+'/'+str(row['epoch']),'value':row['contrast']})
        maps=dict(self.private_maps)
        for (role,held),context in self.reference_contexts.items():maps[context]=self.reference_maps[held]
        return {'answers':answers,'context_answer_maps':maps,'source_admission_pin':pin(self.data['source_admission'],8*1048576)}
    def grade(self,release_envelope):
        bundle=self.target_bundle();self.barrier.open(bundle,release_envelope)
        actors={k:{} for k in PREDICTION_POLICIES};refs={k:{} for k in ('B','N')}
        for (mode,view,held),context in self.contexts.items():
            result=self.actors[context];actors[mode+'/'+view][held]={'context':context,'status':result['status'],'forecasts':result.get('forecasts'),
                'seal':result.get('seal'),'answer_map':bundle['context_answer_maps'].get(context,[])}
        for (role,held),context in self.reference_contexts.items():
            result=self.reference_seals.get(context,{});refs[role][held]={'context':context,'status':self.closed_dispositions[context]['status'],'forecasts':result.get('forecasts'),
                'seal':result.get('seal'),'answer_map':bundle['context_answer_maps'].get(context,[])}
        self.prediction_grade=grade_prediction_panels(self.barrier,actors,refs,bundle)
        self.prediction_grade['supplied_HMP_condition_complete']=bool(self.hmp and self.hmp['complete'])
        self.bodies.put_json('PREDICTION_GRADE.json',self.prediction_grade);return self.prediction_grade
    def reconstruction_actors(self,deployment_path,deployment_pin,credential,exposure_envelopes):
        need(self.barrier.release is not None and not self.reconstruction,'fresh reconstruction after prediction release')
        audits={(r['person'],r['epoch']):r['alias_audit'] for r in self.data['private_alias_audit']}
        for mode in MODES:
            for held in PEOPLE:
                context=opaque(self.seed,'context','reconstruction',[mode,held]);policy=self.commitments.open(context,'reconstruction/'+mode)
                primary=None;self.ledger.begin_context(context,policy['limits'])
                try:
                    admitted=self.authorities.verify(exposure_envelopes[context],'operator','context_exposure',{'context':context,'policy_pin':pin(policy,4*1048576),'held':held,'task':'reconstruction'})
                    check_pin(admitted['facts']['exposure_admission']);need(admitted['facts']['fresh_history'] is True and not admitted['facts']['unknown'],'fresh no-prediction-feedback reconstruction history')
                    rows=[]
                    for row in self.data['private_rows']:
                        a=audits[(row['person'],row['epoch'])]
                        rows.append({'person':row['person'],'epoch':row['epoch'],'rt':row['rt'],'samples':row['samples'],
                            'waveform':row['waveform'],'condition':'accuracy' if row['instruction'] else 'speed',
                            'stimulus':a['logged_literal'],'response':a['response'],'side':a['side']})
                    common={'schema':'neural004_reconstruction_view_v1','sampling_hz':512,'channel_order':list(CHANNELS),'paper_informed':True,
                        'actual_reference_report_visible':False,'supplied_operator_fitted_states':False}
                    train=encode({**common,'rows':[r for r in rows if r['person']!=held]},policy['limits']['view_bytes'])
                    query=encode({**common,'rows':[r for r in rows if r['person']==held]},policy['limits']['view_bytes'])
                    result=report_agents.reconstruction(self.engine,context,mode,held,train,query,policy,self.global_bodies['reconstruction/'+mode],deployment_path,deployment_pin,credential,admitted['facts']['exposure_admission'],self.barrier.release)
                except BaseException as error:
                    primary=error;result=getattr(error,'neural004_report_failure',{'context':context,'mode':mode,'held':held,'status':'failed','failure':describe(error,policy['wire_limits']['max_response_bytes'])})
                    retain_primary(self.bodies,'reconstruction-'+context+'-failure.json',result,error,policy['wire_limits']['max_response_bytes'])
                self.reconstruction[mode+'/'+held]=safe(result,policy['wire_limits']['max_response_bytes'])
                cleanup=Cleanup(self.ledger)
                cleanup.defer('close reconstruction context resource ledger',lambda:self.ledger.end_context(failed=primary is not None))
                cleanup.defer('retain reconstruction context',lambda:self.bodies.put_json('reconstruction-'+context+'.json',self.reconstruction[mode+'/'+held],cutoff='closeout' if primary else 'scientific'))
                cleanup.run(primary)
        need(len(self.reconstruction)==52,'all52 reconstruction contexts accounted');return self.reconstruction
    def reconstruction_grades(self,tolerance_envelope):
        need(self.barrier.release is not None and len(self.reconstruction)==52,'postseal complete reconstruction dispositions')
        from .common import read_body
        if self.hmp is None:
            self.reconstruction_grade={mode:{'status':'incomplete','reason':'independent_HMP_reference_unavailable','whole_paper_reproduction':False} for mode in MODES}
            self.bodies.put_json('RECONSTRUCTION_GRADE.json',self.reconstruction_grade);return self.reconstruction_grade
        def retained(descriptor):
            name=descriptor['name'];need(Path(name).name==name,'flat retained HMP artifact')
            raw=read_body(Path(self.hmp['output_root'])/name,{k:descriptor[k] for k in ('bytes','sha256')},self.ledger,self.hmp_limits['metadata_bytes'])
            return decode(raw,self.hmp_limits['metadata_bytes'])
        index=retained(self.hmp['index'])
        if 'report' not in index:
            self.reconstruction_grade={mode:{'status':'incomplete','reason':'independent2964_cell_reference_incomplete','whole_paper_reproduction':False} for mode in MODES}
            self.bodies.put_json('RECONSTRUCTION_GRADE.json',self.reconstruction_grade);return self.reconstruction_grade
        reference=retained(index['report'])
        verified=self.authorities.verify(tolerance_envelope,'operator','reconstruction_tolerances',{'source_pin':self.source_pin,'reference_report_pin':pin(reference,8*1048576)})
        tolerance=verified['facts']['policy']
        # Invalid independent reference/policy/custody is a gate, not candidate
        # invalidity. Complete this admission before either mode is scored.
        validate_reconstruction_reference(reference,tolerance)
        template={k:reference[k] for k in ('schema','mode','dataset_sha256')}
        for mode in MODES:
            entries=[self.reconstruction[mode+'/'+p] for p in PEOPLE]
            if any(r['status']!='sealed' for r in entries):
                result={'status':'incomplete','contexts':[{'held':r['held'],'status':r['status']} for r in entries],'whole_paper_reproduction':False}
            else:
                try:
                    candidate={**template,'people':[r['person_record'] for r in entries]}
                    result={'status':'compared',**compare_reconstruction(candidate,reference,tolerance)}
                except (KeyError,TypeError,ValueError,OverflowError) as error:
                    # Candidate schema, support or numeric invalidity is a
                    # retained mode outcome; the other mode must still grade.
                    result={'status':'invalid_candidate','failure':describe(error,self.bodies.cap),
                        'contexts':[{'held':r.get('held'),'context':r.get('context'),'seal':r.get('seal')} for r in entries],
                        'whole_paper_reproduction':False}

            self.reconstruction_grade[mode]=result
        self.bodies.put_json('RECONSTRUCTION_GRADE.json',self.reconstruction_grade);return self.reconstruction_grade
    def spatial_descriptions(self):
        need(self.barrier.release is not None and self.hmp is not None,'spatial evidence only after prediction closes')
        exported=self.hmp_module.export_spatial_indices(self.hmp,self.hmp_limits,HMPAccounting(self.ledger));events={}
        for p,rows in exported['people'].items():
            need(rows,'complete spatial support');events[p]={'rows':rows,'state_pin':rows[0]['state_pin'],'evaluation_pin':rows[0]['evaluation_pin']}
        descriptors=[];counts={'event_aligned':0,'fixed_window':0}
        for serial,record in enumerate(spatial.compute(self.data['private_rows'],self.data['private_alias_audit'],events,self.ledger,self.profile['spatial'])):
            descriptors.append(self.bodies.put_json('spatial-'+str(serial)+'.json',record));counts[record['kind']]+=1
        need(counts=={'event_aligned':1820,'fixed_window':2184},'complete spatial programme')
        self.spatial_records={'records':descriptors,'counts':counts,'qualified':False};self.bodies.put_json('SPATIAL_INDEX.json',self.spatial_records);return self.spatial_records
    def evidence_packet(self):
        need(self.prediction_grade is not None and len(self.reconstruction)==52 and set(self.reconstruction_grade)==set(MODES) and self.spatial_records is not None,'all numerical grading dispositions before common explanation evidence')
        from .common import read_body
        from .evidence import hmp_summaries
        spatial_values=[]
        for descriptor in self.spatial_records['records']:
            record=decode(self.bodies.read(descriptor),self.bodies.cap)
            # Complete descriptive values/support summaries are delivered, while
            # the exact per-trial sample inventory remains linked for review.
            spatial_values.append({k:v for k,v in record.items() if k!='trial_support'}|{'trial_support_artifact':descriptor})
        report=None;diagnostics=[]
        if self.hmp is not None:
            descriptor=self.hmp['index'];raw=read_body(Path(self.hmp['output_root'])/descriptor['name'],{k:descriptor[k] for k in ('bytes','sha256')},self.ledger,self.hmp_limits['metadata_bytes'])
            index=decode(raw,self.hmp_limits['metadata_bytes'])
            if 'report' in index:
                descriptor=index['report'];report=decode(read_body(Path(self.hmp['output_root'])/descriptor['name'],{k:descriptor[k] for k in ('bytes','sha256')},self.ledger,self.hmp_limits['metadata_bytes']),self.hmp_limits['metadata_bytes'])
            for held in PEOPLE:diagnostics.extend(hmp_summaries(self._tool(held),held))
        return {'schema':'neural004_reasoning_evidence_v1','source_pin':self.source_pin,
            'prediction':self.prediction_grade,'reconstruction':self.reconstruction_grade,
            'hmp_complete':None if self.hmp is None else self.hmp['complete'],'hmp_retained_index':None if self.hmp is None else self.hmp['index'],
            'original2964_cell_reference_report':report,'hmp_all26_diagnostics':diagnostics,
            'spatial':spatial_values,'paper_informed':True,'retrospective':True,
            'no_latent_ground_truth':True,'same_right_hand_two_response_fingers':True,'whole_paper_replication':False,
            'independent_runtime_qualification':False,'reference_competence':'not established merely by source completion'}
    def explanation_actors(self,deployment_path,deployment_pin,credential):
        need(not self.explanations,'fresh eight explanation contexts');evidence=self.evidence_packet();self.common_evidence=evidence
        self.bodies.put_json('COMMON_REASONING_EVIDENCE.json',evidence)
        for policy_name in PREDICTION_POLICIES:
            context=opaque(self.seed,'context','explanation',policy_name);policy=self.commitments.policies[policy_name]
            primary=None;self.ledger.begin_context(context,policy['limits'])
            try:result=report_agents.explanation(self.engine,context,policy,evidence,self.global_bodies[policy_name],deployment_path,deployment_pin,credential,self.barrier.release)
            except BaseException as error:
                primary=error;result={'context':context,'status':'failed','failure':describe(error,policy['wire_limits']['max_response_bytes'])}
                retain_primary(self.bodies,'explanation-'+context+'-failure.json',result,error,policy['wire_limits']['max_response_bytes'])
            self.explanations[policy_name]=result
            cleanup=Cleanup(self.ledger)
            cleanup.defer('close explanation context resource ledger',lambda:self.ledger.end_context(failed=primary is not None))
            cleanup.defer('retain explanation context',lambda:self.bodies.put_json('explanation-'+context+'.json',result,cutoff='closeout' if primary else 'scientific'))
            cleanup.run(primary)
        return self.explanations
    def reasoning_grade(self,review_envelope):
        need(set(self.explanations)==set(PREDICTION_POLICIES) and all(r['status']=='sealed' for r in self.explanations.values()),'all eight complete reasoning reports')
        reports={k:v['report'] for k,v in self.explanations.items()};evidence_pin=pin(self.common_evidence,32*1048576)
        verified=self.authorities.verify(review_envelope,'human_review','human_reviews',{'reports_pin':pin(reports,32*1048576),'evidence_pin':evidence_pin})
        fields(verified['facts'],('reviews','reviewer_admission'))
        result=score_reasoning(reports,verified['facts']['reviews'],evidence_pin,verified['facts']['reviewer_admission'])
        self.bodies.put_json('REASONING_GRADE.json',result);self.reasoning_result=result;return result
    def closeout(self,closure_envelope=None,scientific_qualification_envelope=None):
        status={'schema':'neural004_programme_closeout_v1','source_pin':self.source_pin,'planned_counts':expected_counts(),
            'hmp':None if self.hmp is None else {'complete':self.hmp['complete'],'index':self.hmp['index']},
            'references':None if self.references is None else {'full_closure':self.references['full_closure'],'finals':len(self.references['finals'])},
            'prediction_contexts':{c:self.actors.get(c,{}).get('status','unentered') for c in self.contexts.values()},'reconstruction_contexts':{m+'/'+p:self.reconstruction.get(m+'/'+p,{}).get('status','unentered') for m in MODES for p in PEOPLE},
            'explanation_contexts':{k:self.explanations.get(k,{}).get('status','unentered') for k in PREDICTION_POLICIES},'prediction_grade_available':self.prediction_grade is not None,
            'reasoning_grade_available':hasattr(self,'reasoning_result'),'resources':self.ledger.report(),'whole_study_qualified':False}
        if closure_envelope is not None:
            verified=self.authorities.verify(closure_envelope,'observer','study_closure',pin(status,32*1048576))
            fields(verified['facts'],('all_job_costs_and_failures','all_processes_and_provider_requests_closed','source_custody','scientific_components_reviewed','unknown'))
            need(not verified['facts']['unknown'],'complete independent study closure')
            for k in ('all_job_costs_and_failures','source_custody','scientific_components_reviewed'):check_pin(verified['facts'][k])
            need(verified['facts']['all_processes_and_provider_requests_closed'] is True,'independently closed complete work')
            status['independent_study_closure_pin']=verified['envelope_pin']
            # Finite negative effects and reproduction mismatches remain outcomes.
            status['independently_custodied_complete_execution']=bool(self.hmp and self.hmp['complete'] and self.references and self.references['full_closure'] and
                self.prediction_grade and self.prediction_grade['whole_prediction_complete'] and len(self.reconstruction_grade)==2 and
                all(x['status']=='compared' for x in self.reconstruction_grade.values()) and hasattr(self,'reasoning_result') and self.spatial_records)
        if scientific_qualification_envelope is not None:
            need(status.get('independently_custodied_complete_execution') is True,'scientific qualification requires complete independently custodied execution')
            scientific=self.authorities.verify(scientific_qualification_envelope,'operator','study_scientific_qualification',pin(status,32*1048576))
            f=scientific['facts'];fields(f,('authentic_input_validation','numerical_environment_validation','reference_competence_review',
                'human_review_reliability_validation','exposure_contamination_characterization','scientific_scope_review','unknown'))
            need(not f['unknown'],'all independent scientific qualifications resolved')
            for key,value in f.items():
                if key!='unknown':check_pin(value)
            status['scientific_qualification_pin']=scientific['envelope_pin'];status['whole_study_qualified']=True
        self.ledger.tick('closeout');self.bodies.put_json('STUDY_CLOSEOUT.json',status,cutoff='closeout');self.ledger.tick('closeout');return status
