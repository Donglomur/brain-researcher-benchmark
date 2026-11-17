"""Case preparation and numerical-evidence joins for both canonical tasks.

This module prepares actual task packets; it does not grant a model process a
filesystem sandbox. The central provider/resource owner is a remaining producer.
"""
from .contracts import require,digest,Refusal
from .packets import prediction_packet,response_prediction_packet,equal_arm_specs
from .splits import validate_fold
from .storage import write_new

def prepare_prediction_cases(construction,feature_kind,private_key,limits):
    cases=[];excluded=[]
    for fold in construction['folds']:
        try:
            validate_fold(construction['rows'],fold)
        except Refusal as error:
            excluded.append({'fold':fold['id'],'reason':str(error)})
            continue
        public,private=prediction_packet(construction['rows'],fold,feature_kind,private_key)
        cases.append({'public':public,'private':private,'arms':equal_arm_specs(public,limits)})
    return {'cases':cases,'fold_dispositions':excluded,'canonical_task_count':1}

def prepare_response_cases(construction,private_key,limits):
    all_rows=[r for r in construction['rows'] if r['control']=='lagged']
    rows=[r for r in all_rows if r['classification_basis']=='independent_pretest']
    cases=[]
    for mouse in sorted({r['mouse'] for r in rows}):
        public,private=response_prediction_packet(rows,mouse,private_key)
        cases.append({'public':public,'private':private,'arms':equal_arm_specs(public,limits)})
    return {'cases':cases,'canonical_task_count':1,
            'response_selected_pairs_excluded':len(all_rows)-len(rows),
            'held_stimulation_signals_not_exposed':True,
            'effect_reconstruction':'separate executable-analysis channel; not a held-response prediction input'}

def investigation_truth(construction,source_digest):
    main=construction['outputs']['lagged']
    require('effect' in main,'investigation not estimable')
    improvements={r['mouse']:r['improvement'] for r in main['improvement']}
    return {'source_digest':source_digest,'disposition_digest':construction['disposition_digest'],
            'mouse_values':[{'mouse':r['mouse'],'effect':r['effect'],
                             'improvement':improvements.get(r['mouse'])} for r in main['effect']],
            'controls':['lead_null','tuning_rotation','distance_strata','true_sham_availability',
                        'response_class_selection','matched_covariates','independent_baseline'],
            'control_results':{'lead_null':construction['outputs']['lead_null'],
                'tuning_rotation':main['tuning_rotation_null'],'distance_strata':main['distance_sensitivity'],
                'true_sham_availability':construction['outputs']['true_sham'],
                'response_class_selection':main['site_class_association'],
                'matched_covariates':main['matched'],
                'independent_baseline':{'required':True,'missing_pair_count':sum(
                    row['reason']=='independent_baseline_cell_identity_missing'
                    for d in construction['dispositions'] for row in d.get('pairs',[]))}}}

def publish_cases(packet_set,public_root,private_root,artifact_cap):
    from pathlib import Path
    public_root=Path(public_root).resolve();private_root=Path(private_root).resolve()
    require(public_root!=private_root and public_root not in private_root.parents and
            private_root not in public_root.parents,'public/private roots overlap')
    require(public_root.is_dir() and private_root.is_dir(),'owner must provision isolated roots')
    rows=[]
    for case in packet_set['cases']:
        case_id=case['public']['case_id']
        require(len(case_id)==64 and all(c in '0123456789abcdef' for c in case_id),'opaque safe name')
        private=write_new(private_root/(case_id+'.json'),case['private'],artifact_cap)
        public=write_new(public_root/(case_id+'.json'),case['public'],artifact_cap)
        arm=write_new(public_root/(case_id+'.arms.json'),case['arms'],artifact_cap)
        rows.append({'case_id':case_id,'public':public,'private':private,'arms':arm})
    # A partial failure leaves exclusive diagnostic artifacts but no completion.
    result={'cases':rows,'complete':True,'canonical_task_count':1,
            'provider_sandbox_verified':False,'physical_costs':'unmeasured'}
    write_new(private_root/'COMPLETE.json',result,artifact_cap)
    return result
