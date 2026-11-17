"""Indivisible full EEGPT programme: source admission to protected reporting.

The public operation accepts configuration and actual submitted source roots,
never prediction files, fit callbacks, asserted native receipts or a score.
Every required reference remains scheduled when a candidate abstains/fails.
"""
import copy,os
from pathlib import Path
from .protocol import validate_code_source_manifest,HandleCustody,boundary,budget_method,Directory,fields,need,descriptor,digest,identity,encode,decode,persist,read_metadata,stream_capture,observation,Refusal,exact_tree,seal_tree,persist_chunks,relative
from .budget import Budget,CoupledBudget,COUNTERS
from .custody import Issuer
from .scope import Scope,CONTRACT_NAMES,validate_census,CONTROLS
from .information import Projection,validate_source_manifest
from .schedule import Schedule
from .execution import LinuxCPUExecutor
from .session import Session
from .learning import LocalLearning
from .products import Collection,scientific_completion
from .grading import ProtectedGrader


def selected_json(root,member,budget):return decode(read_metadata(root,member,cap=budget.limits['metadata_bytes'],ledger=budget))


def source_snapshot(selected,destination,issuer,budget,*,environment,resources,role):
    fields(selected,('root','manifest'),'actual complete original source admission');captures=[]
    with HandleCustody('source_snapshot:'+role) as owned:
        root=owned.own(Directory(selected['root']),'source');target=owned.own(Directory(str(destination)),'destination')
        manifest=selected_json(root,selected['manifest'],budget);validate_source_manifest(manifest,genesis_environment=environment,allowed_resources=resources)
        for member in manifest['files']:
            (target.path/Path(member['path']).parent).mkdir(parents=True,exist_ok=True);captures.append(stream_capture(root,member['path'],expected=member,ledger=budget,cap=budget.limits['per_file_bytes'],destination=target,destination_name=member['path']))
        pin=persist(target,'SOURCE.json',encode(manifest),ledger=budget);exact_tree(target,manifest['files'],extra=('SOURCE.json',));seal_tree(target);receipt=issuer.admit_static('static_source',{'role':role,'source_identity':identity(manifest),'source_manifest':pin,'captures':captures,'actual_source_before_any_data_exposure':True})
        return {'manifest':manifest,'identity':identity(manifest),'host_root':str(target.path),'receipt':receipt}


def admit_reference_source(source,manifest):
    """Full ordered closure, not a length-only or participant-selected join."""
    validate_code_source_manifest(manifest);closure=manifest['reference_source_closure'];fields(closure,('files','entrypoint','operative_source_identity'),'complete selected reference closure')
    need(type(manifest['reference_source_members']) is int and manifest['reference_source_members']==len(manifest['operative_members']),'reference count is descriptive metadata')
    need(closure['files']==manifest['operative_members'] and closure['operative_source_identity']==manifest['operative_source_identity']==identity(manifest['operative_members']),'exact complete ordered operative reference identity')
    need(closure['entrypoint']==['/runtime/python','/source/reference_worker.py'],'exact source-owned original reference entrypoint')
    need(source['manifest']['files']==closure['files'] and source['manifest']['entrypoint']==closure['entrypoint'] and source['identity']==identity(source['manifest']),'actual full source-owned reference closure, not a participant-selected replacement')
    return closure


class OperationCustody:
    """Original inner owner exists before clocks, construction or publication.

    Budget objects and exceptions stay strongly held. The serializable ledger
    view reads their actual fields without report(), a fresh clock or identity.
    Its values are original records, never fabricated successful observations.
    """
    def __init__(self):
        self.programme=None;self.budget_owners={};self.original_exception=None;self.secondary_exceptions=[];self.local_handle_owners=[];self.failure_observations=[];self.received_exception_objects=[]
        self.terminal={'schema':'eegpt_original_operation_terminal_v1','stage':'not_started','original_failure':None,'result_identity':None,'source_scope_identity':None,'targets_open':False,'scientifically_complete':False,'scientific_operation_retried':False,'original_close_failures':[],'publications':{},'work_handle_final_close_pending':False,'terminal_publication_accounting_in_outside_observation':True}
        self.outside={'final_observed_ns':None,'original_deadline_ns':None,'original_terminal':None,'original_terminal_identity':None,'work_handle_close':None,'final_known_counters':None,'final_reserved_counters':None,'costs_complete':False,'late_failure':None}
        self.record={'schema':'eegpt_original_inner_custody_v1','phase':'before_programme_construction','original_failure':None,'secondary_failures':[],'original_failure_records':[],'original_resource_ledger':{},'original_terminal':self.terminal,'outside_final_closure':self.outside,'handle_closes':[],'publication_attempts':[],'accounting_observation_failure':False,'same_original_budget_owners':True,'scientific_operation_retried':False}
    def fail(self,phase,exc):
        self.received_exception_objects.append(exc)
        carrier=exc.__dict__ if type(exc) is Refusal else {}
        if carrier.get('original_operation_custody') is self:return
        local=carrier.get('original_handle_custody')
        if local is not None:
            if any(local is prior for prior in self.local_handle_owners):return
            self.local_handle_owners.append(local);self.record.setdefault('local_handle_custody',[]).append(local.record)
            self.fail(phase+':local_primary',local.original_exception)
            for error in local.secondary_exceptions:self.fail(phase+':local_close',error)
            return
        if exc is self.original_exception or any(exc is prior for prior in self.secondary_exceptions):return
        # Retain the actual object before any exception text/property is read.
        if self.original_exception is None:self.original_exception=exc
        else:self.secondary_exceptions.append(exc)
        try:
            detail=observation(exc);self.failure_observations.append(detail)
            self.secondary_exceptions.extend(detail.description_exceptions)
        except BaseException as secondary:
            self.secondary_exceptions.append(secondary);detail={'kind':type(exc).__name__,'reason':'original exception text/observation unavailable','observation':None,'exception_description_failure':type(secondary).__name__}
        row={'phase':phase,**detail}
        if self.record['original_failure'] is None:self.record['original_failure']=row
        else:self.record['secondary_failures'].append(row)
        self.record['original_failure_records'].append(row);self.outside['late_failure']=self.record['original_failure']
        if phase.startswith(('account_publication:','capture_','final_original_budget')):self.record['accounting_observation_failure']=True;self.outside['costs_complete']=False
    def attempt(self,phase,operation):
        self.record['phase']=phase
        try:return operation()
        except BaseException as exc:self.fail(phase,exc)
    def ledger(self):
        p=self.programme
        if p is None:return
        budgets=[('campaign',p.budget),('operator',None if p.operator is None else p.operator.episode),*p.episode_budgets.items()]
        names=('label','origin','deadline','limits','reserved','known','unknown','failures','jobs','files_reserved','peak_resident','peak_gpu_resident')
        for name,budget in budgets:
            if budget is None:continue
            self.budget_owners[name]=budget
            self.record['original_resource_ledger'][name]={key:getattr(budget,key) for key in names}
        self.record['original_failure_records']=p.failure_records
    def refusal(self):
        error=Refusal('original complete EEGPT operation did not complete',observation=self.record)
        error.original_operation_custody=self
        return error


class Programme:
    def __init__(self,package_root,configuration,*,origin=None,deadline=None,custody=None):
        self.custody=OperationCustody() if custody is None else custody
        self.budget=None;self.operator=None;self.issuer=None;self.executor=None;self.session=None;self.learning=None;self.projection=None;self.scope=None;self.schedule=None;self.collection=None;self.sources={};self.data_roots={};self.episode_budgets={};self.episode_ids={};self.common={};self.selectors={};self.queries={};self.failure_records=self.custody.record['original_failure_records'];self.stage='not_started';self.paths={};self.terminal=self.custody.terminal;self.outside_closure=self.custody.outside;self.terminal_pool=None
        self.custody.programme=self
        self.original_origin=__import__('time').monotonic_ns() if origin is None else origin;self.original_deadline=deadline
        self.package=Path(package_root);self.config=configuration
    def _global(self):
        if self.issuer:self.issuer.budget=self.operator
        if self.executor:self.executor.ledger=self.operator
        if self.session:self.session.budget=self.operator
        if self.projection:self.projection.budget=self.operator
        if self.learning:self.learning.budget=self.operator
    def _episode(self,eid):
        b=CoupledBudget(self.budget,self.episode_budgets[eid]);self.issuer.budget=b;self.executor.ledger=b;self.session.budget=b;self.projection.budget=b;self.learning.budget=b;return b
    def _authority(self):
        config=self.config
        fields(config,('schema','work_root','campaign_limits','operator_limits','episode_limits','job_policy','genesis','qualification','source_packages','resources','data_roots','development_label_root','target_root','census','qualified_population','study','input_metadata_root','executor','source_binary_root','corpus_supports','episode_parent_selection','static_episode_resources','scientific_adjudication','release_policy','terminal_policy'),'complete indivisible operation configuration')
        need(config['schema']=='eegpt_complete_operation_v1','whole original operation profile');g=config['qualification'];fields(g,('operative_source_identity','scope_identity','gates','source_manifest','evidence_root','gate_evidence_manifest','selection_identity'),'original qualification for this exact operative source/scope');digest(g['operative_source_identity']);digest(g['selection_identity']);need(set(g['gates'])=={'G%02d'%i for i in range(1,25)},'all24 original independent qualification gates')
        for gate,row in g['gates'].items():
            fields(row,('status','evidence','operative_source_identity','scope_identity'),'actual source/scope-bound gate')
            need(row['status']=='qualified' and row['evidence'] and row['operative_source_identity']==g['operative_source_identity'] and row['scope_identity']==g['scope_identity'],'unconfigured/unqualified original gate '+gate)
            digest(row['evidence'])
        frozen_science={k:config[k] for k in ('census','qualified_population','study','scientific_adjudication','source_packages','resources','corpus_supports','episode_parent_selection','static_episode_resources','release_policy')};need(g['selection_identity']==identity(frozen_science) and config['genesis']['qualification']==g['selection_identity'],'all source/data/analysis/reference/tolerance choices fixed together before G0, no unbound scoring policy')
        fields(config['scientific_adjudication'],('operative_source_identity','diagnostics','historical','exchangeability','within_family_pairing'),'complete original scientific adjudication policy');need(config['scientific_adjudication']['operative_source_identity']==g['operative_source_identity'],'actual selected protected scorer source')
        need(set(config['source_packages'])=={'A','B','reference'},'both arbitrary participant procedures and separate independent trusted producer')
        need(config['genesis']['budget_policy']=={'campaign':config['campaign_limits'],'operator':config['operator_limits'],'episode':config['episode_limits'],'job':config['job_policy']},'G0 actual complete funding policy fixed before source/data exposure')
    def _setup(self):
        self.stage='source_and_configuration_admission';self._authority();c=self.config
        self.budget=Budget(c['campaign_limits'],origin=self.original_origin,deadline=self.original_deadline,label='whole original EEGPT operation');operator_local=Budget(c['operator_limits'],origin=self.budget.origin,deadline=self.budget.deadline,label='operator view of same whole operation');self.operator=CoupledBudget(self.budget,operator_local)
        # This original terminal allowance is reserved before work-path or
        # metadata admission can fail. It is not reset by an exception/retry.
        fields(c['terminal_policy'],('ledger_bytes','failures_bytes','terminal_bytes'),'full original failure-publication reserve')
        self.terminal_pool=dict(c['terminal_policy'])
        for cap in self.terminal_pool.values():self.operator.reserve('output_bytes',cap);self.operator.reserve_file()
        root=Directory(c['work_root']);self.work=root
        for name in ('journal','sources','calls','views','private-scoring','reports'):
            os.mkdir(name,0o700,dir_fd=root.fd);self.paths[name]=root.path/name
        journal=Directory(str(self.paths['journal']));self.journal_handle=journal;self.issuer=Issuer(journal,self.operator)
        with HandleCustody('package_source') as owned:
            package=owned.own(Directory(str(self.package)),'package')
            manifest=validate_code_source_manifest(selected_json(package,c['qualification']['source_manifest'],self.operator))
            need(manifest['operative_source_identity']==identity(manifest['operative_members'])==c['qualification']['operative_source_identity'],'same selected complete operative source manifest')
            for member in manifest['operative_members']:stream_capture(package,member['path'],expected=member,ledger=self.operator,cap=self.operator.limits['per_file_bytes'])
            contracts={name:selected_json(package,manifest['contracts'][name],self.operator) for name in CONTRACT_NAMES};self.scope=Scope(contracts);need(self.scope.identity==c['qualification']['scope_identity']==c['genesis']['scope_identity'],'same exact accepted entire scientific scope')
        with HandleCustody('qualification_evidence') as owned:
            evidence_root=owned.own(Directory(c['qualification']['evidence_root']),'evidence_root')
            evidence=selected_json(evidence_root,c['qualification']['gate_evidence_manifest'],self.operator);fields(evidence,('schema','root_selection_identity','gates'),'complete independently selected gate evidence index');need(evidence['schema']=='eegpt_gate_evidence_index_v1' and evidence['root_selection_identity']==c['qualification']['selection_identity'] and set(evidence['gates'])==set(c['qualification']['gates']),'complete actual source/science-bound qualification index')
            for gate,member in evidence['gates'].items():
                need(member['sha256']==c['qualification']['gates'][gate]['evidence'],'same original selected full gate evidence bytes');body=selected_json(evidence_root,member,self.operator);fields(body,('schema','gate','status','operative_source_identity','scope_identity','root_selection_identity','original_review_or_execution_receipts','limitations'),'actual complete qualification record');need(body['schema']=='eegpt_independent_gate_evidence_v1' and body['gate']==gate and body['status']=='qualified' and body['operative_source_identity']==manifest['operative_source_identity'] and body['scope_identity']==self.scope.identity and body['root_selection_identity']==evidence['root_selection_identity'] and body['original_review_or_execution_receipts'],'selected actual independent evidence, not a bare qualified Boolean')
                if gate=='G07':
                    provenance=body['original_review_or_execution_receipts'];need(type(provenance) is dict and provenance.get('complete_population_manifest')==c['qualified_population'] and provenance.get('original_receipts'),'G07 actual independently selected full population and historical/prospective split qualification')
        for role,selected in c['source_packages'].items():
            path=self.paths['sources']/role;os.mkdir(path,0o700);self.sources[role]=source_snapshot(selected,path,self.issuer,self.operator,environment=c['genesis']['source_and_environment_identity'],resources=c['genesis']['common_resources'],role=role)
        # Trusted reference source is additionally pinned to the independently
        # accepted package source identity, not selected by participant code.
        admit_reference_source(self.sources['reference'],manifest)
        self.resource_receipts={};self.resource_bindings={}
        for name,resource in c['resources'].items():
            relative(name);need(len(Path(name).parts)==1,'single opaque static resource identifier')
            fields(resource,('root','members','kind','qualification','eligible_roles','guest_root'),'complete original pre-exposure static capability');digest(resource['qualification']);need(resource['kind'] in ('scientific_documents','author_code','qualified_pretrained_state','qualified_reference_recipes','qualified_software_dependency'),'static resources cannot smuggle raw downstream records, labels or adaptive histories');captures=[]
            with HandleCustody('static_resource:'+name) as owned:
                r=owned.own(Directory(resource['root']),'source');snapshot_path=self.paths['sources']/('resource-'+name);os.mkdir(snapshot_path,0o700);snapshot=owned.own(Directory(str(snapshot_path)),'snapshot')
                for member in resource['members']:
                    (snapshot.path/Path(member['path']).parent).mkdir(parents=True,exist_ok=True)
                    captures.append(stream_capture(r,member['path'],expected=member,ledger=self.operator,cap=self.operator.limits['per_file_bytes'],destination=snapshot,destination_name=member['path']))
                exact_tree(snapshot,resource['members']);seal_tree(snapshot)
            receipt=self.issuer.admit_static('static_resource',{'name':name,'kind':resource['kind'],'inventory':resource['members'],'actual_original_captures':captures,'qualification':resource['qualification'],'eligible_roles':resource['eligible_roles']});self.resource_receipts[name]=receipt;self.resource_bindings[name]={'host':str(snapshot_path),'guest':resource['guest_root'],'identity':identity(resource['members'])}
        need(set(self.resource_receipts)==set(c['genesis']['common_resources']),'no undeclared static resource or missing original common capability')
        self.issuer.freeze_genesis(c['genesis'],[v['receipt'] for v in self.sources.values()],list(self.resource_receipts.values()))
        with HandleCustody('input_metadata') as owned:
            metadata=owned.own(Directory(c['input_metadata_root']),'metadata')
            self.census=selected_json(metadata,c['census'],self.operator);self.qualified_population=selected_json(metadata,c['qualified_population'],self.operator);self.study=selected_json(metadata,c['study'],self.operator)
        boundary(self.operator,'complete_census_validation',validate_census,self.census,self.scope,self.qualified_population)
        self.operator.guard('before_original_data_directories')
        for name,path in c['data_roots'].items():self.data_roots[name]=Directory(path)
        self.development_labels=Directory(c['development_label_root'])
        # Store the target root path only; no target directory/file/header open
        # occurs here or during source, fit, selection or query phases.
        self.projection=Projection(self.census,os.urandom(32),self.data_roots,self.issuer,self.operator,development_label_root=self.development_labels,target_root=c['target_root'])
        self.schedule=boundary(self.operator,'complete_schedule_constructor',Schedule,self.scope,self.census,self.study,self.projection,c['genesis']['scientific_policy']);self.collection=boundary(self.operator,'complete_collection_constructor',Collection,copy.deepcopy(self.schedule.expected),self.issuer)
        from .contrasts import graph,validate_pairing_policy
        contrasts=boundary(self.operator,'complete_contrast_graph',graph,self.schedule.classifications);boundary(self.operator,'complete_pairing_policy',validate_pairing_policy,contrasts,c['scientific_adjudication']['within_family_pairing'],c)
        # Complete per-E allocations plus operator allowance are funded before
        # any candidate can consume shared capacity and starve a required bank.
        for dimension in COUNTERS:
            need(c['campaign_limits'][dimension]>=c['operator_limits'][dimension]+len(self.schedule.episodes)*c['episode_limits'][dimension],'whole full programme funds every original episode and reference '+dimension)
        self.operator.guard('before_original_executor_constructor');binaries=Directory(c['source_binary_root']);self.binary_root=binaries;self.executor=LinuxCPUExecutor(c['executor'],binaries,self.operator);self.session=Session(self.paths['calls'],self.issuer,self.operator,self.executor);self.learning=LocalLearning(self.issuer,self.session,self.projection,c['genesis'],{a:self.sources[a] for a in ('A','B')},self.sources['reference'],self.operator,c['job_policy'])
        self._global()
    def _create(self,key,plan,parents):
        c=self.config;budget=Budget(c['episode_limits'],deadline=self.budget.deadline,label='original episode '+key);coupled=CoupledBudget(self.budget,budget);self.issuer.budget=coupled
        names=c['static_episode_resources'].get(key,[]);static={}
        for name in names:
            need(name in self.resource_bindings,'actual G0 static resource');role=plan['spec']['actor_role']+':'+plan['spec']['access'];need(role in c['resources'][name]['eligible_roles'],'exact actual role/access static resource');static[name]=self.resource_bindings[name]
        eid=self.learning.create(plan,[p['common_receipt'] for p in parents],static);self.episode_budgets[eid]=budget;self.episode_ids[key]=eid;self._episode(eid);return eid
    def _views(self,eid,plan,repetition,roles):
        spec=plan['spec'];out={};parents=[self.learning.episodes[eid]['context']]
        if self.learning.episodes[eid]['development_close'] is not None:parents.append(self.learning.episodes[eid]['development_close'])
        for role in roles:
            path=self.paths['views']/(eid+'-'+str(repetition)+'-'+role);os.mkdir(path,0o700)
            if spec['dataset']=='CORPUS':
                parent=plan['pretraining'][0];support=self.config['corpus_supports'][parent['corpus_support']];out[role]=self.projection.materialize_corpus(eid,support,role,path,parents)
            else:out[role]=self.projection.materialize(eid,spec['dataset'],int(spec['outer_fold'][1:]),spec['mode'],role,path,parents,repetition=repetition)
        return out
    def _collect_result(self,eid,result):
        need(result['phase']=='captured','only actual original fully captured outputs')
        for product in result['response']['products']:
            pid=product['product_id'];need(pid in self.collection.expected,'original selected scientific obligation')
            expected=self.collection.expected[pid];need(product['support_identity']==expected['support_identity'] and product['scope']==expected['scope'],'same actual complete scientific scope/support')
            # Public parent identities were supplied before the original call;
            # the private original process is added here after it completed.
            original=self.issuer.verify(result['process_receipt'],'process');need(product['parents']==[r['record_sha256'] for r in original['parents']],'actual original call parents, no future self-reference')
            from .products import admit_producer
            admit_producer(expected,result['process_receipt'],self.issuer);receipt=self.issuer.publish_local(eid,'capture',[result['process_receipt'],result['capture_receipt']],{'product_identity':identity(product),'response_identity':identity(result['response']),'product_id':pid,'actual_capture_root_identity':identity(result['capture_dispositions'])},repetition=product['scope'].get('repetition'),query=self.issuer.episodes[eid]['status']=='closed_development')
            self.collection.add(product,receipt,result['process_receipt'])
    def _failed_episode(self,eid,error):
        row=self.learning.episodes[eid];failure={'episode':eid,'original_scope':row['plan']['spec'],'phase':self.stage,**observation(error)};self.failure_records.append(failure);row['failures'].append(failure)
        if self.issuer.episodes[eid]['active_processes']:return
        if self.issuer.episodes[eid]['status']=='development':self.learning.seal(eid)
        if row['plan']['spec']['dataset']=='CORPUS' and self.issuer.episodes[eid]['status']!='closed':
            row['failed_corpus_disposition']={'reusable_common_parent':False,'failure':failure,'all_required_product_ids':[p['product_id'] for p in row['plan']['diagnostics']]}
            row['selected'].clear()
            self.issuer.close_episode(eid,[],reason='original corpus producer unavailable after verified cleanup; every dependent obligation remains required')
    def _corpus(self):
        self.stage='complete_original_corpus_producers'
        for plan in self.schedule.pretraining:
            key=plan['original_scope_identity'];eid=self._create(key,plan,[])
            try:
                views=self._views(eid,plan,None,('corpus_train','corpus_validation'));eligible=[p['spec'] for k,p in self.schedule.episodes.items() if key in self.config['episode_parent_selection'].get(k,[])];need(eligible,'actual eligible descendant set for complete required parent')
                result=self.learning.pretrain(eid,views,eligible,self.census['overlap']['evidence']);self.common[key]=result
                # Corpus producer was closed only after all actual diagnostics;
                # its products are already source/capture-bound. Collection uses
                # a post-close immutable host receipt, not a new agent operation.
                for output in self.learning.episodes[eid]['outputs']:self._collect_closed_corpus(eid,output)
            except BaseException as exc:self._failed_episode(eid,exc)
            self._global()
    def _collect_closed_corpus(self,eid,result):
        for product in result['response']['products']:
            pid=product['product_id'];expected=self.collection.expected[pid];original=self.issuer.verify(result['process_receipt'],'process');need(product['parents']==[r['record_sha256'] for r in original['parents']],'original completed corpus call parents')
            from .products import admit_producer
            admit_producer(expected,result['process_receipt'],self.issuer)
            receipt=self.issuer._issue('capture',self.issuer.episodes[eid]['scope'],[result['process_receipt'],result['capture_receipt']],{'product_identity':identity(product),'product_id':pid,'immutable_corpus_collection':True});self.collection.add(product,receipt,result['process_receipt'])
    def _development(self):
        self.stage='all_original_downstream_development'
        for key,plan in self.schedule.episodes.items():
            if plan['spec']['dataset']=='CORPUS':continue
            selected=self.config['episode_parent_selection'].get(key,[]);parents=[self.common[k] for k in selected if k in self.common];eid=self._create(key,plan,parents)
            try:
                need(len(parents)==len(selected),'all original selected corpus parents exist; no substituted missing parent')
                corpus_inputs={}
                if parents:
                    need(len(parents)==1,'this concrete original downstream recipe consumes one selected checkpoint parent, not an undeclared mixture');p=parents[0];corpus_inputs['reference_parent']={'host':p['host_root'],'guest':'/state/reference_parent','identity':p['state_identity']}
                for repetition in (0,1,2):
                    views=self._views(eid,plan,repetition,('train','validation'));selected_state=self.learning.develop(eid,repetition,views,corpus_inputs)
                    if selected_state is not None:
                        call=next(r for r in self.session.calls if r['call_id']==selected_state['original_fit_call']);self._collect_result(eid,call)
                # Every actual preparation/A09 result remains mandatory too.
                for output in self.learning.episodes[eid]['outputs']:
                    if output['response']['products']:self._collect_result(eid,output)
                self.learning.seal(eid)
            except BaseException as exc:self._failed_episode(eid,exc)
            self._global()
    def _select(self):
        self.stage='all_same_fold_reference_selections'
        for key,group in self.schedule.selection_groups.items():
            try:
                records={method:self.learning.episodes[self.episode_ids[planned]]['feedback'] for method,planned in group['methods'].items()};receipt=self.issuer.select_reference(group['dataset'],'f'+str(group['fold']),'I',group['access'],self.config['genesis']['scientific_policy'],records,list(CONTROLS));self.selectors[key]={'status':'selected','receipt':receipt}
            except BaseException as exc:self.selectors[key]={'status':'unavailable','original_failure':observation(exc)};self.failure_records.append({'phase':self.stage,'selector':key,**observation(exc)})
    def _queries(self):
        self.stage='all_complete_frozen_original_queries_and_diagnostics'
        for key,plan in self.schedule.episodes.items():
            if plan['spec']['dataset']=='CORPUS':continue
            eid=self.episode_ids[key];self._episode(eid);row=self.learning.episodes[eid]
            try:
                need(row['development_close'] is not None,'actual development must be immutable before any query')
                for repetition in (0,1,2):
                    if repetition not in row['selected']:continue
                    prepared=self._views(eid,plan,repetition,('query',))['query'];parents=[row['development_close'],row['selected'][repetition]['state'],prepared['receipt']];products=[]
                    for expected in plan['classification']:
                        if expected['scope']['repetition']!=repetition:continue
                        p=copy.deepcopy(expected);p['parents']=[r['record_sha256'] for r in parents];products.append(p)
                    before=len(row['outputs']);self.learning.query(eid,repetition,prepared,products)
                    for product in products:self.queries[product['product_id']]=row['query'][repetition]['preparation']
                    for result in row['outputs'][before:]:self._collect_result(eid,result)
                self.issuer.close_episode(eid,[r['product_id'] for r in plan['classification']+plan['diagnostics']],reason=None if not row['failures'] else 'original incomplete episode; all statuses preserved')
            except BaseException as exc:
                self._failed_episode(eid,exc)
                if not self.issuer.episodes[eid]['active_processes'] and self.issuer.episodes[eid]['status']!='closed':self.issuer.close_episode(eid,[],reason='original query/diagnostic failure')
            self._global()
    def _close_collection(self):
        self.stage='complete_original_collection_and_global_barrier'
        for eid,row in self.learning.episodes.items():
            for pid,receipt in row['analysis_specifications'].items():
                if pid in self.collection.members:continue
                try:self.collection.seal_analysis(pid,receipt,self.collection.expected[pid]['support']['primitive_product_ids'])
                except BaseException as exc:self.failure_records.append({'phase':'original_analysis_seal','product_id':pid,**observation(exc)})
        for pid,expected in self.collection.expected.items():
            if pid not in self.collection.members:
                eid=self.episode_ids[identity({k:expected['scope'][k] for k in ('mode','access','policy_id','actor_role','dataset','outer_fold','method')})];row=self.issuer.episodes[eid];receipts=[row['close']] if 'close' in row else [self.learning.episodes[eid]['context']];self.collection.unavailable(pid,'original mandatory product not produced; complete scope retained',receipts)
        closed=self.collection.seal();selectors=[r['receipt'] for r in self.selectors.values() if r['status']=='selected'];closure=self.issuer.close_global(list(self.learning.episodes),{'collection_identity':identity(closed),'full_expected_identity':closed['expected_identity'],'counts':closed['counts'],'selector_failures':{k:v for k,v in self.selectors.items() if v['status']!='selected'}},selectors);return closed,closure
    def _score(self,closed,closure):
        self.stage='protected_full_scientific_reduction';self.operator.guard('before_protected_grader_constructor');grader=ProtectedGrader(self.issuer,self.projection,self.session,self.collection,self.schedule,self.queries,self.operator,self.paths['private-scoring'],self.config['scientific_adjudication'],{'common':self.common,'resource_bindings':self.resource_bindings,'resource_receipts':self.resource_receipts});self.operator.guard('after_protected_grader_constructor');grader.admit(closure);case=grader.full_classification();historical=grader.historical_comparisons();improvement={}
        for access in ('A','B'):improvement[access]=grader.improvement(access,self.selectors,seed=self.config['genesis']['seed_policy']['inference_seed'])
        from .scientific_grading import grade_full_diagnostics
        access_effects=grader.access_effects(seed=self.config['genesis']['seed_policy']['inference_seed']);diagnostic=boundary(self.operator,'complete_diagnostic_reduction',grade_full_diagnostics,grader,self.config['scientific_adjudication']);all_grades={**case,**diagnostic}
        from .contrasts import reduce_all
        contrasts=boundary(self.operator,'complete_contrast_reduction',reduce_all,grader,seed=self.config['genesis']['seed_policy']['inference_seed'])
        report={'schema':'eegpt_complete_scientific_report_v1','scope':self.schedule.summary(),'genesis':self.issuer.genesis,'global_closure':closure,'original_closed_collection':closed,'all_case_grades':case,'all_diagnostic_grades':diagnostic,'historical_reconstruction':historical,'complete_reproduction_dataset_reductions':grader.reproduction_dataset_reductions(),'complete_within_family_contrasts':contrasts,'improvement':improvement,'matched_B_minus_A_access_effects':access_effects,'all_same_fold_selection_records':self.selectors,'all_original_failure_records':self.failure_records+grader.failures,'all_original_episode_closures':{eid:row.get('close') for eid,row in self.issuer.episodes.items()},'scientific_qualification':self.config['qualification'],'numerical_scoring_closed':True,'scientifically_complete':False,'reasoning_adjudication':'pending independent blinded interpretation reviewers; not an automated correctness claim'}
        score=self.issuer.close_scores(closure,identity(report));report['score_closure']=score
        from .reporting import release_and_interpret
        interpretations=boundary(self.operator,'full_report_interpretation',release_and_interpret,self,report,score);report['interpretations']=interpretations
        # G24 reviewer calibration is not the actual24x4 judgment of this new
        # output. Pending original blind reviews do not become complete scores.
        report['scientifically_complete']=scientific_completion(closed,all_grades,self.config['qualification']['gates'],{'A':[v for k,v in self.selectors.items() if k.startswith('A:')],'B':[v for k,v in self.selectors.items() if k.startswith('B:')]},interpretations['adjudicated_claims'],contrasts)
        return report
    def _ledger_lines(self):
        if self.budget is None:
            yield encode({'kind':'budget_uninitialized','known_costs':None});return
        budgets=[('campaign',self.budget),('operator',self.operator.episode)]+[(eid,b) for eid,b in self.episode_budgets.items()]
        for name,budget in budgets:
            report=budget.report();summary={k:v for k,v in report.items() if k not in ('jobs','failures','unknown')}
            yield encode({'kind':'budget_summary','scope':name,'summary':summary})
            for kind in ('jobs','failures','unknown'):
                for ordinal,row in enumerate(report[kind]):yield encode({'kind':kind,'scope':name,'ordinal':ordinal,'original':row})
    def _close_handle(self,role,handle):
        if handle is None:return
        owner=self.custody;row={'role':role,'status':'attempted'};owner.record['handle_closes'].append(row)
        try:handle.close();row['status']='closed'
        except BaseException as exc:
            row['status']='failed_or_unknown';owner.fail('close:'+role,exc);row['failure']=owner.record['secondary_failures'][-1] if owner.record['secondary_failures'] else owner.record['original_failure']
        if role=='work':self.outside_closure['work_handle_close']={'status':'closed'} if row['status']=='closed' else dict(row)
    def _reserved_publication(self,kind,name,chunks):
        if not hasattr(self,'work') or self.terminal_pool is None:return
        owner=self.custody;attempt={'kind':kind,'path':name,'status':'attempted','charge_attempted':False};owner.record['publication_attempts'].append(attempt);amount=None
        try:
            member=persist_chunks(self.work,name,chunks,cap=self.terminal_pool[kind+'_bytes']);attempt.update(status='published',member=member);amount=member['bytes']
            if kind=='terminal':self.terminal_member=member;self.outside_closure['original_terminal']=member
            else:self.terminal['publications'][kind]=member
        except BaseException as exc:
            owner.fail('publication:'+kind,exc);attempt.update(status='failed_or_partial',failure=owner.record['secondary_failures'][-1] if owner.record['secondary_failures'] else owner.record['original_failure'])
            observed=getattr(exc,'observation',None);prefix=observed.get('known_written_prefix') if type(observed) is dict else None
            if type(prefix) is dict:amount=prefix.get('bytes');attempt['known_written_prefix']=prefix
            if kind!='terminal':self.terminal['publications'][kind]={'failed_original_publication':attempt['failure']}
        finally:
            # One charge attempt, including known partial output or unknown.
            # Failed or partially applied coupled accounting is never retried.
            attempt['charge_attempted']=True;attempt['known_bytes']=amount
            owner.attempt('account_publication:'+kind,lambda:self.operator.observe('output_bytes',amount))
    def _publish_report(self,result):
        if result is not None and hasattr(self,'work'):
            self.report_member=persist(self.work,'SCIENTIFIC_REPORT.json',encode(result),ledger=self.operator);self.terminal['publications']['scientific_report']=self.report_member
    def _terminal_facts(self,result):
        owner=self.custody;t=self.terminal
        t.update(stage=self.stage,source_scope_identity=None if self.scope is None else self.scope.identity,targets_open=False if self.issuer is None else self.issuer.targets_open,work_handle_final_close_pending=hasattr(self,'work'))
        t['scientifically_complete']=result is not None and result['scientifically_complete'] and owner.original_exception is None
    def _publish_terminal(self):
        owner=self.custody;t=self.terminal
        # This snapshot stops changing once serialized. Late failures are kept
        # in the already-held owner/outside records, not rewritten into bytes.
        t['original_failure']=owner.record['original_failure'];t['original_secondary_failures']=list(owner.record['secondary_failures']);t['original_close_failures']=[dict(r) for r in owner.record['handle_closes'] if r['status']!='closed'];t['publications']=dict(t['publications'])
        t['scientifically_complete']=t['scientifically_complete'] and owner.original_exception is None
        if hasattr(self,'work') and self.terminal_pool is not None:
            raw=encode(t);need(len(raw)<=self.terminal_pool['terminal_bytes'],'complete compact terminal within original reserve')
            self._reserved_publication('terminal','ORIGINAL_TERMINAL.json',(raw,))
    def _final_budget_check(self):
        if self.budget is not None:
            self.budget.guard('after_original_terminal_publication_and_work_close')
            budgets=[self.budget]+([] if self.operator is None else [self.operator.episode])+list(self.episode_budgets.values())
            for budget in budgets:
                for dimension in COUNTERS:need(budget.known[dimension]<=budget.reserved[dimension]<=budget.limits[dimension],'original final inner resource allowance '+dimension)
    def _outside_facts(self):
        b=self.budget;outside=self.outside_closure
        outside.update(original_deadline_ns=None if b is None else b.deadline,final_known_counters=None if b is None else dict(b.known),final_reserved_counters=None if b is None else dict(b.reserved),costs_complete=b is not None and not b.unknown and not self.custody.record['accounting_observation_failure'],late_failure=self.custody.record['original_failure'])
    def operate(self):
        owner=self.custody;result=None
        try:
            self._setup();self.budget.guard('after_complete_setup');self._corpus();self._development();self._select();self._queries();closed,closure=self._close_collection();result=self._score(closed,closure);self.budget.guard('after_complete_scoring');self.stage='full_operation_returned'
        except BaseException as exc:owner.fail(self.stage,exc)
        finally:
            # Every action has its own guard. One identity/clock/report/ledger
            # fault cannot bypass later publication, closing or accounting.
            owner.attempt('capture_original_ledger_before_close',owner.ledger)
            handles=[('session',self.session),('executor',self.executor),*[(str(k),h) for k,h in self.data_roots.items()],('development_labels',getattr(self,'development_labels',None)),('binary_root',getattr(self,'binary_root',None)),('journal',getattr(self,'journal_handle',None) if self.issuer is None else self.issuer.journal)]
            for role,handle in handles:owner.attempt('close:'+role,lambda role=role,handle=handle:self._close_handle(role,handle))
            owner.attempt('complete_report_publication',lambda:self._publish_report(result))
            if result is not None:owner.attempt('terminal_result_identity',lambda:self.terminal.__setitem__('result_identity',identity(result)))
            owner.attempt('terminal_original_facts',lambda:self._terminal_facts(result))
            owner.attempt('publish_original_failures',lambda:self._reserved_publication('failures','ORIGINAL_FAILURES.jsonl',(encode(row) for row in self.failure_records)))
            owner.attempt('publish_original_ledger',lambda:self._reserved_publication('ledger','ORIGINAL_RESOURCE_LEDGER.jsonl',self._ledger_lines()))
            owner.attempt('publish_original_terminal',self._publish_terminal)
            owner.attempt('close:work',lambda:self._close_handle('work',getattr(self,'work',None)))
            owner.attempt('final_original_budget_admission',self._final_budget_check)
            owner.attempt('outside_original_terminal_identity',lambda:self.outside_closure.__setitem__('original_terminal_identity',identity(self.terminal)))
            owner.attempt('outside_final_clock',lambda:self.outside_closure.__setitem__('final_observed_ns',__import__('time').monotonic_ns()))
            owner.attempt('outside_original_facts',self._outside_facts)
            owner.attempt('capture_final_original_ledger',owner.ledger)
        if owner.original_exception is not None:raise owner.refusal() from owner.original_exception
        return {'report':self.report_member,'terminal':self.terminal_member,'outside_final_closure':self.outside_closure,'scientifically_complete':self.terminal['scientifically_complete']}



for _name in ('_create','_views','_collect_result','_corpus','_collect_closed_corpus','_development','_select','_queries','_close_collection','_score'):
    setattr(Programme,_name,budget_method(getattr(Programme,_name)))
