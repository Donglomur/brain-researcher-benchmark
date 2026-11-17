"""Independent fit/residual/calibration/selection/seal/evaluation programme."""
from __future__ import annotations
from .common import require,identity,Refusal

class References:
    def __init__(self,contracts,science,meter,journal,source_sha256,qualification,case_arrays,case_truth):
        self.contracts,self.science,self.meter,self.journal=contracts,science,meter,journal
        self.source=source_sha256;self.qualification=qualification;self.case_arrays=case_arrays;self.case_truth=case_truth
        self.states={};self.residual_states={};self.calibration={};self.evaluation={}
        self.selections={};self.records=[];self.sealed=None;self.prior_states={}
        self.provider_plan=None;self.provider_plan_hash=None;self.diagnostic_evaluation={}

    def bind_provider_plan(self, provider_plan):
        require(self.provider_plan is None and not self.records,'LATE_PROVIDER_PLAN_BINDING')
        # Canonical string keys, never JSON tuple-key coercion. Every later job must
        # equal this predeclared source/recipe/case input binding.
        self.provider_plan=dict(provider_plan)
        self.provider_plan_hash=identity(provider_plan)
        require(self.provider_plan_hash==self.qualification['provider_plan_sha256'],
                'UNREVIEWED_UNCERTAINTY_PROVIDER_PLAN')

    def providers_for(self,variant_id,case_id):
        require(self.provider_plan is not None,'UNSEALED_PROVIDER_PLAN')
        return self.provider_plan.get(variant_id+'::'+case_id,{})

    def interval_state(self, variant, ci):
        sk=self.state_key(variant)
        definitions=self.qualification['provider_definitions'].get(variant['id'],{})
        recipe=definitions.get(ci['rule']) if ci['rule']!='U04_DEVELOPMENT_RESIDUAL' else {
            'source_sha256':self.source,'qualification_id':self.qualification['residual_fit']}
        return {'state_id':identity({'point_state':self.states[sk]['state_id'],
            'residual_state':self.residual_states[sk]['state_id'], 'point_id':variant['id'],
            'rule':ci['rule'],'scale':ci['scale'],'provider_definition':recipe,
            'provider_plan':self.provider_plan_hash}),
            'point_state_id':self.states[sk]['state_id'],
            'residual_state_id':self.residual_states[sk]['state_id'],
            'provider_definition_sha256':identity(recipe),
            'provider_plan_sha256':self.provider_plan_hash}

    def state_key(self,variant):
        key=self.contracts.keys[variant['key']]
        return identity([variant['reference_id'],variant['variant'],key['target_class'],key['protocol'],key['trial_view']])

    def protocol(self,key,case=None):
        p={**self.qualification['protocol'],**(case['scientific_protocol'] if case else {}),
           'primary_key':key['id'],'family':key['family'],'target':key['target_class'],
           'protocol_id':key['protocol'],'trial_view':key['trial_view'],
           'reference_definition_presealed':True}
        if case:p['input_identity']=case['input_sha256']
        return p

    def execute(self,operation,variant,key,*,arrays,parameters,protocol=None,lineage=None):
        self.meter.checkpoint('next_independent_reference_operation')
        p=self.protocol(key) if protocol is None else protocol
        record=self.science.invoke(operation,arrays=arrays,protocol=p,parameters=parameters,
            lineage={'reference_variant':variant['id'],'reference_source_sha256':self.source,
                     **(lineage or {})},namespace='independent_reference')
        self.records.append(record)
        return record

    def fit(self,development):
        require(self.sealed is None,'REFERENCE_REFIT_AFTER_SEAL')
        variants=[v for key in self.contracts.keys for v in self.contracts.variants(key)]
        for variant in variants:
            key=self.contracts.keys[variant['key']];state_key=self.state_key(variant)
            if state_key in self.states:continue
            record=self.execute('reference.fit',variant,key,arrays={},parameters={
                'reference_id':variant['reference_id'],'variant':variant['variant']})
            result=record['response']['result']
            require(result['status']=='ok','REFERENCE_FIT_REQUIRED_UNSCORABLE')
            self.states[state_key]={'state':result['outputs']['state'],'state_id':identity(result['outputs']['state']),
                                    'receipt':record['process_receipt'],'source_sha256':self.source}
        # Exact20/cell residual half spans every compatible family for a fixed point identity.
        for variant in variants:
            sk=self.state_key(variant)
            if sk in self.residual_states:continue
            key=self.contracts.keys[variant['key']];point=self.states[sk]
            compatible=[k for k in self.contracts.keys.values()
                if k['target_class']==key['target_class'] and k['protocol']==key['protocol']
                and k['trial_view']==key['trial_view']
                and variant['reference_id'] in k['eligible_reference_ids_before_qualification']]
            expected=[];records=[]
            for current in compatible:
                worlds=development[current['id']]['uncertainty_residual_fit']
                require(len(worlds)==120,'INCOMPLETE_RESIDUAL_HALF')
                for case in worlds:
                    self.meter.checkpoint('next_residual_fit_world')
                    v={**variant,'key':current['id'],
                       'id':f"{current['id']}/{variant['reference_id']}/{variant['variant']}"}
                    req={**case['reference_parameters'],'reference_id':v['reference_id'],
                         'variant':v['variant'],'state':point['state']}
                    r=self.execute('reference.point',v,current,arrays=self.case_arrays(case),
                          protocol=self.protocol(current,case),parameters=req,
                          lineage={'point_state_id':point['state_id'],'case_id':case['case_id'],
                                   'input_identity':case['input_sha256'],'allocation':'uncertainty_residual_fit'})
                    output=r['response']['result']
                    e={'world_id':case['world_id'],'key_id':current['id'],'cell':case['cell'],
                       'input_identity':case['input_sha256'],'allocation':'uncertainty_residual_fit',
                       'truth':self.case_truth(case,'development')}
                    expected.append(e);records.append({**{k:e[k] for k in e if k!='truth'},
                        'status':output['status'],'gamma':output['outputs'].get('gamma'),
                        'reference_id':v['reference_id'],'variant':v['variant'],
                        'point_state_id':point['state_id'],'point_source_sha256':self.source})
            p=self.protocol(key);p.update(stage='uncertainty_residual_fit',fit_pool_ancestry_admitted=True)
            r=self.execute('uncertainty.residual_fit',variant,key,arrays={},protocol=p,parameters={
                'reference_id':variant['reference_id'],'variant':variant['variant'],
                'point_state_id':point['state_id'],'point_source_sha256':self.source,
                'expected_worlds':expected,'records':records})
            result=r['response']['result'];require(result['status']=='ok','RESIDUAL_FIT_REQUIRED_UNSCORABLE')
            state=result['outputs']['state']
            self.residual_states[sk]={'state':state,'state_id':identity(state),'receipt':r['process_receipt']}
        self.fit_diagnostics(development)
        return self.states

    def fit_diagnostics(self,development):
        for key in self.contracts.keys.values():
            binding=(key['target_class'],key['protocol'],key['trial_view'])
            if binding in self.prior_states:continue
            worlds=[]
            for compatible in self.contracts.keys.values():
                if (compatible['target_class'],compatible['protocol'],compatible['trial_view'])!=binding:continue
                for case in development[compatible['id']]['point_fit']:
                    worlds.append({'world_id':case['world_id'],'key_id':compatible['id'],'cell':case['cell'],
                       'input_identity':case['input_sha256'],'allocation':'point_fit','truth':self.case_truth(case,'development')})
            p=self.protocol(key);p.update(stage='point_fit',fit_pool_ancestry_admitted=True)
            variant={'id':'diagnostic-prior/'+identity(binding)}
            request={'reference_id':'REF16_PRIOR_CONSTANT',
                'variant':self.contracts.bank['REF16_PRIOR_CONSTANT']['variants'][0],
                'expected_worlds':worlds,'records':worlds}
            r=self.execute('reference.fit',variant,key,arrays={},parameters=request,protocol=p)
            result=r['response']['result'];require(result['status']=='ok','PRIOR_CONTROL_FIT_UNSCORABLE')
            state=result['outputs']['state']
            self.prior_states[binding]={'state':state,'state_id':identity(state),'receipt':r['process_receipt']}

    def bundle(self,case,variant,provider_jobs):
        require(provider_jobs==self.providers_for(variant['id'],case['case_id']),
                'PROVIDER_PLAN_SUBSTITUTION')
        key=self.contracts.keys[variant['key']];sk=self.state_key(variant)
        require(sk in self.states and sk in self.residual_states,'REFERENCE_NOT_FITTED')
        point=self.states[sk];residual=self.residual_states[sk];arrays=self.case_arrays(case);providers={};shared={}
        # Covariance/design-specific resampling providers are exact independently qualified
        # source jobs. Missing source is required-unscorable, not a generic bootstrap substitution.
        for rule,job in provider_jobs.items():
            require(rule in {'U01_FIELLER','U02_LOG_DELTA','U03_TWO_AXIS_PERCENTILE'},'UNKNOWN_INTERMEDIATE_RULE')
            require(job['point_id']==variant['id'] and job['input_identity']==case['input_sha256'],
                    'INTERMEDIATE_CASE_OR_VARIANT_SUBSTITUTION')
            definition=self.qualification['provider_definitions'][variant['id']][rule]
            require(job['definition_sha256']==identity(definition), 'PROVIDER_DEFINITION_SUBSTITUTION')
            require(job['operation']==definition['operation'] and
                    job['qualification_id']==definition['qualification_id'] and
                    definition['source_sha256']==self.source,'WRONG_PROVIDER_SOURCE_OR_OPERATION')
            self.meter.checkpoint('before_uncertainty_intermediate')
            expected_point={**case['reference_parameters'],'reference_id':variant['reference_id'],
                            'variant':variant['variant']}
            require(job['parameters']['point_request']==expected_point,
                    'PROVIDER_POINT_REQUEST_SUBSTITUTION')
            expected_protocol={**self.protocol(key,case),
                'resampling_design':definition['algorithm'],
                'resampling_qualification_id':definition['qualification_id']}
            require(job['protocol']==expected_protocol,'PROVIDER_PROTOCOL_SUBSTITUTION')
            from .uncertainty_plan import materialize_seeds
            seed_recipe=job['parameters']['seed_recipe']
            require(seed_recipe['context']==[self.source,variant['id'],case['case_id'],
                    case['input_sha256']], 'PROVIDER_SEED_CONTEXT_SUBSTITUTION')
            parameters={k:v for k,v in job['parameters'].items() if k!='seed_recipe'}
            parameters.update(materialize_seeds(seed_recipe))
            parameters['point_request']={**expected_point,'state':point['state']}
            token=identity({'operation':job['operation'],'protocol':job['protocol'],
                            'parameters':parameters,'state_id':point['state_id']})
            if token not in shared:
                produced=self.science.invoke(job['operation'],arrays=self.case_arrays(case),
                    protocol=job['protocol'],parameters=parameters,
                    lineage={'point_id':variant['id'],'input_identity':case['input_sha256'],
                    'state_id':point['state_id']},namespace='independent_reference')
                self.records.append(produced);shared[token]=produced
            else:produced=shared[token]
            array_bindings={}
            for field,descriptor in produced['response'].get('array_outputs',{}).items():
                destination={'moment_covariance':'covariance','bootstrap_gamma':'bootstrap_gamma'}.get(field)
                if destination:
                    qualified_key=rule+'.'+destination
                    arrays[qualified_key]=descriptor;array_bindings[destination]=qualified_key
            providers[rule]={'source_sha256':produced['response']['source_manifest_sha256'],
                 'state_id':point['state_id'],'receipt_id':produced['process_receipt']['sha256'],
                 'input_identity':case['input_sha256'],'qualification_id':job['qualification_id'],
                 'point_id':variant['id'],'array_bindings':array_bindings}
        providers['U04_DEVELOPMENT_RESIDUAL']={'source_sha256':self.source,'state_id':residual['state_id'],
             'receipt_id':residual['receipt']['sha256'],'input_identity':identity(residual['state']['training_world_ids']),
             'qualification_id':self.qualification['residual_fit'],'point_id':variant['id'],
             'development_pool_admitted':True,'residual_quantiles':residual['state']['quantiles'],
             'residual_n':len(residual['state']['training_world_ids'])}
        p=self.protocol(key,case)
        return self.execute('reference.bundle',variant,key,arrays=arrays,protocol=p,parameters={
            'point_request':{**case['reference_parameters'],'reference_id':variant['reference_id'],
                             'variant':variant['variant'],'state':point['state']},
            'providers':providers,'uncertainty_request':self.qualification['uncertainty_request']},
            lineage={'case_id':case['case_id'],'input_identity':case['input_sha256'],
                     'point_state_id':point['state_id'],'residual_state_id':residual['state_id'],
                     'interval_states':{ci['id']:self.interval_state(variant,ci)
                       for ci in self.contracts.uncertainty_variants(key['id'])
                       if ci['reference_id']==variant['reference_id'] and ci['variant']==variant['variant']},
                     'provider_plan_sha256':self.provider_plan_hash})

    def calibrate(self,calibration,provider_plan):
        require(identity(provider_plan)==self.provider_plan_hash,'LATE_PROVIDER_PLAN_CHANGE')
        require(self.sealed is None,'REFERENCE_CALIBRATION_AFTER_SEAL')
        for key_id,key in self.contracts.keys.items():
            cases=calibration[key_id];require(len(cases)==240,'INCOMPLETE_240_REFERENCE_CALIBRATION')
            expected=[{'world_id':x['world_id'],'cell':x['cell'],'input_identity':x['input_sha256'],
                       'truth':self.case_truth(x,'calibration')} for x in cases]
            points={};intervals={}
            for variant in self.contracts.variants(key_id):
                sk=self.state_key(variant);state=self.states[sk]
                base={'key_id':key_id,'reference_id':variant['reference_id'],'variant':variant['variant'],
                      'qualification_id':self.qualification['point'],'source_sha256':self.source,
                      'state_id':state['state_id']}
                points[variant['id']]={**base,'records':[]}
                cis=[v for v in self.contracts.uncertainty_variants(key_id)
                     if v['reference_id']==variant['reference_id'] and v['variant']==variant['variant']]
                for ci in cis:intervals[ci['id']]={**base,**self.interval_state(variant,ci),
                    'rule':ci['rule'],'scale':ci['scale'],'records':[]}
                for case in cases:
                    r=self.bundle(case,variant,self.providers_for(variant['id'],case['case_id']))
                    self.calibration[(variant['id'],case['case_id'])]=r
                    out=r['response']['result']['outputs'];point=out['point']
                    row={'world_id':case['world_id'],'cell':case['cell'],'input_identity':case['input_sha256'],
                         'source_sha256':self.source,'state_id':state['state_id']}
                    points[variant['id']]['records'].append({**row,'variant_id':variant['id'],
                         'status':point['status'],'gamma':point['outputs'].get('gamma')})
                    require(set(out['uncertainty'])=={x['id'] for x in cis},'MISSING_UNCERTAINTY_VARIANTS')
                    for ci in cis:
                        data=out['uncertainty'][ci['id']]
                        intervals[ci['id']]['records'].append({**row,**self.interval_state(variant,ci),'variant_id':ci['id'],
                            'status':data['status'],'sets':data['outputs']['sets']})
            p=self.protocol(key);p.update(selection_stage='public_calibration',bank_presealed=True)
            selections={}
            for category,variants,operation in [('point',points,'score.select_point'),
                                                ('uncertainty',intervals,'score.select_uncertainty')]:
                record=self.execute(operation,{'id':key_id+'/selector/'+category},key,arrays={},protocol=p,
                    parameters={'expected_worlds':expected,'expected_variant_ids':list(variants),'variants':variants})
                selections[category]=record
            self.selections[key_id]=selections
        return self.selections

    def seal(self):
        self.meter.checkpoint('reference_global_seal')
        require(set(self.selections)==set(self.contracts.keys),'MISSING_REFERENCE_SELECTOR_KEY')
        self.sealed={'source_sha256':self.source,'states':self.states,'residual_states':self.residual_states,
                     'selections':{k:{c:v['product_sha256'] for c,v in x.items()} for k,x in self.selections.items()},
                     'receipt_head':self.journal.head,'prior_states':[{'binding':list(k),'value':v}
                         for k,v in self.prior_states.items()],
                     'provider_plan_sha256':self.provider_plan_hash,
                     'provider_definitions_sha256':identity(self.qualification['provider_definitions']),
                     'qualified_point':all(x['point']['response']['result']['status']=='ok' and
                         x['point']['response']['result']['outputs']['selected_id'] is not None for x in self.selections.values()),
                     'qualified_uncertainty':all(x['uncertainty']['response']['result']['status']=='ok' and
                         x['uncertainty']['response']['result']['outputs']['selected_id'] is not None for x in self.selections.values())}
        return self.sealed

    def evaluate(self,evaluation,provider_plan):
        require(identity(provider_plan)==self.provider_plan_hash,'EVALUATION_PROVIDER_PLAN_CHANGE')
        require(self.sealed is not None,'EVALUATION_BEFORE_REFERENCE_SEAL')
        for key_id,cases in evaluation.items():
            require(key_id in self.contracts.keys,'UNKNOWN_REFERENCE_KEY')
            require(len(cases)==1200,'INCOMPLETE_REFERENCE_EVALUATION_KEY')
            for variant in self.contracts.variants(key_id):
                for case in cases:
                    self.meter.checkpoint('next_reference_evaluation_case')
                    record=self.bundle(case,variant,self.providers_for(variant['id'],case['case_id']))
                    self.evaluation[(variant['id'],case['case_id'])]=record
        require(set(evaluation)==set(self.contracts.keys),'REFERENCE_EVALUATION_SCOPE_REDUCTION')
        return self.evaluation

    def diagnostic_bank(self,jobs):
        covered=set();out=[]
        for job in jobs:
            self.meter.checkpoint('next_diagnostic_reference')
            rid=job['reference_id'];require(rid in self.contracts.bank,'UNKNOWN_DIAGNOSTIC_REFERENCE')
            covered.add(rid)
            protocol=dict(job['protocol']);parameters={**job['parameters'],'reference_id':rid,
                'variant':job['variant']}
            require(job['operation']=='reference.point','DIAGNOSTIC_REFERENCE_DISPATCH_CHANGED')
            if rid=='REF13_LITERAL_SOURCE':
                parameters['literal_version']=job['reference_source_version']
            else:
                require(job['reference_source_version']==job['variant'],'DIAGNOSTIC_FIXED_VERSION_CHANGED')
            require(protocol.get('primary_key') is None,'DIAGNOSTIC_CANNOT_BE_PRIMARY_REFERENCE')
            require(job['case']['case_id']==job['case_id'] and job['case']['input_sha256']==job['input_identity'],
                    'DIAGNOSTIC_CASE_SUBSTITUTION')
            arrays=self.case_arrays(job['case'])
            require(arrays==job['arrays'],'DIAGNOSTIC_ARRAY_SUBSTITUTION')
            if rid=='REF16_PRIOR_CONSTANT':
                binding=(protocol['target'],protocol['protocol_id'],protocol['trial_view'])
                require(binding in self.prior_states,'PRIOR_MUST_FIT_BEFORE_GLOBAL_REFERENCE_SEAL')
                prior=self.prior_states[binding];parameters['state']=prior['state']
                protocol.update(prior_state_ancestry_admitted=True,state_id=prior['state_id'])
            record=self.science.invoke(job['operation'],arrays=job['arrays'],protocol=protocol,
                parameters=parameters,lineage={'diagnostic':True,'reference_id':rid,
                'original_support_sha256':job['original_support_sha256']},namespace='independent_reference')
            token=(job['reference_variant_id'],job['case_id'])
            require(token not in self.diagnostic_evaluation,'DUPLICATE_DIAGNOSTIC_PRODUCT')
            self.diagnostic_evaluation[token]={'record':record,'state_id':job['reference_state_id'],
                'source_version':job['reference_source_version'],'target_class':protocol['target'],
                'protocol_id':protocol['protocol_id'],'pairwise_fields':job.get('pairwise_fields',{'gamma':['outputs','gamma']})}
            self.records.append(record);out.append(record)
        require({f'REF{i:02d}_'+name for i,name in [(13,'LITERAL_SOURCE'),(14,'TWONN'),
            (15,'HARMONIC'),(16,'PRIOR_CONSTANT'),(17,'STABLE_CONSTANT')]}<=covered,
            'REQUIRED_SECONDARY_REFERENCE_OMITTED')
        return out
