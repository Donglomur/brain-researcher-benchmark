"""Complete protected reproduction, improvement, uncertainty and access grading."""
from __future__ import annotations
from .common import require,decode,RESULT_LIMIT,identity,FRAME_LIMIT
from .proof import adjudicate
from .objects import get_object
from .comparisons import Products
from .tables import actor_table

class GuardedTargets:
    def __init__(self,store,access,max_bytes):
        self.store,self.access,self.meter=store,access,store.meter;self.max_bytes=max_bytes
        self.legacy_decodes=0
    def read(self,desc,roles):
        self.access.check('before_each_protected_body_read')
        return self.store.read(desc,roles)
    def json(self,desc,roles):return decode(self.read(desc,roles),FRAME_LIMIT)
    def expand(self,value):
        self.meter.checkpoint('next_protected_metadata_node')
        if type(value) is dict:
            if value.get('schema')=='finite_object_ref_v1':
                return self.expand(get_object(self,value,allowed_roles={'protected_truth'},max_bytes=self.max_bytes))
            return {k:(v if k=='legacy_target_ref' else self.expand(v)) for k,v in value.items()}
        if type(value) is list:return [self.expand(x) for x in value]
        return value
    def records(self,index):
        value=self.json(index,{'protected_target_index'});seen=set()
        for part in value['parts']:
            body=self.read(part,{'protected_truth'})
            for line in body.splitlines():
                self.meter.checkpoint('before_protected_target_decode')
                row=decode(line,RESULT_LIMIT)
                require(row['id'] not in seen,'DUPLICATE_PROTECTED_TARGET');seen.add(row['id'])
                yield self.expand(row)
        require(len(seen)==value['records'],'PROTECTED_TARGET_CENSUS_MISMATCH')
    def legacy(self,ref):
        self.access.check('before_original_legacy_gold_decode')
        value=get_object(self,ref,allowed_roles={'protected_truth'},max_bytes=self.max_bytes)
        self.legacy_decodes+=1
        self.meter.checkpoint('after_legacy_gold_decode_before_score')
        receipt=self.access.journal.append('LEGACY_GOLD_DECODE_COMPLETE',{
            'identity':ref,'actual_decode_count':self.legacy_decodes,
            'not_historical_standalone_loader_count':True})
        return value,receipt

class Grade:
    def __init__(self,plan,science,meter,journal,store,access):
        self.plan,self.science,self.meter,self.journal,self.store,self.access=plan,science,meter,journal,store,access
    def scientific(self,operation,parameters,protocol,lineage):
        self.access.check('before_each_protected_compare')
        result=self.science.invoke(operation,arrays={},parameters=parameters,protocol=protocol,
            lineage=lineage,namespace='protected_grade',access=self.access)
        self.meter.checkpoint('after_protected_compare_before_next_effect')
        return result

    def run(self,campaign,target_index,paired_campaign=None):
        self.meter.checkpoint('before_whole_protected_grade')
        products=Products(campaign,self.access)
        loader=GuardedTargets(self.store,self.access,self.plan.value['resource_preflight']['max_metadata_object_bytes'])
        targets={x['id']:x for x in loader.records(target_index)}
        report={x['id']:x for x in actor_table(self.store,campaign.report,'obligations',{'participant_report'})}
        dispositions={};records=[]
        required=[f'R{i:02d}' for i in range(37)]+([] if self.plan.r_only else [f'I{i:02d}' for i in range(1,6)])
        for obligation in required:
            self.meter.checkpoint('next_original_obligation_grade')
            require(obligation in targets,'MISSING_PROTECTED_OBLIGATION_TARGET',obligation)
            target=targets[obligation]
            require(target['scientific_plan_sha256']==self.plan.value['scientific_plan_sha256'],
                    'TARGET_FROM_OTHER_SCIENTIFIC_PLAN')
            if obligation in {'R01','R33','R35'}:
                dispositions[obligation]=adjudicate(obligation,report[obligation]['source_proof'],
                    target['rubric'],source_registry=self.plan.value['source_registry'],admission=self.access)
                continue
            if obligation in {'R31','R32'}:
                self.access.check('before_cost_adjudication')
                dispositions[obligation]={'status':'ok' if campaign.resource_report['complete'] else 'unscorable',
                    'actual_original_resources':campaign.resource_report,
                    'claim':'Original observed whole-job costs; final grading/report costs follow in closure.'}
                continue
            if obligation=='R00':
                require(campaign.legacy_validation['response']['result']['status']=='ok',
                        'LEGACY_GOLD_WITHOUT_ORIGINAL_VALIDATION')
                gold,receipt=loader.legacy(target['legacy_target_ref'])
                record=self.scientific('score.legacy76',{
                    'design':campaign.data['legacy_public_design'],
                    'candidate':campaign.extract_legacy_candidate(),'legacy_target':gold},
                    {'legacy_design_identity_admitted':True,'score_stage':'target_last',
                     'legacy_candidate_validation_receipt_id':campaign.legacy_validation['process_receipt']['sha256'],
                     'legacy_target_decode_receipt_id':receipt['sha256'],
                     'legacy_actual_target_decode_count':loader.legacy_decodes},
                    {'obligation':'R00','original_target_identity':identity(target['legacy_target_ref'])})
            elif obligation.startswith('R'):
                record=self.scientific('score.reproduction',products.reproduction(target),
                    {'tolerance_qualification_id':target['tolerance_qualification_id']},
                    {'obligation':obligation,'original_support_sha256':target['original_support_sha256']})
            elif obligation in {'I01','I02'}:
                category='point' if obligation=='I01' else 'uncertainty'
                qualified=campaign.references.sealed['qualified_'+category]
                candidate_ok=category=='point' or all(s['uncertainty_state'] is not None for s in campaign.states.values())
                if not qualified or not candidate_ok:
                    dispositions[obligation]={'status':'required_unscorable',
                        'reason':'No complete pre-R qualified comparator or participant uncertainty state.',
                        'all_planned_cases_retained':True,'no_reselection_or_fallback':True}
                    continue
                record=self.scientific('score.paired' if category=='point' else 'score.uncertainty_quality',
                    products.paired(target,category),
                    {'score_stage':'target_last','paired_states_sealed':True,
                     'inference_qualification_id':target['inference_qualification_id']},
                    {'selector_seal':identity(campaign.references.sealed),'global_seal':campaign.global_seal})
            elif obligation in {'I03','I04'}:
                record=self.scientific('aggregate.transfer',products.transfer(target),
                    {'score_stage':'target_last','transfer_group_manifest_admitted':True},
                    {'obligation':obligation,'unit_manifest_sha256':identity(target['unit_manifest'])})
            else:
                require(obligation=='I05','UNKNOWN_OBLIGATION_BRANCH')
                if paired_campaign is None:
                    dispositions[obligation]={'status':'pending_matched_arm',
                        'reason':'A complete independent second arm and original paired barrier are required.'}
                    continue
                from .collection import TargetAccess
                other_access=TargetAccess(paired_campaign.authority,paired_campaign.plan,
                    paired_campaign.store,paired_campaign.journal,paired_campaign.meter,paired_campaign.global_seal)
                other=Products(paired_campaign,other_access)
                a,b=(products,other) if campaign.plan.arm=='A' else (other,products)
                require(campaign.data['paired_experiment_identity']==paired_campaign.data['paired_experiment_identity'],
                        'PAIRED_EXPERIMENT_BINDING_CHANGED')
                record=self.scientific('score.access_effect',a.access(target,b),
                    {'score_stage':'target_last','paired_states_sealed':True,
                     'inference_qualification_id':target['inference_qualification_id']},
                    {'arm_A_seal':a.c.global_seal,'arm_B_seal':b.c.global_seal,
                     'paired_experiment':campaign.data['paired_experiment_identity']})
            records.append(record);dispositions[obligation]=record['response']['result']
            if obligation in {'I03','I04'}:
                dispositions[obligation]={'status':record['response']['result']['status'],
                    'descriptive_result':record['response']['result'],'biological_true_dimension_known':False,
                    'cross_source_population_claim':False}
        supplementary={}
        if not self.plan.r_only:
            require('SUPPORT240' in targets,'MISSING_SUPPORT_CHALLENGE_TARGETS')
            support=self.scientific('score.support',products.support(targets['SUPPORT240']),
                {'score_stage':'target_last'}, {'global_seal':campaign.global_seal})
            records.append(support);supplementary['support240']=support['response']['result']
            pairwise=[]
            for comparison in campaign.data['mandatory_pairwise_manifest']:
                self.meter.checkpoint('next_complete_mandatory_pairwise_comparison')
                target=targets['PAIRWISE/'+comparison['comparison_id']]
                require(target['comparison']==comparison,'PROTECTED_PAIRWISE_MANIFEST_CHANGED')
                result=self.scientific('score.mandatory_pairwise',products.mandatory(target),
                    {'score_stage':'target_last','paired_states_sealed':True,'pairwise_manifest_admitted':True},
                    {'global_seal':campaign.global_seal,'comparison_id':comparison['comparison_id']})
                records.append(result);pairwise.append({'comparison_id':comparison['comparison_id'],
                    'result':result['response']['result'],'original_receipt':result['process_receipt']})
            supplementary['mandatory_pairwise']=pairwise
        self.meter.checkpoint('after_all_grades_before_report')
        return {'obligations':dispositions,'supplementary_complete_controls':supplementary,'scientific_receipts':[x['process_receipt'] for x in records],
                'complete_requested_obligation_census':set(dispositions)==set(required),
                'qualified_count_promotion':False,'all_original_gates_retained':True}
