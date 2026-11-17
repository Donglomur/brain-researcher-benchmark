from .deadline import boundary
from .custody import Custody,custody,failure_notice,observation,reader_details
"""Complete DAG controller: immutable source, real work, terminal bank and barrier."""
from pathlib import Path
import time
from .errors import Refusal,require
from .objects import Reader,canonical,digest,fields,write_new,inventory,unique_paths
from .ledger import Ledger
from .exposure import Exposure
from .sources import Sources
from .process import Launcher
from .products import Collector
from .roster import Scope


class Controller:
    def begin_boundary(self,phase):
        if phase=='Controller.run_job':self.current_run_collection=None
        if phase=='Controller.register':
            if not hasattr(self,'registration_stack'):self.registration_stack=[]
            self.registration_stack.append(getattr(self,'current_registration',None))
            self.current_registration=None
        # This original-lifetime hold survives physical child retirement. All
        # ordinary controller operations, including bank/report closure, stop.
        if hasattr(self,'launcher'):self.launcher.require_accounting_closed()

    def release_boundary_success(self,phase):
        if phase=='Controller.run_job':self.current_run_collection=None
        if phase=='Controller.register':
            if self.current_registration is not None:self.sources.complete_registration(self.current_registration,self)
            self.current_registration=self.registration_stack.pop()

    def retain_boundary_failure(self,exc,phase):
        if phase=='Controller.register':
            try:
                if getattr(self,'current_registration',None) is not None:self.sources.reject_registration(self.current_registration)
            finally:self.current_registration=self.registration_stack.pop()
        if phase=='Controller.run_job' and getattr(self,'current_run_collection',None) is not None:
            # Collector's return is not the end of the original operation:
            # calibration freeze and the outer final authority check can fail.
            self.collector.reject_collection(self.current_run_collection)

    def __init__(self,root,scope,plan,authority,domain_roster,environment,mode):
        self.custody=Custody();self.guard=authority.check_current;self.guard()
        self.root=Path(root).absolute()
        require(authority.selection['output_root']==str(self.root),'unselected programme destination')
        require(authority.selection['environment']==environment['identity'] and authority.selection['domain_roster']==digest(canonical(domain_roster)),'environment/domain source identity')
        require(authority.selection['limits']==plan['resources'],'authority resource limits')
        self.root.mkdir(mode=0o700,exist_ok=False)
        self.scope=scope;self.plan=plan;self.authority=authority;self.mode=mode
        self.plan_receipt=scope.validate_plan(plan,production=mode=='production')
        require(authority.selection['plan']==self.plan_receipt['plan'],'authority plan identity')
        self.ledger=Ledger(self.root/'private-ledger',plan['resources']['metadata_bytes'])
        self.ledger.append('programme_begin',{'plan':self.plan_receipt,'authority':authority.identity,'mode':mode})
        self.exposure=Exposure(domain_roster,self.ledger,guard=self.guard)
        self.sources=Sources(self.root/'registered',self.exposure,self.ledger,[x['sha256'] for x in scope.sources['ordinary_author_files']],guard=self.guard)
        self.launcher=Launcher(self.root/'attempts',self.ledger,mode,environment,plan['resources']['aggregate'],guard=self.guard)
        self.collector=Collector(plan['required_products'],self.ledger,mode,guard=self.guard)
        self.jobs={x['id']:x for x in plan['jobs']};self.stage_receipts={};self.closed=None;self.frozen_states=set();self.case_states={};self.grading_results=None;self.support_admissions={}
        if mode=='production':
            from .references import reference_policies
            candidate_programmes={x['id'] for x in plan['programmes'] if x['role']=='candidate'}
            candidates={j['source'] for j in plan['jobs'] if j['programme'] in candidate_programmes}
            self.reference_policy_identities=reference_policies(plan['reference_policies'],scope,candidates)

    @boundary
    def register(self,context,source_root,manifest,entrypoint,interpreter,environment,role,parents=()):
        require(self.closed is None,'source registration after global barrier')
        sid=digest(canonical(manifest));expected=self.authority.selection['source_roots'].get(sid)
        actual={'root':str(Path(source_root).absolute()),'manifest':manifest,'entrypoint':entrypoint,'interpreter':interpreter,'environment':environment,'role':role,'context':context}
        require(expected==actual,'source registration not selected')
        transaction=self.sources.begin_registration(context,manifest,self)
        self.current_registration=transaction
        return self.sources.register(context,source_root,manifest,entrypoint,interpreter,environment,role,parents,transaction=transaction)

    @boundary
    def bind_products(self,job,source_key=None):
        """Plan names are producer references; hashes are bound after actual output."""
        result={}
        for name in job['expected_outputs']:
            spec=dict(self.plan['required_products'][name])
            def produced(identifier):
                require(identifier in self.collector.products,'unproduced state reference')
                return self.collector.products[identifier]['identity']
            spec['parent_states']=[produced(x) for x in spec['parent_states']]
            mandatory=[x for x in job['inputs'] if self.collector.products[x]['original_process'] is not None]
            spec['ancestry']=list(dict.fromkeys([*spec['ancestry'],*mandatory,*([source_key] if source_key is not None else [])]))
            require(all(x in self.collector.products or x in self.sources.registered for x in spec['ancestry']),'parent is neither a closed product nor registered source')
            spec['ancestry']=[produced(x) if x in self.collector.products else x for x in spec['ancestry']]
            require(all(x in self.exposure.artifacts for x in spec['ancestry']),'unadmitted parent artifact')
            if spec['kind']=='prediction':spec['state']=produced(spec['state'])
            if spec['kind']=='soup':
                spec['soup_members']=[produced(x) for x in spec['soup_members']];spec['soup_state']=produced(spec['soup_state'])
            result[name]=spec
        return result

    @boundary
    def admit_operator_product(self,job_id,descriptor,root):
        """Root-selected immutable operator facts; not a participant clean=true claim."""
        job=self.jobs[job_id];self.authority.job(job)
        require(job['stage'] in ('S01','S02','S03','S04','S14','S16'),'only selected ingest/support facts; closure/grade cannot be injected')
        require(job_id not in self.collector.terminal,'operator stage replay')
        expected=self.authority.selection['input_roots'].get(job_id)
        require(expected and expected['root']==str(Path(root).absolute()) and expected['operator_product']==descriptor,'unselected operator fact')
        reader=Reader(root,descriptor['bytes']+1,1,guard=self.guard)
        with observation(self,'operator_read',{'job':job_id,'descriptor':descriptor,'reader':None},'operator_read_observation',lambda d:d.update(reader=reader_details(reader))):
            obj=reader.json(descriptor)
        fields(obj,('job_id','stage','scope','products','upstream','qualification'))
        require(obj['job_id']==job_id and obj['stage']==job['stage'] and obj['scope']==self.scope.identity,'operator source scope')
        require(set(obj['products'])==set(job['expected_outputs']) and obj['qualification'],'incomplete operator product')
        require(set(obj['upstream'])==set(job['parent_jobs']) and all(x in self.collector.terminal and self.collector.terminal[x]['status']=='closed' for x in job['parent_jobs']),'operator upstream closure')
        for key,product in obj['products'].items():
            self.guard()
            require(key not in self.collector.products,'operator product replay')
            fields(product,('id','kind','details','objects'))
            require(product['id']==key and product['kind']==self.plan['required_products'][key]['kind'],'operator product type/identity')
            unique_paths(product['objects'])
            if self.mode=='production':
                from .support import admit_support_product
                admitted=admit_support_product(self,job,product)
                self.support_admissions.update(admitted)
            self.collector.products[key]={'identity':digest(canonical(product)),'product':product,'original_process':None,'output_root':str(Path(root).absolute()),'operator_selection':self.authority.identity,'qualified':False}
        self.collector.terminal[job_id]={'status':'closed','receipt':descriptor}
        self.ledger.append('operator_product_admitted',{'job':job_id,'object':descriptor,'selection':self.authority.identity})
        return obj

    @boundary
    def _complete_trusted(self,job,kind,details):
        require(job['id'] not in self.collector.terminal,'trusted stage replay')
        require(all(self.plan['required_products'][name]['kind']==kind for name in job['expected_outputs']),'trusted stage output type')
        evidence=self.ledger.append('trusted_stage_completed',{'job':job['id'],'kind':kind,'details':details,'upstream':job['parent_jobs']})
        for name in job['expected_outputs']:
            expected=self.plan['required_products'][name]
            require(expected['kind']==kind,'trusted stage output type')
            product={'id':name,'kind':kind,'details':details,'controller_source':self.authority.selection['implementation'],'original_controller_receipt':evidence}
            self.collector.products[name]={'identity':digest(canonical(product)),'product':product,'original_process':None,'operator_selection':self.authority.identity,'qualified':False}
        self.collector.terminal[job['id']]={'status':'closed','receipt':evidence}
        return evidence

    @boundary
    def admit_product_inputs(self,job):
        """Check original provenance before opening/copying a parent's objects."""
        for name in job['inputs']:
            require(name in self.collector.products,'missing declared parent product')
            record=self.collector.products[name];product=record['product']
            if record['original_process'] is not None:
                self.exposure.admit_reuse(record['identity'],job['context'])
            elif product['kind']=='grade':
                require(job['stage']=='S21' and self.grading_results is not None,'protected grader product is report-only')
            elif product['kind']=='freeze':
                require(job['stage'] in ('S14','S15','S16','S17','S21'),'freeze receipt not a development input')
            else:
                spec=self.plan['required_products'][name]
                require(spec.get('visibility')=='domain_view' and job['domain'] in spec.get('allowed_domains',[]),'private operator fact is not an actor input')
                grant=spec['view_exposure'];fields(grant,('labels','signals'))
                selection=self.authority.selection['input_roots'][job['id']]
                require(set(grant['labels'])<=set(selection['labels']) and set(grant['signals'])<=set(selection['signals']),'operator view observations exceed selected input grant')
        return True

    @boundary
    def run_job(self,job_id,source_key,input_root,input_manifest,payload):
        job=self.jobs[job_id];self.authority.job(job);self.authority.check_time(time.time_ns())
        require(job_id not in self.collector.terminal,'job already terminal')
        self.current_run_collection=job_id
        require(all(x in self.collector.terminal for x in job['parent_jobs']),'upstream jobs incomplete')
        require(all(self.collector.terminal[x]['status']=='closed' for x in job['parent_jobs']),'failed upstream cannot become valid input')
        require(self.scope.stage[job['stage']]['actor']=='participant_or_reference' or job['stage']=='S21','operator stage cannot be participant source')
        require(self.exposure.contexts[job['context']]['domain']==job['domain'],'job/context domain mismatch')
        if job['stage']=='S21':
            require(self.closed is not None and self.grading_results is not None,'scientific report source cannot run before closed grading')
            require(all(self.plan['required_products'][x]['kind']=='claim' for x in job['expected_outputs']),'report source cannot rewrite predictions/states')
        source=self.sources.resolve(source_key,job['context']);require(source['source_id']==job['source'],'job source not actual registration')
        if self.mode=='production':
            if job['stage']!='S05':
                builds=[self.collector.products[x]['product'] for x in job['inputs'] if x in self.collector.products and self.collector.products[x]['product']['kind']=='executable']
                require(len(builds)==1 and builds[0]['details']['source_id']==job['source'],'every scientific source operation consumes its actual completed build')
            programmes={x['id']:x for x in self.plan['programmes']};require(job['programme'] in programmes,'source programme missing')
            programme=programmes[job['programme']];domain=self.exposure.domains[job['domain']]
            expected_role='independent_reference' if programme['role']=='reference' else 'candidate_'+programme['arm']
            require(domain['role']==expected_role and domain['arm']==programme['arm'],'programme/domain role binding')
            if programme['role']=='reference':
                from .fixed_reference import validate_fixed_registered
                validate_fixed_registered(source,self.scope)
        selection=self.authority.selection['input_roots'].get(job_id)
        require(selection and selection['root']==str(Path(input_root).absolute()),'exact selected domain view root')
        if selection.get('from_products') is not None:
            require(set(selection['from_products'])==set(job['inputs']),'produced-input authority')
            expected_manifest=self.stage_receipts.get(('materialized_input',job_id))
            require(expected_manifest is not None and expected_manifest==input_manifest,'input not materialized from actual closed producer')
        else:require(selection['manifest']==input_manifest,'exact selected domain view')
        require(payload==job['payload'],'request payload differs from selected whole plan')
        actual=inventory(input_root,sum(r['bytes'] for r in input_manifest)+1,len(input_manifest)*4+1,guard=self.guard)
        require(actual==sorted((r['path'],r['bytes']) for r in input_manifest),'extra files visible in input view')
        reader=Reader(input_root,sum(r['bytes']+1 for r in input_manifest)+1,len(input_manifest)+1,guard=self.guard)
        self.ledger.ensure_capacity(8*len(canonical(input_manifest))+4096)
        with observation(self,'input_read',{'job':job_id,'reader':None},'input_read_observation',lambda d:d.update(reader=reader_details(reader))):
            for row in input_manifest:reader.read(row)
        self.admit_product_inputs(job)
        if job['stage'] in ('S15','S17'):
            require(self.exposure.contexts[job['context']]['sealed'] or self.exposure.contexts[job['context']]['case'] is not None,'query/calibration before method freeze')
        if job['stage']=='S15':
            ctx=self.exposure.contexts[job['context']]
            require(ctx['case'] is not None and not ctx['sealed'],'fresh own-case calibration context')
            require(any(self.plan['required_products'][x]['kind']=='state' for x in job['expected_outputs']),'calibration requires actual passive case state')
        if job['stage']=='S17':
            allowed=self.frozen_states|set(self.case_states.get(job['context'],[]))
            for output in job['expected_outputs']:
                spec=self.plan['required_products'][output]
                if spec['kind']=='prediction':
                    require(spec['state'] in self.collector.products and self.collector.products[spec['state']]['identity'] in allowed,'prediction state not frozen before query')
            require(all(self.collector.products[x]['product']['kind'] not in ('prediction','representation') for x in job['inputs']),'cross-query prediction/feature feedback')
            if self.mode=='production':
                queries=[self.plan['required_products'][x] for x in job['expected_outputs'] if self.plan['required_products'][x]['kind']=='prediction']
                require(len(queries)==1 and set(selection['signals'])==set(queries[0]['events']) and not selection['labels'],'one exact query partition, no extra visible observations')
        self.exposure.admit_inputs(job_id,job['context'],selection['labels'],selection['signals'],job['operation'])
        if self.mode=='production':
            for output in job['expected_outputs']:
                spec=self.plan['required_products'][output]
                if spec.get('purpose') in ('I-person','I-person-montage'):
                    cell=spec['dataset']+'|'+spec['condition']
                    require(cell in self.support_admissions and self.support_admissions[cell].get('status')!='unavailable','unavailable or unadmitted physical support cannot launch a learner/query')
        bound_specs=self.bind_products(job,source_key)
        if job['stage']=='S21':
            self.exposure.contexts[job['context']]['feedback_exposed']=True
            self.ledger.append('post_grade_feedback_exposure',{'context':job['context'],'job':job_id,'closed_bank':self.closed['receipt'],'future_learning_reuse':False})
        request={'schema':'reve-actor-request-v1','programme_id':job['programme'],'job_id':job_id,'task_id':'PAPER-paper-method-003','stage':job['stage'],
                 'operation':job['operation'],'source_id':source['source_id'],'domain':job['domain'],'context':job['context'],
                 'input_manifest':input_manifest,'parent_products':{k:self.collector.products[k]['identity'] for k in job['inputs']},
                 'expected_outputs':bound_specs,'payload':payload,
                 'input_root':'/input' if self.mode=='production' else str(Path(input_root).absolute()),'output_root':'/output' if self.mode=='production' else '.',
                 'resource_limits':job['resource_limit'],'mode':self.mode}
        self.ledger.append('input_view_admitted',{'job':job_id,'source_key':source_key,'manifest':input_manifest,'reader_cost':{'bytes':reader.bytes,'files':reader.files}})
        try:
            receipt,output=self.launcher.run(job_id,source,input_root,request,job['resource_limit'])
        except BaseException as exc:
            state=custody(self);state.fail(exc,'Controller.run_job:launch')
            owned=self.launcher.owned.get(job_id)
            if owned is not None:
                state.process=owned
                receipt=owned['receipt']
                try:self.collector.fail(job,receipt)
                except BaseException as secondary:state.add_secondary(secondary,'Controller.run_job:failed_collection')
            raise
        if not receipt['natural_completion']:
            self.collector.fail(job,receipt);return receipt
        try:
            admitted=self.collector.collect(job,receipt,output,self.exposure,bound_specs)
            if job['stage']=='S15':
                self.case_states[job['context']]=[v['identity'] for v in admitted.values() if v['product']['kind']=='state']
                require(self.case_states[job['context']],'calibration must produce actual passive case state')
                self.exposure.freeze(job['context'])
        except BaseException as exc:
            state=failure_notice(self,exc,'Controller.run_job:collection','collection_refusal',lambda:{'job':job_id,'original_error':custody(self).record(),'original_process':receipt})
            try:self.collector.fail(job,receipt)
            except BaseException as secondary:state.add_secondary(secondary,'Controller.run_job:failed_collection')
            raise
        return receipt

    def terminal_unavailable(self,job_id,reason):
        job=self.jobs[job_id];self.authority.job(job,custody_only=True)
        self.launcher.require_accounting_closed()
        require(not self.launcher.active and not self.collector.unresolved,'unresolved process scope cannot become unavailable')
        require(job_id not in self.collector.terminal and reason,'explicit unavailable slot')
        self.collector.terminal[job_id]={'status':'unavailable','receipt':None,'reason':reason}
        self.ledger.append('required_job_unavailable',{'job':job_id,'reason':reason,'products':job['expected_outputs']})

    @boundary
    def freeze(self,contexts,job_id=None):
        require(self.closed is None,'closed programme')
        if self.mode=='production' or job_id is not None:
            require(job_id in self.jobs and self.jobs[job_id]['stage']=='S13','declared S13 stage required')
            job=self.jobs[job_id];self.authority.job(job)
            require(contexts==job['payload']['contexts'] and all(x in self.collector.terminal and self.collector.terminal[x]['status']=='closed' for x in job['parent_jobs']),'complete exact freeze inputs')
        if self.mode=='production':
            coupled={j['context'] for j in self.plan['jobs'] if j['stage'] in ('S05','S06','S07','S08','S09','S10','S11','S12','S22')}
            require(set(contexts)==coupled,'whole pre-query source/domain freeze; no omitted scientific family')
        self.sources.freeze(contexts)
        self.frozen_states={v['identity'] for v in self.collector.products.values() if v['product'].get('kind') in ('state','soup') and v['product']['exposure_context'] in contexts}
        self.ledger.append('programme_source_freeze',{'contexts':contexts,'plan':self.plan_receipt})
        if job_id is not None:return self._complete_trusted(job,'freeze',{'contexts':contexts,'states':sorted(self.frozen_states),'plan':self.plan_receipt})

    @boundary
    def collect_banks(self,job_id):
        job=self.jobs[job_id];self.authority.job(job)
        require(job['stage']=='S18' and all(x in self.collector.terminal for x in job['parent_jobs']),'collection stage needs all producer terminal states')
        actual={x:self.collector.products[x]['identity'] for parent in job['parent_jobs'] for x in self.jobs[parent]['expected_outputs'] if x in self.collector.products}
        required={x for parent in job['parent_jobs'] for x in self.jobs[parent]['expected_outputs']}
        references=None
        if self.mode=='production':
            from .references import close_reference_bank
            references=close_reference_bank(self.plan['reference_policies'],self)
        return self._complete_trusted(job,'bank',{'products':actual,'missing':sorted(required-set(actual)),'terminal_jobs':{x:self.collector.terminal[x]['status'] for x in job['parent_jobs']},'scope':self.scope.identity,'reference_banks':references})

    @boundary
    def barrier(self,job_id=None):
        require(self.closed is None,'barrier replay')
        if self.mode=='production' or job_id is not None:
            require(job_id in self.jobs and self.jobs[job_id]['stage']=='S19','declared S19 stage required')
            job=self.jobs[job_id];self.authority.job(job)
            require(all(x in self.collector.terminal for x in job['parent_jobs']),'barrier upstream bank incomplete')
        require(not self.launcher.active and not self.collector.unresolved,'original process scope remains live or unobserved')
        if self.mode=='production':require(set(self.support_admissions)==set(self.plan['support_admission']),'complete physical support admission before targets')
        jobs=[j for j in self.plan['jobs'] if j['stage'] not in ('S19','S20','S21')]
        required={x for j in jobs for x in j['expected_outputs']}
        self.closed=self.collector.barrier(jobs,required)
        if self.mode=='production' or job_id is not None:
            self._complete_trusted(job,'barrier',self.closed)
        write_new(self.root/'CLOSED_BANK.json',canonical(self.closed),guard=self.guard)
        return self.closed

    @boundary
    def grade(self,job_id,target_root,target_index):
        from .grading import Grader
        job=self.jobs[job_id];self.authority.job(job)
        require(job['stage']=='S20' and self.closed is not None and self.grading_results is None,'single closed protected grading stage')
        grader=Grader(self,target_root,target_index)
        results=[]
        try:
            scoring=job['payload']['scoring']
            results=[]
            for row in scoring:
                self.guard()
                result=grader.score(row['prediction'],row['target'],row['purpose'])
                results.append({**row,'result':result})
            comparisons=grader.compare(job['payload']['comparisons'])
            audits=grader.audit_products(job['payload']['scientific_audits'])
            from .reductions import complete_reductions
            reductions=complete_reductions(self,grader,results,audits)
            self.grading_results={'scoring':results,'comparisons':comparisons,'scientific_audits':audits,'reductions':reductions,'reference_banks':getattr(grader,'reference_banks',{}),'manifest':digest(canonical(job['payload']))}
            self._complete_trusted(job,'grade',self.grading_results)
            return self.grading_results
        except BaseException as exc:
            failure_notice(self,exc,'Controller.grade','protected_grade_failed',lambda:{'job':job_id,'original_error':custody(self).record(),'completed_score_rows':results,'target_reader':reader_details(grader.reader),'product_read_reserved_bytes':grader.product_read_bytes,'product_consumed_bytes':grader.product_consumed_bytes,'product_partial_observations':grader.product_partial_observations,'ordinary_admission':False})
            raise

    @boundary
    def materialize_produced_input(self,job_id):
        """Acyclic recipe: selected producer names first, actual postimage pins later."""
        job=self.jobs[job_id];self.authority.job(job)
        selection=self.authority.selection['input_roots'][job_id]
        require(set(selection['from_products'])==set(job['inputs']),'complete producer input recipe')
        self.admit_product_inputs(job)
        destination=Path(selection['root']);planned=[];manifest=[]
        for name in selection['from_products']:
            self.guard()
            require(name in self.collector.products,'upstream producer absent')
            produced=self.collector.products[name];product=produced['product']
            if product['kind']=='freeze':
                value={'schema':'reve-local-freeze-view-v1','producer':name,'identity':produced['identity'],'scope':self.scope.identity,'source_id':job['source'],'frozen':True}
            elif job['stage']=='S21' and product['kind']=='grade':
                require(product['kind']=='grade' and self.grading_results is not None,'report sees only closed grader projection')
                # No target-store paths/labels, native-only audit details or another
                # candidate's source enter this public post-grading projection.
                arm=self.exposure.domains[job['domain']]['arm']
                selected=[{k:r[k] for k in ('arm','dataset','condition','reference','estimate','interval','p_value','holm_p','status') if k in r}
                          for r in self.grading_results['comparisons'] if r['arm']==arm]
                own={x['id'] for x in self.plan['programmes'] if x['arm']==arm or x['role']=='reference'}
                scientific=[]
                for row in self.grading_results['scoring']:
                    if row['programme'] in own and row['purpose']!='R-native':
                        scientific.append({**{k:row[k] for k in ('programme','case_id','run','purpose')},'result':{k:v for k,v in row['result'].items() if k in ('status','purpose','representation','metrics','events','people')}})
                value={'schema':'reve-post-grading-participant-view-v1','arm':arm,'comparisons':selected,'full_case_results':scientific,'source_and_states_remain_frozen':True,'trusted_reductions':self.public_reductions(arm)}
            else:
                if job['stage']=='S21':require(product['kind']=='executable','only closed public grading and own executable enter report')
                mapping=[{'original':obj,'materialized':digest(name.encode())+'/'+obj['path']} for obj in product.get('objects',[])]
                from .method_lineage import provenance
                value={'schema':'reve-produced-input-reference-v1','producer':name,'identity':produced['identity'],'product':product,'object_map':mapping,'provenance':provenance(produced),'method_lineage':produced.get('method_lineage')}
            path=digest(name.encode())+'.json';raw=canonical(value)
            planned.append({'path':path,'raw':raw,'source':None,'bytes':len(raw)})
            if job['stage']!='S21':
                for obj in product.get('objects',[]):
                    local=digest(name.encode())+'/'+obj['path']
                    planned.append({'path':local,'raw':None,'source':{'root':produced['output_root'],'object':obj},'bytes':obj['bytes']})
        require(sum(x['bytes'] for x in planned)<=selection['byte_cap'] and len(planned)<=selection['file_cap'],'whole produced-input reservation before copies')
        require(len({x['path'].casefold() for x in planned})==len(planned),'produced input collision')
        destination.mkdir(mode=0o700,exist_ok=False)
        source_read=0;source_consumed=0;read_observations=[];write_attempts=[];written=0
        custody(self).observations.append({'phase':'materialize','manifest':manifest,'readers':read_observations,'writes':write_attempts})
        try:
            for item in planned:
                self.guard()
                raw=item['raw']
                if item['source'] is not None:
                    origin=item['source'];reader=Reader(origin['root'],selection['byte_cap']+selection['file_cap']-source_read,selection['file_cap'],guard=self.guard)
                    details={'reader':None};read_observations.append(details)
                    def finish_read(d):
                        nonlocal source_read,source_consumed
                        source_read+=reader.bytes;source_consumed+=reader.consumed_bytes
                        d.update(reader=reader_details(reader))
                    with observation(self,'materialize_read',details,refresh=finish_read):
                        raw=reader.read(origin['object'])
                dest=destination/item['path'];self.guard();dest.parent.mkdir(mode=0o700,parents=True,exist_ok=True);write_attempts.append({'path':item['path'],'requested_bytes':len(raw)})
                write_new(dest,raw,guard=self.guard);written+=len(raw)
                from .objects import pin
                manifest.append(pin(raw,item['path']))
        except BaseException as exc:
            failure_notice(self,exc,'Controller.materialize','produced_input_failed',lambda:{'job':job_id,'recipe':selection,'original_error':custody(self).record(),'partial_manifest':manifest,'source_read_bytes_plus_EOF':source_read,'consumed_source_bytes':source_consumed,'read_observations':read_observations,'write_attempts':write_attempts,'written_bytes_acknowledged':written,'eligible':False})
            raise
        self.stage_receipts['materialized_input',job_id]=manifest
        self.ledger.append('produced_input_materialized',{'job':job_id,'recipe':selection,'actual_manifest':manifest,'source_read_bytes_plus_EOF':source_read,'consumed_source_bytes':source_consumed,'read_observations':read_observations})
        return destination,manifest

    @boundary
    def final_report(self):
        from .reporting import report
        require(self.grading_results is not None and set(self.collector.terminal)==set(self.jobs),'full report requires all22 stages and all source reports terminal')
        case_rows=[]
        for case in self.scope.ids:
            members=[x for x in self.grading_results['scoring'] if x['case_id']==case]
            case_rows.append({'case_id':case,'status':'scored' if members and all(x['result']['status']=='scored' for x in members) else 'unavailable','programme_run_results':members})
        claims={k:v['product'] for k,v in self.collector.products.items() if v['product'].get('kind')=='claim'}
        result=report(self,case_rows,self.grading_results['comparisons'],claims)
        write_new(self.root/'REPORT.json',canonical(result),guard=self.guard)
        return result

    def public_status(self):
        return {'schema':'reve-build-status-v1','scope':self.scope.identity,'legacy_cases':2144,'fewshot_cases':1800,'mandatory_principal_products':113,
                'closed_jobs':len(self.collector.terminal),'expected_jobs':len(self.plan['jobs']),'closed_products':len(self.collector.products),'expected_products':len(self.plan['required_products']),
                'all_scientific_gates_open_in_this_build':True,'scientifically_qualified':False,'submission_ready':False,'mode':self.mode}

    @boundary
    def public_reductions(self,arm):
        reduction=self.grading_results['reductions'];own={p['id'] for p in self.plan['programmes'] if p['arm']==arm or p['role']=='reference'}
        def clean(value):
            if isinstance(value,list):return [clean(v) for v in value]
            if isinstance(value,dict):return {k:clean(v) for k,v in value.items() if k not in ('target','test_target','validation_target','target_identity','oracle','independent_source','actual_member_identity','selected_run_pairs')}
            return value
        families=reduction['family_reductions']
        result={'case_run_reductions':[x for x in reduction['case_run_reductions'] if x['programme'] in own and x['purpose']!='R-native'],'family_reductions':{k:[x for x in v if x['programme'] in own and x['purpose']!='R-native'] for k,v in families.items()},'fewshot':[x for x in reduction['fewshot'] if x['programme'] in own and x['purpose']!='R-native'],'soups':[x for x in reduction['soups'] if x['programme'] in own and x['purpose']!='R-native'],'missing_and_failed_cases_retained':True,'scientifically_qualified':False}
        audits=[]
        for row in reduction['scientific_audits']:
            spec=self.plan['required_products'].get(row.get('product'),{})
            if spec.get('programme') in own and spec.get('purpose') in ('R-paper','I-person','I-person-montage'):
                audits.append({k:v for k,v in row.items() if k in ('product','kind','status','reason','scalar_agrees','arithmetic_agrees','agrees','scientifically_qualified')})
        result['scientific_audit_dispositions']=audits
        result['all_private_source_audits_retained_in_trusted_report']=True
        return clean(result)
