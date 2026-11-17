"""Complete arbitrary-participant programme, with a genuine pre-R I barrier."""
from __future__ import annotations
from .common import require,identity,error_record,Refusal
from .ancestry import Ancestry,capsule,validate_resume
from .participant import public_case
from .truth import prediction_view
from .collection import Collector,Records,TargetAccess
from .grading import Grade
from .tables import actor_table
from .planner import paired_input_target_identity
from .objects import put_object,get_object,object_descriptors

class Campaign:
    def __init__(self,plan,data,participant,science,references,preparation,store,journal,meter,authority):
        self.plan,self.data,self.actor,self.science=plan,data,participant,science
        self.references,self.preparation,self.store=references,preparation,store
        self.journal,self.meter,self.authority=journal,meter,authority
        self.ancestry=Ancestry(data['folds'],data['raw_registry'])
        self.operator_receipts={};self.phase=None;self.states={};self.all_configs={}
        self.participant_records={};self.uncertainty_records={};self.reference_records={};self.aggregates={}
        self.capsule=None;self.global_seal=None;self.report=None;self.resource_report=None
        self.exposure={'original':plan.value['original_exposure_history'],'held_R_disclosures':[]}
        self.method_manifest=None;self.build_I=None;self.build_R=None;self.R_source=None
        self.closed=False;self.legacy_validation=None

    def checkpoint(self,effect):
        self.meter.checkpoint(effect)
        self.authority.admit(plan=self.plan.hash,source_manifest=self.plan.value['source_manifest_sha256'],
            route=self.plan.route,input_registry=self.plan.value['input_registry_sha256'],effect=effect)

    def phase_start(self,name):
        self.checkpoint('phase_'+name+'_admission')
        receipt=self.journal.append('PHASE_START',{'phase':name,'previous_phase':self.phase})
        self.checkpoint('after_phase_START_'+name)
        self.phase=name;return receipt

    def op(self,operator,receipts,*,mode='executed'):
        self.checkpoint('operator_completion_'+operator)
        require(operator in self.plan.contracts.operators,'UNKNOWN_OPERATOR')
        require(receipts or mode=='mode_not_requested','OPERATOR_REQUIRES_ORIGINAL_EVIDENCE',operator)
        evidence=put_object(self.store,f'operators/{operator}-{len(self.operator_receipts.get(operator,[])):08d}',
                            receipts,producer=self.plan.hash)
        record=self.journal.append('OPERATOR_DISPOSITION',{'operator':operator,'phase':self.phase,
            'mode':mode,'original_evidence':evidence})
        self.operator_receipts.setdefault(operator,[]).append(record)
        return record

    def artifacts(self,ids,role=None):
        out=[]
        for key in ids:
            self.checkpoint('next_stage_artifact')
            require(key in self.preparation.registry,'UNPREPARED_STAGE_INPUT',key)
            desc=self.preparation.registry[key]
            require(desc['role'] not in {'protected_truth','reference_product','reference_state'},
                    'HIDDEN_PRODUCT_AS_PARTICIPANT_INPUT')
            if role in {'training_truth','calibration_truth'}:
                stage='development' if role=='training_truth' else 'calibration'
                out.append(self.preparation.truth.label(key,stage))
            elif role in {'training_input','calibration_input','R_input','I_input'}:
                out.append(prediction_view(desc,role))
            else:out.append(desc)
        return out

    def case_arrays(self,case):
        self.checkpoint('case_input_resolution')
        return self.preparation.case_arrays(case)

    def _stage_products(self,record,roles):
        return [x for x in record['response']['artifacts'] if x['role'] in roles]

    def _state(self,record,fold,configuration,actual_parents):
        result=record['response']['payload']
        if result['status']=='failed':
            return {'configuration':configuration,'fit_status':'failed','state_id':None,
                    'record':record,'artifacts':[]}
        state=result['state']
        state_id=self.ancestry.add_state(state,actual_visible_parents=actual_parents,
                                        fold_id=fold,lane='I')
        artifacts=self._stage_products(record,{'fit_state'})
        require(artifacts or result['status']=='no_fit','FITTED_STATE_ARTIFACT_REQUIRED')
        require(state.get('artifact_sha256s',[])==[x['sha256'] for x in artifacts],
                'STATE_ARTIFACT_SUBSTITUTION')
        return {'configuration':configuration,'fit_status':'ok','state_id':state_id,'state':state,
                'record':record,'artifacts':artifacts}

    def _estimate(self,case,state,*,lane,source=None,calibration=False):
        self.checkpoint('before_actual_participant_prediction')
        arrays=self.case_arrays(case)
        role='calibration_input' if calibration else ('R_input' if lane=='R' else 'I_input')
        inputs=[prediction_view(x,role) for x in arrays.values()]
        if lane=='I':
            self.ancestry.apply(state['state']['id'],fold_id=case['fold_id'],
                input_coordinates=case['coordinates'],case_id=case['case_id'],lane='I')
        build=self.build_R if lane=='R' else self.build_I
        artifacts=[*inputs,*state['artifacts'],*self._stage_products(build,{'build_artifact'})]
        record=self.actor.invoke('estimate',{'case':public_case(case),'state_sha256':state['state_id'],
             'state':state.get('state',{}),'calibration_prediction':calibration},lane=lane,
             protocol_id=case['protocol_id'],artifacts=artifacts,
             state_seals={x['path']:x['sha256'] for x in state['artifacts']},source=source)
        return record

    def prepare_and_learn(self):
        self.phase_start('P00')
        self.plan.validate_case_rows(self.data['R_cases'],'R')
        if not self.plan.r_only:
            self.plan.validate_case_rows(self.data['I_cases'],'I')
            self.plan.validate_evaluation_worlds([x for x in self.data['I_cases'] if x['kind']=='known_truth'])
        self.op('O01',[{'authority':self.authority.hash,'source':self.plan.value['source_authority_sha256']}])
        self.op('O02',[{'roster':identity(self.plan.value['group_roster']),'folds':identity(self.data['folds'])}])
        self.op('O31',[{'original_exposure':self.exposure,'receipt_head':self.journal.head}])
        if self.plan.resume:
            saved=self.data['resume_capsule'];r=self.data['resume_R_receipts']
            validate_resume(saved,self.data['resume_request'],r)
            require(saved['resources']['deadline']==self.meter.deadline,'RESET_ORIGINAL_RESUME_DEADLINE')
            current=self.meter.snapshot()
            for section in ('reserved','observed'):
                require(all(current[section][k]>=v for k,v in saved['resources'][section].items()),
                        'RESET_RESUME_RESOURCE_HISTORY',section)
            require(r['original_resource_snapshot_sha256']==identity(self.bootstrap['prior']),
                    'RESUME_OMITS_OR_REPLACES_INTERVENING_R_COSTS')
            self.capsule=saved;self.states=self.data['resume_states']
            require(set(self.states)==set(saved['states']),'RESUME_FOLD_STATE_CENSUS_CHANGED')
            for fold,state in self.states.items():
                require(state['state_id']==saved['states'][fold]['state_id'] and
                        state['artifacts']==saved['states'][fold]['artifacts'] and
                        state['uncertainty_selection']==saved['states'][fold]['uncertainty_selection'],
                        'RESUME_STATE_OR_SELECTION_CHANGED')
            refs=self.references;refs.sealed=self.data['resume_reference_capsule']
            require(refs.sealed==saved['selectors'],'RESUME_REFERENCE_CAPSULE_CHANGED')
            refs.states=refs.sealed['states'];refs.residual_states=refs.sealed['residual_states']
            refs.prior_states={tuple(x['binding']):x['value'] for x in refs.sealed['prior_states']}
            refs.bind_provider_plan(self.data['provider_plan'])
            require(refs.provider_plan_hash==refs.sealed['provider_plan_sha256'],'RESUME_PROVIDER_PLAN_CHANGED')
            refs.selections=self.data['resume_reference_selections']
            for key,categories in refs.selections.items():
                for category,record in categories.items():
                    require(record['product_sha256']==identity(record['response'])==
                            refs.sealed['selections'][key][category],'RESUME_SELECTOR_PRODUCT_CHANGED')
            self.reference_records=self.data['resume_reference_records']
            self.participant_records=self.data['resume_participant_R_records']
            self.operator_receipts=self.data['resume_operator_receipts']
            self.build_I=self.data['resume_build_I'];self.R_source=self.data['resume_R_source']
            self.build_R=self.data['resume_build_R'];self.ancestry.nodes=self.data['resume_ancestry_nodes']
            self.preparation.registry=dict(self.data['resume_prepared_registry'])
            original_products=self.data['resume_preparation_products']
            require(identity(original_products)==saved['prepared_truth_products_sha256'],
                    'RESUME_GENERATOR_TRUTH_ANCESTRY_SUBSTITUTION')
            jobs={x['id']:x for x in self.data['preparation_P02']+self.data['preparation_P06']}
            for job_id,record in original_products.items():
                require(job_id in jobs,'RESUME_UNKNOWN_PREPARATION_JOB')
                self.preparation.products[job_id]=record
                self.preparation.truth.register(jobs[job_id],record)
            self.exposure=self.data['resume_exposure_history']
            require(self.exposure['held_R_disclosures'],'RESUME_LOST_ORIGINAL_R_EXPOSURE')
            for case in self.data['R_cases']:
                record=self.participant_records[case['case_id']]
                require(record['product_sha256']==identity(record['response']) and
                        record['request']['source_manifest_sha256']==self.R_source['source_manifest_sha256'],
                        'RESUME_R_PRODUCT_SOURCE_SUBSTITUTION')
            return
        if self.plan.r_only:
            self.phase_start('R_SOURCE_ONLY')
            self.op('O15',[],mode='mode_not_requested');self.op('O16',[],mode='mode_not_requested')
            self.capsule={'capsule_kind':'R_SOURCE_ONLY','participant':self.actor.participant_id,
                          'arm':self.plan.arm,'plan_sha256':self.plan.hash,'no_clean_I_reuse':True}
            self.op('O17',[{'R_source_only_seal':identity(self.capsule)}])
            return
        self.phase_start('P01')
        views=[*self.data['common_views'],*(self.data['author_views'] if self.plan.arm=='B' else [])]
        described=self.actor.invoke('describe',{'submission_spec':self.data['submission_spec']},
                        lane='I',protocol_id='whole_programme',artifacts=views)
        self.method_manifest=described['response']['payload']
        self.build_I=self.actor.invoke('build',{'manifest':self.method_manifest,'lane':'I'},
                        lane='I',protocol_id='whole_programme',artifacts=self.data['build_dependencies'])
        require(self.build_I['response']['payload']['status'] in {'ok','no_fit'},'I_BUILD_FAILED')
        self.op('O14',[described['process_receipt'],self.build_I['process_receipt']])
        self.phase_start('P02')
        self.preparation.run(self.data['preparation_P02'],phase='P02',all_I_sealed=False)
        for op in ['O03','O04','O05','O06','O07','O08']:
            records=[r['process_receipt'] for key,r in self.preparation.products.items()
                     if next(x for x in self.data['preparation_P02'] if x['id']==key)['operator']==op]
            self.op(op,records)
        self.op('O09',[{'stage_scoped_case_handles':identity(self.data['case_manifest_identity'])}])
        self.phase_start('P03')
        configurations=self.method_manifest['configurations']
        for fold_id,fold in self.data['folds'].items():
            self.checkpoint('next_training_fold')
            states={};parents=self.data['training_parent_ids'][fold_id]
            for config in configurations:
                self.checkpoint('next_original_configuration')
                record=self.actor.invoke('learn',{'fold_id':fold_id,'configuration':config,
                       'allowed_parent_ids':parents,'allowed_training_groups':fold['training'],
                       'search_budget':self.data['search_budget'],'transform_contract':self.data['transform_contract']},
                    lane='I',protocol_id='whole_programme',artifacts=[
                       *self.artifacts(self.data['training_view_ids'][fold_id],'training_input'),
                       *self.artifacts(self.data['training_truth_ids'][fold_id],'training_truth'),
                       *self._stage_products(self.build_I,{'build_artifact'})])
                require({x['configuration_id'] for x in record['response']['payload']['attempts']}=={config['id']},
                        'UNREPORTED_OR_EXTRA_CONFIGURATION_ATTEMPTS')
                states[config['id']]=self._state(record,fold_id,config['id'],parents)
                self.op('O15',[record['process_receipt']])
            self.all_configs[fold_id]=states
        self.references.bind_provider_plan(self.data['provider_plan'])
        self.references.fit(self.data['reference_development'])
        self.phase_start('P04')
        for fold_id,states in self.all_configs.items():
            self._calibrate_fold(fold_id,states)
        self.references.calibrate(self.data['reference_calibration'],self.data['provider_plan'])
        self.phase_start('P05')
        reference_seal=self.references.seal()
        self.capsule=capsule(self.actor.run_id,self.actor.participant_id,self.plan.arm,self.plan.hash,
            self.actor.source['source_manifest_sha256'],self.data['folds'],
            {k:{'state_id':v['state_id'],'artifacts':v['artifacts'],'selection_receipt':v['selection_receipt'],
                'uncertainty_selection':v['uncertainty_selection'],
                'uncertainty_artifacts':v['uncertainty_state']['artifacts'] if v['uncertainty_state'] else []}
               for k,v in self.states.items()},
            reference_seal,identity(self.data['I_cases']),self.exposure,self.journal.head,self.meter.snapshot())
        self.capsule['prepared_truth_products_sha256']=identity(self.preparation.products)
        capsule_file=put_object(self.store,'state/PRE_R_CAPSULE',self.capsule,
                                role='pre_R_capsule',producer=self.journal.head)
        self.op('O17',[{'capsule':capsule_file,'all_fold_states_sealed':True}])

    def _calibrate_fold(self,fold_id,states):
        cases=self.data['participant_calibration'][fold_id];configuration_records={}
        ledger=Records(self.store,f'calibration/{fold_id}','calibration_ledger',self.plan.hash)
        expected=[]
        for case in cases:
            expected.append(self.preparation.truth.expected(
                self.data['public_calibration_expected'][case['case_id']],case,'calibration'))
        expected_by_id={x['case_id']:x for x in expected}
        for config,state in states.items():
            self.checkpoint('next_calibration_configuration')
            outputs=[];cpu=state['record']['process_completion']['telemetry']['cpu_seconds']
            for case in cases:
                self.checkpoint('next_public_calibration_case')
                if state['fit_status']!='ok':
                    payload={'status':'no_call','value':None,'intervals':{}}
                else:
                    result=self._estimate(case,state,lane='I',calibration=True)
                    payload=result['response']['payload'];cpu+=result['process_completion']['telemetry']['cpu_seconds']
                row={**{k:expected_by_id[case['case_id']][k]
                         for k in ['case_id','world_id','family','cell','view','input_identity','target_identity']},
                     'configuration_id':config,'source_sha256':self.actor.source['source_manifest_sha256'],
                     'state_id':state['state_id'],'status':payload['status'],'gamma':payload['value'],
                     'sets':payload['intervals']}
                outputs.append(row);ledger.append(row)
            configuration_records[config]={'source_sha256':self.actor.source['source_manifest_sha256'],
                'original_fit_receipt_id':state['record']['process_receipt']['sha256'],
                'fit_status':state['fit_status'],'fitted_state_id':state['state_id'],
                'original_total_cpu_seconds':cpu,'records':outputs}
        ledger_seal=ledger.seal()
        # Exact shards are participant-owned calibration predictions, never reference outputs.
        ledger_artifacts=[]
        def gather(desc):
            ledger_artifacts.append({**desc,'role':'calibration_ledger'})
            index=self.store.json(desc,{'sealed_record_index'})
            for part in index['members']:
                if index['depth']:gather(part)
                else:ledger_artifacts.append(part)
        gather(ledger_seal['root'])
        selected=self.actor.invoke('calibrate',{'fold_id':fold_id,'candidate_states':[
                {'configuration':k,'state_id':v['state_id'],'fit_status':v['fit_status']} for k,v in states.items()],
                'calibration_predictions':ledger_seal,'selection_rule':'primary_risk_then_actual_CPU_then_configuration_ID',
                'all_expected_case_ids':[x['case_id'] for x in cases]},lane='I',protocol_id='whole_programme',
            artifacts=[*ledger_artifacts,*self.artifacts(self.data['calibration_truth_ids'][fold_id],'calibration_truth'),
                       *[x for v in states.values() for x in v['artifacts']]])
        value=selected['response']['payload'];choice=value['selected_configuration']
        require(choice in states and states[choice]['fit_status']=='ok','SELECTED_UNFITTED_CONFIGURATION')
        require(value['selected_state_sha256']==states[choice]['state_id'],'NEW_STATE_CREATED_DURING_CALIBRATION')
        uncertainty=value['uncertainty_selection']
        declared={'point_configuration_id':choice,'point_state_id':states[choice]['state_id'],
                  'uncertainty_configuration_id':uncertainty['configuration_id'],
                  'uncertainty_state_id':uncertainty['state_id']}
        validation=self.science.invoke('score.select_participant',arrays={},protocol={
            'selection_stage':'public_calibration','fit_state_registry_admitted':True,
            'original_costs_admitted':True},parameters={'scope':'complete_primary_calibration',
            'expected_cases':expected,'declared_configuration_ids':list(states),
            'configurations':configuration_records,'participant_selection':declared},
            lineage={'fold_id':fold_id,'I_source':self.actor.source['source_manifest_sha256'],
                     'actual_selected_response':selected['product_sha256']},namespace='trusted_collection')
        require(validation['response']['result']['status']=='ok','PARTICIPANT_CALIBRATION_RULE_VIOLATED')
        ci_choice=uncertainty['configuration_id']
        ci_state=None
        if ci_choice is not None:
            require(ci_choice in states and states[ci_choice]['fit_status']=='ok' and
                    uncertainty['state_id']==states[ci_choice]['state_id'],
                    'UNFITTED_OR_SUBSTITUTED_UNCERTAINTY_STATE')
            ci_state=states[ci_choice]
        self.states[fold_id]={**states[choice],'selection_receipt':validation['process_receipt'],
                             'uncertainty_selection':uncertainty,'uncertainty_state':ci_state}
        self.op('O16',[selected['process_receipt'],validation['process_receipt']])

    def reproduce_and_infer(self):
        require(self.capsule is not None,'R_OR_I_WITHOUT_ORIGINAL_CAPSULE')
        if not self.plan.resume:
            self.phase_start('P06')
            disclosure=self.journal.append('FIRST_HELD_R_DISCLOSURE',{'capsule_sha256':identity(self.capsule),
                'capsule_kind':self.capsule['capsule_kind'],'data_support':self.data['R_support_sha256']})
            self.checkpoint('after_R_disclosure_intent_before_R_data')
            self.exposure['held_R_disclosures'].append(disclosure)
            self.preparation.run(self.data['preparation_P06'],phase='P06',all_I_sealed=True)
            for operator in ['O03','O04','O05','O06','O07','O08']:
                evidence=[self.preparation.products[j['id']]['process_receipt']
                          for j in self.data['preparation_P06'] if j['operator']==operator]
                if evidence:self.op(operator,evidence)
                elif self.plan.r_only:
                    # R-only preparation must still include every biological/LLM producer.
                    require(False,'MISSING_R_ONLY_PREPARATION_BRANCH',operator)
            R_views=self.artifacts(self.data['R_authoring_input_ids'],'R_input')
            authored=self.actor.invoke('author_R',{'complete_obligations':sorted(self.plan.contracts.obligations),
                'source_can_evolve':True,'no_write_or_feedback_to_I':True,
                'complete_R_case_plan':self.data['R_case_plan_public']},lane='R',protocol_id='whole_R',
                artifacts=[*self.data['common_views'],
                  *(self.data['author_views'] if self.plan.arm=='B' else []),*R_views])
            self.R_source=self.actor.derive_R_source(authored)
            R_fits=self._stage_products(authored,{'R_fit_state'})
            self.build_R=self.actor.invoke('build',{'lane':'R','authored_source_sha256':self.R_source['source_manifest_sha256']},
                lane='R',protocol_id='whole_R',source=self.R_source,
                artifacts=[*R_fits,*self.data['build_dependencies']])
            require(self.build_R['response']['payload']['status'] in {'ok','no_fit'},'R_BUILD_FAILED')
            self.op('O14',[authored['process_receipt'],self.build_R['process_receipt']])
            R_state={'state':self.build_R['response']['payload']['state'],
                'state_id':identity(self.build_R['response']['payload']['state']),
                'artifacts':R_fits+self._stage_products(self.build_R,{'build_artifact'})}
            for case in self.data['R_cases']:
                self.checkpoint('next_original_R_case')
                self.participant_records[case['case_id']]=self._estimate(case,R_state,lane='R',source=self.R_source)
            self.op('O18',[x['process_receipt'] for k,x in self.participant_records.items()
                           if any(c['case_id']==k for c in self.data['R_cases'])])
            self.op('O09',[{'actual_R_input_selections':identity(self.data['R_cases'])}])
            self._R_references()
        if self.plan.r_only:
            self.op('O19',[],mode='mode_not_requested')
            return
        self.phase_start('P07')
        for case in self.data['I_cases']:
            self.checkpoint('next_original_I_case')
            state=self.states[case['fold_id']]
            record=self._estimate(case,state,lane='I')
            self.participant_records[case['case_id']]=record
            ci_state=state['uncertainty_state']
            if ci_state is not None:
                self.uncertainty_records[case['case_id']]=(record if ci_state['state_id']==state['state_id']
                    else self._estimate(case,ci_state,lane='I'))
        self.op('O19',[x['process_receipt'] for x in
            [*[self.participant_records[c['case_id']] for c in self.data['I_cases']],
             *self.uncertainty_records.values()]])
        self.references.evaluate(self.data['reference_evaluation'],self.data['provider_plan'])
        self.op('O09',[{'actual_I_input_selections':identity(self.data['I_cases'])}])

    def _R_references(self):
        covered=set()
        for job in self.data['R_reference_jobs']:
            self.checkpoint('next_original_R_reference_job')
            case=next(x for x in self.data['R_cases'] if x['case_id']==job['case_id'])
            require(job['input_sha256']==case['input_sha256'] and
                    job['original_support_sha256']==case['original_support_sha256'],
                    'R_REFERENCE_DIFFERENT_INPUT_OR_SUPPORT')
            record=self.science.invoke(job['operation'],arrays=self.case_arrays(case),protocol=job['protocol'],
                parameters=job['parameters'],lineage={'operator':job['operator'],'case_id':case['case_id'],
                    'input_identity':case['input_sha256'],'selection_sha256':case['selection_sha256'],
                    'original_support_sha256':case['original_support_sha256'],
                    'reference_source_sha256':self.science.source['source_manifest_sha256']},
                namespace='independent_reference')
            require(job['id'] not in self.reference_records,'DUPLICATE_R_REFERENCE_JOB')
            self.reference_records[job['id']]=record;covered.add(job['operator'])
            self.op(job['operator'],[record['process_receipt']])
        require({'O10','O11','O12','O13','O20','O21','O22','O32'}<=covered,
                'INCOMPLETE_LITERAL_CORRECTED_FINITE_NOISE_LOCAL_REFERENCE_GRAPH')
        if not self.plan.r_only:
            diagnostics=self.references.diagnostic_bank(self.data['diagnostic_jobs'])
            self.reference_records['diagnostics']={'records':diagnostics}

    def aggregate_and_report(self):
        self.phase_start('P08')
        for job in self.data['aggregate_jobs']:
            self.checkpoint('next_homogeneous_aggregate')
            require(job['issuer'] in {'participant','reference'},'AGGREGATE_ISSUER_UNSPECIFIED')
            source=self.participant_records if job['issuer']=='participant' else self.reference_records
            records=[]
            for binding in job['members']:
                require(binding['record_id'] in source,'MISSING_ORIGINAL_DRAW_PRODUCT')
                record=source[binding['record_id']]
                value=(record['response']['payload'] if job['issuer']=='participant'
                       else record['response']['result']['outputs'])
                fields={}
                for target,path in binding['fields'].items():
                    item=value
                    for part in path:item=item[part]
                    fields[target]=item
                records.append({'id':binding['id'],**fields})
            result=self.science.invoke(job['operation'],arrays={},protocol=job['protocol'],parameters={
                **job['parameters'],'records':records},lineage={'aggregate_id':job['id'],
                'issuer':job['issuer'],'original_receipts':put_object(self.store,
                    'aggregate-parents/'+job['id'],[source[b['record_id']]['process_receipt']
                    for b in job['members']],producer=self.plan.hash)},namespace='trusted_collection')
            self.aggregates[job['id']]=result
            self.op(job['operator'],[result['process_receipt']])
        require({'O23','O24'}<=set(self.operator_receipts),'MISSING_ACTUAL_AGGREGATION_OR_UNCERTAINTY_STAGE')
        # A separate participant-only transport is built; no reference row is relabeled own.
        own=Records(self.store,'report/own-products','sealed_own_product',self.plan.hash)
        own_objects=[]
        for category,bank in [('point_or_R',self.participant_records),('uncertainty',self.uncertainty_records)]:
            for case_id,record in bank.items():
                obj=put_object(self.store,'report/objects/'+identity([category,case_id]),
                    record['response']['payload'],producer=record['product_sha256'],role='sealed_own_product')
                own_objects.append(obj)
                own.append({'case_id':case_id,'category':category,'value_object':obj,
                            'original_process_receipt':record['process_receipt']})
        for job in self.data['aggregate_jobs']:
            if job['issuer']=='participant':
                record=self.aggregates[job['id']]
                obj=put_object(self.store,'report/objects/'+identity(['aggregate',job['id']]),
                    record['response']['result'],producer=record['product_sha256'],role='sealed_own_product')
                own_objects.append(obj)
                own.append({'aggregate_id':job['id'],'value_object':obj,
                            'original_process_receipt':record['process_receipt']})
        sealed=own.seal();visible=[]
        def expose(desc):
            visible.append(desc);index=self.store.json(desc,{'sealed_record_index'})
            for item in index['members']:
                if index['depth']:expose(item)
                else:visible.append(item)
        expose(sealed['root'])
        for obj in own_objects:
            visible.extend({**d,'role':'sealed_own_product'} for d in object_descriptors(self.store,obj))
        self.report=self.actor.invoke('report',{'own_products':sealed,
            'required_obligations':sorted(self.plan.contracts.obligations),
            'all_input_source_gaps':self.plan.value['source_gap_register'],
            'no_protected_reference_values_available':True},lane='R',protocol_id='whole_report',
            source=self.R_source,artifacts=[*visible,*self.data['common_views'],
                                          *self._stage_products(self.build_R,{'build_artifact'})])
        expected={f'R{i:02d}' for i in range(37)}|({f'I{i:02d}' for i in range(1,6)} if not self.plan.r_only else set())
        rows=actor_table(self.store,self.report,'obligations',{'participant_report'})
        require({x['id'] for x in rows}==expected and len(rows)==len(expected),'REPORT_OMITS_OR_DUPLICATES_OBLIGATIONS')
        self.op('O25',[self.report['process_receipt']])

    def close_and_seal(self):
        self.phase_start('P09')
        # Legacy actual76 outputs validate under original semantics BEFORE any gold decode.
        legacy_candidate=self.extract_legacy_candidate()
        self.legacy_validation=self.science.invoke('score.legacy76_validate',arrays={},protocol={
            'legacy_design_identity_admitted':True},parameters={'design':self.data['legacy_public_design'],
            'candidate':legacy_candidate},lineage={'original_candidate_receipts':[
            self.participant_records[c['case_id']]['process_receipt'] for c in self.data['R_cases']
            if 'R00' in c['obligations']]},namespace='trusted_collection')
        require(self.legacy_validation['response']['result']['status']=='ok','LEGACY_CANDIDATE_INVALID_BEFORE_GOLD')
        self.resource_report={'complete':True,'snapshot':self.meter.snapshot(),
            'all_original_process_receipts':self._all_process_receipts(),
            'controller_not_final_yet':True,'final_grade_and_reporting_costs_still_required':True}
        close=self.journal.append('PARTICIPANT_REFERENCE_REPORT_RESOURCE_CLOSE',self.resource_report)
        self.op('O26',[close])
        self.op('O27',[self.legacy_validation['process_receipt'],{'full_product_binding_validation':'before_global_commit'}])
        expected=[];entries=[]
        for case in [*self.data['R_cases'],*([] if self.plan.r_only else self.data['I_cases'])]:
            record=self.participant_records[case['case_id']];p=record['response']['payload']
            binding={'id':'participant/'+case['case_id'],'issuer':'participant-'+case['lane'],
                'source':record['request']['source_manifest_sha256'],'state':p['state_sha256'],
                'input_identity':case['input_sha256'],'support_identity':case['original_support_sha256']}
            expected.append(binding);entries.append((binding,record))
        for case_id,record in self.uncertainty_records.items():
            case=self.data['case_by_id'][case_id];state=self.states[case['fold_id']]
            binding={'id':'participant/uncertainty/'+case_id,'issuer':'participant-I-uncertainty',
                'source':record['request']['source_manifest_sha256'],
                'state':state['uncertainty_selection']['state_id'],
                'input_identity':case['input_sha256'],'support_identity':case['original_support_sha256']}
            expected.append(binding);entries.append((binding,record))
        for job in self.data['R_reference_jobs']:
            record=self.reference_records[job['id']]
            binding={'id':'reference/R/'+job['id'],'issuer':'reference-R',
                'source':self.science.source['source_manifest_sha256'],'state':job['reference_state_id'],
                'input_identity':job['input_sha256'],'support_identity':job['original_support_sha256']}
            expected.append(binding);entries.append((binding,record))
        for (variant,case_id),item in self.references.diagnostic_evaluation.items():
            record=item['record'];case=self.data['case_by_id'][case_id]
            binding={'id':'reference/diagnostic/'+variant+'/'+case_id,'issuer':'reference-diagnostic',
                'source':self.science.source['source_manifest_sha256'],'state':item['state_id'],
                'input_identity':case['input_sha256'],'support_identity':case['original_support_sha256']}
            expected.append(binding);entries.append((binding,record))
        for (variant,case_id),record in self.references.evaluation.items():
            case=self.data['case_by_id'][case_id]
            binding={'id':'reference/I/'+variant+'/'+case_id,'issuer':'reference-I',
                'source':self.science.source['source_manifest_sha256'],
                'state':record['request']['lineage']['point_state_id'],
                'input_identity':case['input_sha256'],'support_identity':case['original_support_sha256']}
            expected.append(binding);entries.append((binding,record))
        collector=Collector(self.plan,self.store,self.journal,self.meter,expected)
        for binding,record in entries:
            self.checkpoint('next_full_product_collection')
            collector.add(binding['id'],record,**{k:v for k,v in binding.items() if k!='id'})
        ancestry={k:{**v,'groups':sorted(v['groups'])} for k,v in self.ancestry.nodes.items()}
        pregrade=set(self.plan.contracts.operators)-{'O28','O29','O30'}
        require(pregrade<=set(self.operator_receipts),'MISSING_PRE_GRADE_OPERATOR_CUSTODY',
                sorted(pregrade-set(self.operator_receipts)))
        self.global_seal=collector.seal({'terminal_complete':True,'report_sha256':self.report['product_sha256'],
            'process_receipt':self.report['process_receipt']},self.resource_report,ancestry,self.capsule,
            {'covered':sorted(pregrade),'receipts':self.operator_receipts})
        self.checkpoint('after_global_seal_before_any_target')
        return self.global_seal

    def extract_legacy_candidate(self):
        records=[]
        for case in self.data['R_cases']:
            if 'R00' not in case['obligations']:continue
            value=self.participant_records[case['case_id']]['response']['payload']['value']
            require(type(value) is dict and type(value.get('records')) is list,'LEGACY76_RECORDS_REQUIRED')
            records.extend(value['records'])
        return {'records':records}

    def _all_process_receipts(self):
        # Complete stage history is sharded in the original journal; this index binds
        # every actual request without pretending it is a fresh numerical run.
        receipts=[x['process_receipt'] for x in self.actor.responses]
        receipts += [x['process_receipt'] for x in self.references.records]
        receipts += [x['process_receipt'] for x in self.preparation.products.values()]
        receipts += [x['process_receipt'] for x in self.reference_records.values() if 'process_receipt' in x]
        receipts += [x['process_receipt'] for x in self.aggregates.values()]
        receipts += [self.legacy_validation['process_receipt']]
        unique={x['sha256']:x for x in receipts}
        return {'count':len(unique),'receipt_index':put_object(self.store,'resources/process-receipts',
                list(unique.values()),producer=self.plan.hash)}

    def run_to_seal(self):
        self.checkpoint('before_complete_campaign')
        self.prepare_and_learn();self.reproduce_and_infer();self.aggregate_and_report()
        return self.close_and_seal()

    def grade(self,paired_campaign=None):
        require(self.global_seal is not None,'GRADING_WITHOUT_COMPLETE_COLLECTION')
        self.phase_start('P10')
        access=TargetAccess(self.authority,self.plan,self.store,self.journal,self.meter,self.global_seal)
        capability=access.check('initial_target_last_grading_capability')
        self.op('O28',[capability])
        grader=Grade(self.plan,self.science,self.meter,self.journal,self.store,access)
        result=grader.run(self,self.data['protected_target_index'],paired_campaign)
        self.checkpoint('after_final_grade_before_grade_receipt')
        self.op('O29',result['scientific_receipts'])
        self.op('O31',[{'original_receipt_head':self.journal.head,
            'source_versions':{'I':self.actor.source['source_manifest_sha256'],
                               'R':self.R_source['source_manifest_sha256']},
            'all_prior_costs':self.meter.snapshot(),'exposure_history':self.exposure}])
        output=put_object(self.store,'result/complete-report',{
            'schema':'finite_complete_result_v1','run_id':self.actor.run_id,'arm':self.plan.arm,
            'route':self.plan.route,'plan_sha256':self.plan.hash,'capsule_sha256':identity(self.capsule),
            'global_seal':self.global_seal,'report_product_sha256':self.report['product_sha256'],
            'grading':result,'original_exposure_history':self.exposure,
            'costs_before_final_closure':self.meter.snapshot(),
            'no_qualified_count_promotion':True},producer=self.journal.head,role='final_report_chunk')
        self.checkpoint('after_final_report_before_publication')
        self.op('O30',[{'final_report':output}])
        require(set(self.operator_receipts)==set(self.plan.contracts.operators),'INCOMPLETE_32_FINAL_OPERATORS')
        self.checkpoint('before_final_success_commit')
        receipt=self.journal.append('PROGRAMME_COMPLETE',{'final_report':output,
            'operator_census':sorted(self.operator_receipts),'resources':self.meter.snapshot()})
        self.checkpoint('after_final_success_before_return')
        self.closed=True
        return {'report':output,'original_completion':receipt,'scientific_benchmark_ready':False,
                'source_and_execution_qualification_are_separate':True}


def execute_campaigns(campaigns):
    """Both source arms freeze every I state before either arm's R disclosure."""
    require(1<=len(campaigns)<=2,'INVALID_ARM_CENSUS')
    if len(campaigns)==2:
        by={c.plan.arm:c for c in campaigns}
        require(set(by)=={'A','B'},'PAIRED_ROUTE_REQUIRES_BOTH_ARMS')
        a,b=by['A'],by['B']
        require(a.actor.participant_id!=b.actor.participant_id,'CONTINUING_CONTEXT_IS_NOT_INDEPENDENT_ACCESS_ARM')
        require(a.plan.value['same_inputs_A_B_sha256']==b.plan.value['same_inputs_A_B_sha256']==
                paired_input_target_identity(a.plan,a.data)==paired_input_target_identity(b.plan,b.data),
                'PAIRED_INPUT_CONTRACT_MISMATCH')
        require(a.data['paired_experiment_identity']==b.data['paired_experiment_identity'],
                'PAIRED_EXPERIMENT_MISMATCH')
    for c in campaigns:c.prepare_and_learn()
    for c in campaigns:
        c.checkpoint('all_arm_I_capsules_before_first_R')
        require(all(x.capsule is not None for x in campaigns),'MISSING_CROSS_ARM_I_SEAL')
        c.journal.append('ALL_SELECTED_ARM_I_CAPSULES_SEALED',{
            'capsules':{x.plan.arm:identity(x.capsule) for x in campaigns}})
    for c in campaigns:c.reproduce_and_infer()
    for c in campaigns:c.aggregate_and_report()
    for c in campaigns:c.close_and_seal()
    for c in campaigns:
        c.checkpoint('paired_global_barrier_before_targets')
        require(all(x.global_seal is not None for x in campaigns),'EARLY_PAIRED_TARGET_ACCESS')
        c.journal.append('ALL_SELECTED_ARM_PRODUCTS_COMMITTED',{
            'seals':{x.plan.arm:x.global_seal for x in campaigns}})
    return {c.plan.arm:c.grade(next((x for x in campaigns if x is not c),None)) for c in campaigns}
