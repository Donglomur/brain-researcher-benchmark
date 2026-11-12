"""Trusted joins of original participant products and pre-R frozen comparators.

This module performs identity/transport joins only. All numerical comparisons are
owned by the separately qualified scientific kernels. No participant supplies the
reference side of a contrast.
"""
from .common import require,identity

def field(value,path):
    require(type(path) is list,'FIELD_PATH_LIST_REQUIRED')
    for key in path:
        require((type(value) is dict and type(key) is str and key in value) or
                (type(value) is list and type(key) is int and 0<=key<len(value)),
                'MISSING_DECLARED_SCIENTIFIC_FIELD',path)
        value=value[key]
    return value

class Products:
    def __init__(self,campaign,truth_access=None):
        self.c=campaign;self.truth_access=truth_access
        self.cases={x['case_id']:x for x in campaign.data['R_cases']+campaign.data['I_cases']}

    def participant(self,case_id,uncertainty=False):
        c=self.c;case=self.cases[case_id]
        absent_ci=uncertainty and case_id not in c.uncertainty_records
        if absent_ci:
            require(c.states[case['fold_id']]['uncertainty_state'] is None,
                    'MISSING_REQUIRED_UNCERTAINTY_PRODUCT')
        record=(c.uncertainty_records if uncertainty and not absent_ci else c.participant_records)[case_id]
        payload=record['response']['payload'];request=record['request']
        if absent_ci:
            # An explicit original calibration no-call is an observed denominator,
            # not a fabricated CI or a claimed separate participant invocation.
            payload={**payload,'state_sha256':None,'status':'no_call','value':None,
                'intervals':{str(x):{'status':'no_call','space':'gamma','intervals':[]}
                             for x in (.5,.8,.9,.95)}}
        require(payload['input_sha256']==case['input_sha256'] and
                payload['selection_sha256']==case['selection_sha256'],'ACTUAL_PRODUCT_CASE_CHANGED')
        require(request['plan_sha256']==c.plan.hash,'ACTUAL_PRODUCT_PLAN_CHANGED')
        require(record['product_sha256']==identity(record['response']),'ACTUAL_PRODUCT_BYTES_CHANGED')
        if case['lane']=='I':
            frozen=c.states[case['fold_id']]
            sid=frozen['uncertainty_selection']['state_id'] if uncertainty else frozen['state_id']
            require(payload['state_sha256']==sid,'POST_SEAL_PARTICIPANT_STATE_SUBSTITUTION')
            require(request['source_manifest_sha256']==c.actor.source['source_manifest_sha256'],
                    'POST_SEAL_PARTICIPANT_SOURCE_SUBSTITUTION')
        return record,payload

    def reference(self,case,category,variant_id=None):
        refs=self.c.references;key_id=case['reference_key']
        selection=refs.selections[key_id][category]
        require(selection['product_sha256']==refs.sealed['selections'][key_id][category],
                'REFERENCE_SELECTOR_CHANGED_AFTER_R')
        result=selection['response']['result']
        if variant_id is None:
            require(result['status']=='ok' and result['outputs']['selected_id'] is not None,
                    'NO_QUALIFIED_REFERENCE_SELECTION')
            selected=result['outputs']['selected_id']
        else:selected=variant_id
        candidates=list(refs.contracts.variants(key_id) if category=='point'
                        else refs.contracts.uncertainty_variants(key_id))
        matches=[v for v in candidates if v['id']==selected]
        require(len(matches)==1,'SELECTED_REFERENCE_NOT_IN_ORIGINAL_BANK')
        variant=matches[0]
        point_id=f"{key_id}/{variant['reference_id']}/{variant['variant']}"
        actual=refs.evaluation[(point_id,case['case_id'])]
        require(actual['product_sha256']==identity(actual['response']),'REFERENCE_PRODUCT_CHANGED')
        lineage=actual['request']['lineage'];out=actual['response']['result']['outputs']
        require(lineage['input_identity']==case['input_sha256'] and
                actual['request']['source_manifest_sha256']==refs.sealed['source_sha256'],
                'REFERENCE_INPUT_OR_SOURCE_SUBSTITUTION')
        require(lineage['provider_plan_sha256']==refs.sealed['provider_plan_sha256'],
                'REFERENCE_PROVIDER_PLAN_SUBSTITUTION')
        if category=='point':
            sid=refs.states[refs.state_key(variant)]['state_id']
            require(lineage['point_state_id']==sid,'REFERENCE_POINT_STATE_SUBSTITUTION')
            value=out['point']
        else:
            parent=refs.interval_state(variant,variant);sid=parent['state_id']
            require(lineage['interval_states'][selected]==parent,
                    'REFERENCE_INTERVAL_PARENT_SUBSTITUTION')
            value=out['uncertainty'][selected]
        return {'variant_id':selected,'state_id':sid,'source_sha256':refs.source,
                'value':value,'record':actual}

    def paired(self,target,category):
        expected=[];rows=[];c=self.c
        require(category in {'point','uncertainty'},'UNKNOWN_COMPARISON_CATEGORY')
        for original in target['expected_cases']:
            c.checkpoint('next_original_comparison_join')
            case=self.cases[original['case_id']]
            require(case['kind']=='known_truth' and case['lane']=='I','WRONG_PROSPECTIVE_CASE')
            require(original['input_identity']==case['input_sha256'] and
                    original['target_identity']==case['target_identity'],'TARGET_CASE_CONTRACT_SUBSTITUTION')
            for key in ('world_id','family','cell','view'):
                require(original[key]==case[key],'TARGET_ORIGINAL_SUPPORT_CHANGED',key)
            original=c.preparation.truth.expected(original,case,'evaluation',access=self.truth_access)
            actual,payload=self.participant(case['case_id'],category=='uncertainty')
            reference=self.reference(case,category)
            e={**original,'candidate_state_id':payload['state_sha256'],
               'candidate_source_sha256':actual['request']['source_manifest_sha256'],
               'reference_state_id':reference['state_id'],'reference_source_sha256':reference['source_sha256'],
               'reference_variant_id':reference['variant_id']}
            row={k:v for k,v in e.items() if k!='truth'}
            value=reference['value']
            if category=='point':
                row.update(candidate={'status':payload['status'],'gamma':payload['value']},
                           reference={'status':value['status'],'gamma':value['outputs'].get('gamma')})
            else:
                row.update(candidate_sets=payload['intervals'],reference_sets=value['outputs']['sets'],
                           reference_status=value['status'])
            expected.append(e);rows.append(row)
        return {'expected_cases':expected,'records':rows,'bootstrap_seeds':target['bootstrap_seeds']}

    def reproduction(self,target):
        actual=[];reference=[]
        for binding in target['product_bindings']:
            self.c.checkpoint('next_original_reproduction_join')
            case=self.cases[binding['case_id']];a,payload=self.participant(case['case_id'])
            r=self.c.reference_records[binding['reference_job_id']]
            require(case['lane']=='R' and case['original_support_sha256']==binding['original_support_sha256'],
                    'REPRODUCTION_SUPPORT_SUBSTITUTION')
            require(r['request']['lineage']['original_support_sha256']==case['original_support_sha256'],
                    'REFERENCE_REPRODUCTION_SUPPORT_SUBSTITUTION')
            base={k:binding[k] for k in ['id','version','target_identity']}
            actual.append({**base,'status':payload['status'],
                **{name:field(payload,path) for name,path in binding['participant_fields'].items()}})
            result=r['response']['result']
            reference.append({**base,'status':result['status'],
                **{name:field(result,path) for name,path in binding['reference_fields'].items()}})
        require([x['id'] for x in actual]==target['expected_ids'],'REPRODUCTION_ORDER_OR_CENSUS_CHANGED')
        return {'expected_ids':target['expected_ids'],'actual':actual,'reference':reference,
                'field_tolerances':target['field_tolerances']}

    def transfer(self,target):
        groups=[]
        for group in target['unit_manifest']:
            self.c.checkpoint('next_descriptive_transfer_group')
            rows=[]
            for binding in group['product_bindings']:
                _,payload=self.participant(binding['case_id'])
                row={'id':binding['draw_id'],'status':payload['status'],
                     **{name:field(payload,path) for name,path in binding['fields'].items()}}
                rows.append(row)
            groups.append({k:group[k] for k in ('group_id','identities','unit','planned_draws','aggregation')}|
                          {'records':rows})
        return {'expected_group_ids':target['expected_groups'],'groups':groups}

    def access(self,target,other):
        require(self.c.plan.arm=='A' and other.c.plan.arm=='B','ACCESS_ARM_ORIENTATION_CHANGED')
        require(self.c.global_seal and other.c.global_seal,'ACCESS_BEFORE_BOTH_GLOBAL_SEALS')
        require(self.c.plan.value['same_inputs_A_B_sha256']==other.c.plan.value['same_inputs_A_B_sha256'],
                'UNMATCHED_ACCESS_CASE_CONTRACT')
        expected=[];rows=[]
        for original in target['expected_cases']:
            self.c.checkpoint('next_paired_access_join');other.c.checkpoint('next_paired_access_join')
            a,pa=self.participant(original['case_id']);b,pb=other.participant(original['case_id'])
            ca=self.cases[original['case_id']];cb=other.cases[original['case_id']]
            require(self.c.plan.case_contract(ca)==other.c.plan.case_contract(cb),
                    'CROSS_ACCESS_SUPPORT_SUBSTITUTION')
            require(original['input_identity']==ca['input_sha256'] and
                    original['target_identity']==ca['target_identity']==cb['target_identity'],
                    'CROSS_ACCESS_TARGET_SUBSTITUTION')
            original=self.c.preparation.truth.expected(original,ca,'evaluation',access=self.truth_access)
            other_expected=other.c.preparation.truth.expected(original,cb,'evaluation',access=other.truth_access)
            require(other_expected['truth']==original['truth'],'PAIRED_GENERATOR_TRUTH_CHANGED')
            e={**original,'arm_A_state_id':pa['state_sha256'],'arm_B_state_id':pb['state_sha256'],
               'arm_A_source_sha256':a['request']['source_manifest_sha256'],
               'arm_B_source_sha256':b['request']['source_manifest_sha256']}
            expected.append(e);rows.append({**{k:v for k,v in e.items() if k!='truth'},
                'arm_A':{'status':pa['status'],'gamma':pa['value']},
                'arm_B':{'status':pb['status'],'gamma':pb['value']}})
        return {'expected_cases':expected,'records':rows,'bootstrap_seeds':target['bootstrap_seeds']}

    def support(self,target):
        require(len(target['expected_cases'])==240,'INCOMPLETE_240_SUPPORT_CHALLENGES')
        rows=[]
        for case in target['expected_cases']:
            self.c.checkpoint('next_original_support_challenge')
            _,payload=self.participant(case['case_id'])
            require(payload['input_sha256']==case['input_identity'],'SUPPORT_INPUT_SUBSTITUTION')
            rows.append({'case_id':case['case_id'],'input_identity':case['input_identity'],
                         'status':payload['status'],'gamma':payload['value']})
        return {'expected_cases':target['expected_cases'],'records':rows}

    def mandatory(self,target):
        comparison=target['comparison'];expected=[];rows=[]
        require(comparison in self.c.data['mandatory_pairwise_manifest'],
                'UNSCHEDULED_HELD_TARGET_PAIRWISE_SELECTION')
        for original in target['expected_cases']:
            self.c.checkpoint('next_mandatory_pairwise_original_case')
            require(original['target_class']==comparison['target_class'] and
                    original['protocol_id']==comparison['protocol_id'], 'PAIRWISE_TARGET_PROTOCOL_CHANGED')
            case=self.cases[original['case_id']];ci=comparison['endpoint']=='uncertainty'
            require(case['reference_key']==comparison['key_id'] and
                    case['input_sha256']==original['input_identity'],'MANDATORY_PAIRWISE_CASE_SUBSTITUTION')
            original=self.c.preparation.truth.expected(original,case,'evaluation',access=self.truth_access)
            actual,payload=self.participant(case['case_id'],ci)
            if comparison['kind']=='primary_bank_variant':
                reference=self.reference(case,'uncertainty' if ci else 'point',comparison['reference_variant_id'])
            else:
                d=self.c.references.diagnostic_evaluation[(comparison['reference_variant_id'],case['case_id'])]
                require(d['source_version']==comparison['reference_source_version'] and
                        d['target_class']==comparison['target_class'] and d['protocol_id']==comparison['protocol_id'],
                        'DIAGNOSTIC_VERSION_OR_TARGET_SUBSTITUTION')
                r=d['record'];raw=r['response']['result']
                bindings=d['pairwise_fields']
                require(bindings==comparison.get('reference_fields',{'gamma':['outputs','gamma']}),
                        'DIAGNOSTIC_LITERAL_OUTPUT_PROJECTION_CHANGED')
                if comparison['compatibility']['same_estimand']:
                    require('gamma' in bindings,'MISSING_COMPATIBLE_LITERAL_RATIO_FIELD')
                    gamma=field(raw,bindings['gamma']) if raw['status']=='ok' else None
                else:gamma=None
                reference={'state_id':d['state_id'],
                    'source_sha256':r['response']['source_manifest_sha256'],
                    'variant_id':comparison['reference_variant_id'],
                    'value':{'status':raw['status'],'outputs':{'gamma':gamma}}}
            e={**original,'candidate_state_id':payload['state_sha256'],
                'candidate_source_sha256':actual['request']['source_manifest_sha256'],
                'reference_state_id':reference['state_id'],'reference_source_sha256':reference['source_sha256'],
                'reference_variant_id':reference['variant_id']}
            row={k:v for k,v in e.items() if k!='truth'};value=reference['value']
            if ci:row.update(candidate_sets=payload['intervals'],reference_sets=value['outputs']['sets'],
                             reference_status=value['status'],candidate_status=payload['status'])
            else:row.update(candidate={'status':payload['status'],'gamma':payload['value']},
                            reference={'status':value['status'],'gamma':value['outputs'].get('gamma')})
            expected.append(e);rows.append(row)
        return {'comparison':comparison,'expected_cases':expected,'records':rows}
