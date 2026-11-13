"""Complete29-session task-specific actor/reference/diagnostic/scorer caller.

No framework dispatch, proxy numerical runtime or invented native receipt is
accepted. Scientific transformations and scalar metrics are the retained kernels.
"""
from copy import deepcopy
import time
from .core import need, keys, encode, parse, pin, capture, verify_file, literal, decode_body, CONDITIONS, STATUS
from .selection import capture_policies
from .native_profile import validate_profile, digest
from .scientific import preparation, diagnostics, evaluation, native_references as reference
from .scientific.contracts import member_map, check_prepared
from .scientific.controller import PanelController
from .scientific.campaign import calibration
from .managed_views import CalibrationViews
from .managed_io import OwnedDirectory, Journal
from .scientific.lifecycle import LifecycleLedger, FIELDS, zero


class Programme:
    def __init__(self, selection, host, budget, journal):
        self.s=selection; self.h=host; self.b=budget; self.j=journal
        self.members=None; self.prepared=None; self.actor_artifacts={}; self.actor_rows=[]
        self.model_rows={}; self.model_account={}; self.reference_rows=[]; self.grades=[]
        self.model_sequence=0; self.lifecycle=None; self.views=None; self.native=None
        self.primary_rows=None; self.primary_methods=None; self.declared_slots=0
        self.root_metadata_written=0
        self.actor_attempts=[]

    def record(self,name,value):
        body=encode(value); self.root_metadata_written+=len(body)
        need(self.root_metadata_written<=self.s['stage_caps']['root_metadata'],'complete original root metadata partition')
        return self.j.write(name,body)

    def model_setup(self):
        config=parse(capture(self.s['model']['configuration'],self.b))
        keys(config,('kind','request_bytes','maximum_input_tokens','maximum_output_tokens',
                     'seed','system_prompt'))
        need(config['kind']=='local_transformers_text_v1' and type(config['seed']) is int,
             'exact frozen local greedy configuration')
        self.model_configuration=config
        # Complete selected immutable checkpoint namespace is authenticated before
        # either service loads it. No discovery/download/remote code is supported.
        from pathlib import Path
        import os
        root=literal(self.s['model']['checkpoint_root'])
        need(os.statvfs(root).f_flag & os.ST_RDONLY,'selected complete checkpoint mount is read-only on owner')
        descriptors=self.s['model']['checkpoint_files']
        need(type(descriptors) is list and descriptors,'whole selected checkpoint manifest')
        expected={d['path'] for d in descriptors}
        need(len(expected)==len(descriptors) and all(not Path(x).is_absolute() and '..' not in Path(x).parts
             for x in expected),'canonical distinct checkpoint members')
        actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
        need(actual==expected and not any(p.is_symlink() for p in root.rglob('*')),
             'exact unlinked checkpoint namespace')
        for d in descriptors: verify_file({**d,'path':str(root/d['path'])},self.b)
        for arm in ('F','I'):
            setup_cpu=self.h.cpu()
            row=self.h.start('model-'+arm,'model',self.s['model']['role'],
                             {'arm':arm,'configuration':config},checkpoint=True)
            self.model_rows[arm]=row
            out=self.h.rpc(row,'initialize',{})
            need(out=={'initialized':True,'arm':arm,'qualification':False},'actual original resident initialization')
            row['startup_cpu']=row['group'].sample(); row['allocated_cpu']=0.0
            row['startup_whole_cpu']=self.h.cpu()-setup_cpu
            row['startup_wall']=time.monotonic()-row['origin']

    def model_call(self,actor,request):
        owner=actor['owner']; cell=(owner['session_id'],owner['condition'],owner['arm'])
        account=self.model_account.setdefault(cell,{'calls':0,'input_tokens':0,'output_tokens':0,'cpu':0.0,'wall':0.0})
        limits=self.s['actors'][owner['condition']][owner['arm']]['model_limits']
        keys(request,('messages','max_new_tokens'))
        config=self.model_configuration; maximum=request['max_new_tokens']
        need(type(maximum) is int and 0<maximum<=config['maximum_output_tokens'],'fixed output token cap')
        need(account['calls']+1<=limits['calls'] and
             account['input_tokens']+config['maximum_input_tokens']<=limits['input_tokens'] and
             account['output_tokens']+maximum<=limits['output_tokens'], 'complete model allocation before dispatch')
        # Unknown/failed returns retain the entire token reservation; no retry.
        account['calls']+=1; account['input_tokens']+=config['maximum_input_tokens']; account['output_tokens']+=maximum
        actor['model_usage']={'reservation_status':'pending','complete_cell_account':dict(account)}
        self.b.model_calls+=1; self.b.check('before original resident model dispatch')
        row=self.model_rows[owner['arm']]; before=row['group'].sample(); start=time.monotonic()
        self.model_sequence+=1
        request_owner={**owner,'request_ordinal':self.model_sequence}
        result=self.h.rpc(row,'generate',{'owner':request_owner,'request':request,
            'call_deadline':min(actor['deadline'],row['deadline'])},deadline=min(actor['deadline'],row['deadline']))
        self.h.poll(min(actor['deadline'],row['deadline']))
        need(result.get('owner')==request_owner,'actual exact arm/participant/request return')
        usage=result['usage']; keys(usage,('input_tokens','output_tokens'))
        need(type(usage['input_tokens']) is int and 0<usage['input_tokens']<=config['maximum_input_tokens']
             and type(usage['output_tokens']) is int and 0<=usage['output_tokens']<=maximum,
             'actual complete bounded token usage')
        account['input_tokens']+=usage['input_tokens']-config['maximum_input_tokens']
        account['output_tokens']+=usage['output_tokens']-maximum
        cpu=row['group'].sample()-before; need(cpu>=0,'original model CPU delta')
        row['allocated_cpu']+=cpu; account['cpu']+=cpu; account['wall']+=time.monotonic()-start
        actor['model_usage']={'reservation_status':'settled','complete_cell_account':dict(account)}
        return {'text':result['text'],'usage':usage}

    def point(self,owner):
        cell=(owner['session_id'],owner['condition'],owner['arm'])
        a=self.model_account.get(cell,{'calls':0,'input_tokens':0,'output_tokens':0,'cpu':0.0,'wall':0.0})
        return {'time':time.monotonic(),'read':self.b.read_bytes,'write':self.b.write_bytes,
                'whole_cpu':self.h.cpu(),'model':dict(a)}

    def charge(self,owner,row,start,phase,failed=False):
        cell=(owner['session_id'],owner['condition'],owner['arm'])
        current=self.model_account.get(cell,start['model']); before=start['model']
        final=row.get('group_final') or {}; native=final.get('cpu_seconds')
        need(type(native) in (int,float) and final.get('complete') is True,
             'complete actual candidate subtree CPU before lifecycle acceptance')
        observed={'wall_seconds':time.monotonic()-start['time'],
            'cpu_seconds':self.h.cpu()-start['whole_cpu'],
            'read_bytes':self.b.read_bytes-start['read'],'write_bytes':self.b.write_bytes-start['write'],
            'tool_calls':current['calls']-before['calls'],'fit_calls':int(phase in ('fit','investigation')),
            'provider_tokens':current['input_tokens']+current['output_tokens']-before['input_tokens']-before['output_tokens']}
        self.lifecycle.charge(*cell,phase,observed,failed=failed,evidence={
            'container':row['id'],'actual_closed_group':final,'model_account':deepcopy(current),
            'counter_scope':'managed owner bytes; fixed fit/RPC calls; serial active-cell whole-cgroup CPU delta including controller/daemon; actual provider tokens',
            'candidate_and_model_subtree_CPU':'nonadditive explanatory breakdown',
            'internal_candidate_fit_counts_and_physical_native_IO':'not separately measured',
            'qualification':False})

    def fit_actors(self,policies):
        commitments={'F':[],'I':[]}; sources={'F':[],'I':[]}
        for session in self.prepared:
            sid=session['session_id']
            for condition in CONDITIONS:
                train,val=calibration(session,condition,preparation.project_case)
                for arm in ('F','I'):
                    owner={'session_id':sid,'subject_id':session['subject_id'],'condition':condition,'arm':arm,
                           'case_id':None,'phase':'calibration'}
                    role=self.s['actors'][condition][arm]['role']; source=policies[(condition,arm)]
                    start=self.point(owner)
                    attempt={'owner':owner,'phase':'fit' if arm=='F' else 'investigation','started':start,
                             'complete_costs':False,'status':'attempted','row_key':'actor-fit-%03d'%len(self.actor_rows)}
                    self.actor_attempts.append(attempt)
                    row=self.h.start('actor-fit-%03d'%len(self.actor_rows),'actor',role,
                        {'arm':arm,'condition':condition,'policy_pin':pin(source),
                         'calibration':{'session_id':sid,'condition':condition,'train':train,'val':val}},policy_body=source)
                    row['owner']=owner; self.actor_rows.append(row)
                    result=self.h.rpc(row,'fit',{},self.model_call)
                    keys(result,('source_body','config_body','state_body'))
                    bodies={k:decode_body(v,role['artifact_bytes']) for k,v in result.items()}
                    if arm=='F': need(bodies['source_body']==source,'unchanged global F procedure')
                    captured=self.views.commit_actor(sid,arm,condition,**{
                        'source_body':bodies['source_body'],'config_body':bodies['config_body'],
                        'learned_state_body':bodies['state_body']})
                    self.h.close(row); self.charge(owner,row,start,'fit' if arm=='F' else 'investigation')
                    attempt.update(status='closed',complete_costs=True,container_id=row['id'])
                    self.actor_artifacts[(sid,condition,arm)]=result
                    commitments[arm].append({'session_id':sid,'condition':condition,
                        'config_identity':captured['configuration'],'parameter_identity':captured['state']})
                    sources[arm].append({'session_id':sid,'condition':condition,'source':captured['source']})
        return [{'method_id':'actor','kind':'actor','arm':a,
                 'method_source_identity':{'source_table':pin(sources[a]),'status':STATUS},
                 'commitments':commitments[a]} for a in ('F','I')]

    def actor_predict(self,session_id,condition,arm,view):
        session=next(s for s in self.prepared if s['session_id']==session_id)
        owner={'session_id':session_id,'subject_id':session['subject_id'],'condition':condition,'arm':arm,
               'case_id':view['case_id'],'phase':'inference'}
        start=self.point(owner); artifacts=self.actor_artifacts[(session_id,condition,arm)]
        attempt={'owner':owner,'phase':'inference','started':start,'complete_costs':False,
                 'status':'attempted','row_key':'actor-query-%06d'%len(self.actor_rows)}
        self.actor_attempts.append(attempt)
        row=self.h.start('actor-query-%06d'%len(self.actor_rows),'actor_predict',
            self.s['actors'][condition][arm]['role'],{'artifacts':artifacts})
        row['owner']=owner; self.actor_rows.append(row)
        result=self.h.rpc(row,'predict',{'view':view},self.model_call)
        expected={k:pin(decode_body(v,row['role']['artifact_bytes'])) for k,v in artifacts.items()}
        need(result.get('artifacts')==expected,'fresh prediction uses exact captured source/config/state')
        self.h.close(row); self.charge(owner,row,start,'inference')
        attempt.update(status='closed',complete_costs=True,container_id=row['id'])
        return result['p']

    def fit_references(self,sessions,conditions,tag):
        models={}; rows={}; results={}
        for session in sessions:
            sid=session['session_id']; shape=reference.shape_from_prepared(session)
            small={k:deepcopy(session[k]) for k in ('session_id','source_identity','unit_ids')}
            small['cases']=[deepcopy(c) for c in session['cases'] if c['split'] in ('train','val')]
            boot={'selection_identity':pin(self.s),'native_profile':self.native,'shape':shape,
                  'session':small,'conditions':list(conditions)}
            row=self.h.start(tag+'-ref-%02d'%len(rows),'reference',self.s['deployment']['reference_role'],boot)
            self.reference_rows.append(row); rows[sid]=row
            auth={'schema':'n059_native_capability_v1','profile_sha256':digest(self.native),
                'selection_identity':pin(self.s),'container_inspect':row['started_inspect'],
                'container_inspect_pin':pin(row['started_inspect']),'expected_cgroup':row['membership'],
                'worker_io':{k:row['role'][k] for k in ('journal_bytes','artifact_bytes')}}
            result=self.h.rpc(row,'fit',{'authorization':auth}); results[sid]=result
            expected={(c,f) for c in conditions for f in ('L','H')}
            got={(x['condition'],x['family']) for x in result['models']}
            need(got==expected and len(result['models'])==len(expected),'complete original reference model grid')
            for x in result['models']: models[(sid,x['condition'],x['family'])]=x['model']
            for c in conditions: models[(sid,c,'prior')]=result['prior']
            self.declared_slots+=17*len(conditions)
            self.record(tag+'-fit-%02d.json'%(len(rows)-1),result)
        return models,rows,results

    def reference_methods(self,models):
        methods=[]
        for family in ('L','H','prior'):
            rows=[]
            for s in self.prepared:
                for c in CONDITIONS:
                    model=models[(s['session_id'],c,family)]
                    if family=='prior':
                        commitment={'status':model['status'],'config_identity':pin({'family':'Laplace_prior'}),
                                    'parameter_identity':pin(model)}
                    else: commitment=reference.model_commitment(model)
                    need(commitment['status']=='available','complete available original reference panel')
                    rows.append({'session_id':s['session_id'],'condition':c,
                        'config_identity':commitment['config_identity'],'parameter_identity':commitment['parameter_identity']})
            methods.append({'method_id':family,'kind':'prior' if family=='prior' else 'reference','arm':'R',
                            'method_source_identity':reference.source_identity(),'commitments':rows})
        return methods

    def close_references(self,rows):
        for row in rows.values():
            self.h.close(row)
            result=row['close_result']
            need(result['object_handles_closed'] and not result['closure_errors'], 'complete reference handle closure')

    def close_models(self):
        for arm,row in self.model_rows.items():
            close_cpu=self.h.cpu(); close_wall=time.monotonic()
            self.h.close(row)
            remainder=row['group_final']['cpu_seconds']-row['allocated_cpu']
            need(remainder>=0,'separate resident startup/idle/retirement CPU remainder')
            row['retirement_whole_cpu']=self.h.cpu()-close_cpu
            row['retirement_wall']=time.monotonic()-close_wall
            # No hidden free setup. Equal allocation of physical service overhead
            # to the116 complete session/condition cells for each respective arm.
            for session in self.prepared:
                for condition in CONDITIONS:
                    measured=zero(); measured['cpu_seconds']=(row['startup_whole_cpu']+row['retirement_whole_cpu'])/116
                    measured['wall_seconds']=(row['startup_wall']+row['retirement_wall'])/116
                    self.lifecycle.charge(session['session_id'],condition,arm,'inference',measured,
                        evidence={'resident_service':row['id'],'kind':'equal116 original setup/retirement allocation',
                                  'resident_noncall_cpu_nonadditive_breakdown':remainder,
                                  'full_original_closed_group':row['group_final'],'qualification':False})

    def grade(self,operation,payload,producers,tag):
        completion=self.h.complete(producers)
        # Activation is target-last. No candidate/provider process remains live.
        need(all(r['closed'] for r in self.h.rows),'all previously selected roles closed before target-bearing grade')
        row=self.h.start(tag+'-grade','grade',self.s['deployment']['grade_role'],{'completion':completion})
        result=self.h.rpc(row,operation,payload); self.h.close(row)
        self.grades.append(row)
        self.record(tag+'-GRADE.json',{'report':result,'producer_completion':completion,
            'grader_closure':self.h.document(row),'qualification':False})
        return result

    def primary(self,actor_methods,models,workers):
        methods=self.reference_methods(models)+actor_methods
        with OwnedDirectory(self.j.root/'primary',self.s['stage_caps']['prediction_grade']) as out:
            journal=Journal(out,'predictions.jsonl',out.max_bytes)
            ctl=PanelController(self.prepared,self.members,methods,preparation.project_case,journal.append)
            try:
                while True:
                    request=ctl.next_case()
                    if request is None: break
                    sid=request['session_id']; responses=[]
                    for method in methods:
                        for condition in CONDITIONS:
                            view=request['views'][condition]; family=method['method_id']
                            if family=='prior': p=models[(sid,condition,family)]['probability_left']
                            elif method['arm']=='R':
                                p=self.h.rpc(workers[sid],'infer',{'family':family,'condition':condition,'view':view})['p']
                            else: p=self.actor_predict(sid,condition,method['arm'],view)
                            responses.append({'method_id':family,'arm':method['arm'],'condition':condition,
                                              'case_id':request['case_id'],'p':p})
                    ctl.commit(responses)
                captured=journal.seal()
                self.close_references(workers); self.close_models()
                producers=[*self.actor_rows,*workers.values(),*self.model_rows.values()]
                completion=ctl.finish(self.h.complete(producers))
                prepared,rows,methods=ctl.captured_scoring_operands()
                self.primary_rows=rows; self.primary_methods=methods
                self.record('PRIMARY_COMPLETION.json',{'completion':completion,'journal':captured,
                    'models':116*3,'actor_method_cells':232,'qualification':False})
                return self.grade('primary',{'prepared':prepared,'predictions':rows,'methods':methods},producers,'primary')
            finally: journal.close()

    def diagnostic(self,tag,replicate):
        conditions=CONDITIONS if tag=='D-label' else ('SHN','SBHN')
        label=tag+'-%02d'%replicate; altered=[]; transformations=[]
        for session in self.prepared:
            transformed=diagnostics.diagnostic_transform(session,tag,replicate)
            transformations.append(transformed); altered.append(transformed['prepared_session'])
        self.record(label+'-TRANSFORMS.json',transformations)
        models,workers,results=self.fit_references(altered,conditions,label)
        methods=deepcopy([m for m in self.primary_methods if m['arm']=='R'])
        primary=[deepcopy(r) for r in self.primary_rows if r['arm']=='R']
        failed=[]
        for method in methods:
            family=method['method_id']
            if family=='prior': continue
            for session in altered:
                sid=session['session_id']
                for c in conditions:
                    model=models[(sid,c,family)]
                    if model.get('status')!='available':
                        # Original diagnostics use the actual selection/refit
                        # records as unavailable commitments, never a fitted state.
                        holder=results[sid]['records'][1]['complete_panel_records']
                        entry=next(x for x in holder if x['family']==family and x['condition']==c)
                        replacement={'session_id':sid,'condition':c,'status':'unavailable',
                            'config_identity':pin(entry['selection']),'parameter_identity':pin(entry['refit']),
                            'error':'complete validation/refit unavailable'}
                        failed.append({'session_id':sid,'condition':c,'family':family,'model_status':model.get('status')})
                    else:
                        commitment=reference.model_commitment(model)
                        replacement={'session_id':sid,'condition':c,'config_identity':commitment['config_identity'],
                                     'parameter_identity':commitment['parameter_identity']}
                    method['commitments']=[replacement if x['session_id']==sid and x['condition']==c else x
                                           for x in method['commitments']]
        self.record(label+'-COMMITMENTS.json',{'methods':methods,'failed_cells':failed})
        def reused(f,c): return f=='prior' or c not in conditions
        reuse={(r['session_id'],r['case_id'],r['method_id'],r['condition']):r for r in primary
               if reused(r['method_id'],r['condition'])}
        need(len(reuse)==sum(reused(r['method_id'],r['condition']) for r in primary),'unique original reusable rows')
        if failed:
            rows=list(reuse.values()); self.close_references(workers)
            self.record(label+'-UNAVAILABLE.json',{'full_sessions':[s['session_id'] for s in self.prepared],
                'failed_cells':failed,'new_held_prediction_attempts':0,'all_reference_workers_closed':True})
        else:
            by_case={c['case_id']:c for s in altered for c in s['cases']}
            def project(case,condition,include_label=False):
                return preparation.project_case(by_case[case['case_id']],condition,include_label=include_label)
            with OwnedDirectory(self.j.root/label,self.s['diagnostic_output_bytes']) as out:
                journal=Journal(out,'predictions.jsonl',out.max_bytes)
                ctl=PanelController(self.prepared,self.members,methods,project,journal.append)
                try:
                    while True:
                        request=ctl.next_case()
                        if request is None: break
                        sid=request['session_id']; cid=request['case_id']; responses=[]
                        original_session=next(s for s in self.prepared if s['session_id']==sid)
                        original_case=next(c for c in original_session['cases'] if c['case_id']==cid)
                        for method in methods:
                            family=method['method_id']
                            for c in CONDITIONS:
                                if reused(family,c):
                                    original=reuse[(sid,cid,family,c)]; p=original['p']
                                    need(evaluation.build_prediction(original_session,original_case,method,c,p)==original,
                                         'exact unchanged original diagnostic reuse identity')
                                else:
                                    p=self.h.rpc(workers[sid],'infer',{'family':family,'condition':c,
                                                                    'view':request['views'][c]})['p']
                                responses.append({'method_id':family,'arm':'R','condition':c,'case_id':cid,'p':p})
                        ctl.commit(responses)
                    sealed=journal.seal(); self.close_references(workers)
                    completion=ctl.finish(self.h.complete(list(workers.values())))
                    unused,rows,methods=ctl.captured_scoring_operands()
                    self.record(label+'-COMPLETION.json',{'completion':completion,'journal':sealed})
                finally: journal.close()
        return self.grade('diagnostic',{'prepared':self.prepared,'primary':primary,'diagnostic':rows,
            'primary_methods':[m for m in self.primary_methods if m['arm']=='R'],
            'diagnostic_methods':methods,'tag':tag,'replicate':replicate},list(workers.values()),label)

    def run(self):
        policies=capture_policies(self.s,self.b)
        self.native=parse(capture(self.s['native_profile'],self.b)); validate_profile(self.native)
        need(self.native['image_id']==self.s['deployment']['reference_role']['image'],'native profile/actual reference image join')
        self.members=parse(capture(self.s['members'],self.b)); member_map(self.members)
        self.lifecycle=LifecycleLedger([m['eid'] for m in self.members],self.s['paired_cost_limits'],self.s['global_cost_limits'])
        self.lifecycle.global_development(self.s['measured_global_F'],self.s['global_F_evidence'])
        raw=parse(capture(self.s['raw_inputs'],self.b))
        self.prepared=preparation.prepare_all(raw,self.members,limits=self.s['preparation_limits']); del raw
        check_prepared(self.prepared,self.members); self.record('PREPARATION.json',self.prepared)
        holds=[{'session_id':s['session_id'],'holds':s['structural_holds']} for s in self.prepared if s['structural_holds']]
        if holds:
            self.record('UNAVAILABLE.json',{'holds':holds,'full_sessions':29,'no_fit_attempted':True})
            return {'status':'unavailable','qualification':False,'holds':holds}
        self.views=CalibrationViews(self.j.root/'calibration',self.prepared,self.members,preparation.project_case,
            {c:policies[(c,'F')] for c in CONDITIONS},self.s['stage_caps']['calibration'])
        try:
            self.model_setup(); actor_methods=self.fit_actors(policies)
            models,workers,results=self.fit_references(self.prepared,CONDITIONS,'primary')
            unavailable=[k for k,v in models.items() if v.get('status')!='available']
            if unavailable:
                self.close_references(workers); self.close_models()
                self.record('UNAVAILABLE.json',{'cells':[list(k) for k in unavailable],
                    'full_sessions':29,'all_reference_records_retained':True,'held_prediction_attempts':0})
                return {'status':'unavailable','qualification':False,'cells':unavailable}
            grade=self.primary(actor_methods,models,workers); diagnostic_grades=[]
            for tag in ('D-label','D-neural'):
                for replicate in range(20): diagnostic_grades.append(self.diagnostic(tag,replicate))
            need(self.declared_slots==61132,'all1972 primary plus59160 diagnostic declared fit slots')
            self.record('LIFECYCLE.json',self.lifecycle.report())
            return {'status':'source_only_complete_dispositions_unqualified','sessions':29,'animals':13,'labs':7,
                'primary_grade':grade,'diagnostic_grades':diagnostic_grades,'declared_reference_fit_slots':61132,
                'actual_fit_work':'original per-stage/grid/refit records; declared slots are not completed fits',
                'old_exposed93_pilot':'separate unchanged','scientific_qualification':False}
        finally:
            self.views.close()
