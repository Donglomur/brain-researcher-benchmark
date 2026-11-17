"""Protected evidence/scoring source, never executed during BUILD.
Candidate capture must precede protected target opening in a real isolated owner.
Structural admission is separate from the unexecuted numerical consumer.
"""
import math
from .design import POLICIES,CELL_TYPES
from .lifecycle import require_native_producers
from .support import SUPPORT_EVIDENCE_FIELDS

PRODUCT_IDS=('original_support','prestate_predictions','outcome_sensitivity_predictions','analysis_report')

def admit_support_claim(body):
    if set(body)!={'catalogue','secondary','interpretation'}:raise ValueError('two population support evidence and interpretation required')
    for population in ('catalogue','secondary'):
        table=body[population]
        if table.get('population')!=population:raise ValueError('population binding')
        if not isinstance(table.get('condition_support'),list) or not table['condition_support']:raise ValueError('quantitative condition support required')
        for row in table['condition_support']:
            for key in ('experiments','events'):
                value=row.get(key)
                if value is not None and (type(value)is not int or value<0):raise ValueError('count/null domain')
            if not isinstance(row.get('status'),str):raise ValueError('availability disposition')
        if not {'overlap','coverage','complete_quantitative_support','event_dispositions','disposition_counts','event_denominators','event_denominator_summary'}<=set(table):raise ValueError('support evidence not a canned identifiability claim')
    if not isinstance(body['interpretation'],dict):raise ValueError('structured interpretation')
    return body

def admit_predictions(body,expected_case_ids,query_binding):
    if body.get('query_binding')!=query_binding:raise ValueError('captured query lineage')
    records=body.get('predictions');expected=set(expected_case_ids)
    if not isinstance(records,list) or len(records)!=len(expected) or {r['id'] for r in records}!=expected:raise ValueError('every planned supported case exactly once')
    for row in records:
        if set(row)!={'id','JOINT','NUISANCE'}:raise ValueError('paired model outputs')
        for arm in ('JOINT','NUISANCE'):
            if type(row[arm]) not in (int,float) or not math.isfinite(row[arm]):raise ValueError('finite prediction')
    return {arm:{r['id']:r[arm] for r in records} for arm in ('JOINT','NUISANCE')}

def _support_evidence_consumer(candidate,protected):
    """Exact quantitative evidence, not a reward for repeating 'nonidentifiable'."""
    admit_support_claim(candidate);reports={}
    for population in ('catalogue','secondary'):
        got=candidate[population];truth=protected[population]
        complete=truth['complete_quantitative_support']
        fields=SUPPORT_EVIDENCE_FIELDS
        comparisons={key:got.get(key)==truth.get(key) for key in fields}
        reports[population]={'available':complete,'field_agreement':comparisons,
            'quantitative_success':True if complete and all(comparisons.values()) else False if complete else None,
            'status':'complete_support_assessed' if complete else 'unavailable_protected_membership_or_projection'}
    interpretation=candidate['interpretation']
    required={'Familiar_vs_Novel':'distinct_from_FIRST_vs_REPEAT','exact_lifetime':'unavailable_without_authenticated_counter',
              'poststimulus_outcome':'separate_conditioned_sensitivity','causal_effect':'not_identified_by_matching_alone'}
    interpretation_ok=all(interpretation.get(k)==v for k,v in required.items())
    return {'populations':reports,'interpretation_consistent':interpretation_ok,
            'original_support_success':all(r['quantitative_success'] is True for r in reports.values()) and interpretation_ok,
            'causal_estimate':None}

def _evaluate_policy(policy,candidate,targets,reference,query_binding,core):
    rows=targets['cases'];expected=[r['id'] for r in rows]
    predictions=admit_predictions(candidate,expected,query_binding)
    new=[r for r in rows if r['subset']=='new_image'];sd=targets['training_target_sd']
    missing=[r for r in targets['mouse_support'] if r['status']!='complete_supported']
    full=targets['complete_primary_support'] and not missing and sd is not None and core.finite(sd) and sd>0
    output={'policy':policy,'matched_denominator':expected,'mouse_support':targets['mouse_support'],
            'complete_primary_support':full,'primary_prediction_error':None,'primary_fixed_reference_gain':None,
            'references':{},'celltypes':{},'observational_contrast':'FIRST-minus-REPEAT','causal_effect':False,
            'selection_source':'validation_only_frozen_before_query','unsupported_primary_reason':None if full else 'missing_intended_support_or_scale'}
    for subset in ('new_image','already_familiar_image_control','unknown_first_image_status'):
        for celltype in CELL_TYPES:
            cc=[r for r in rows if r['subset']==subset and r['cre_line']==celltype]
            output['celltypes'][subset+'/'+celltype]={'status':'not_evaluated_incomplete_primary' if cc else 'no_support','observed':None,'predicted':None,'supported_case_count':len(cc)}
    if not full:return output
    # Candidate cannot nominate or weaken the evaluator-owned comparator.
    for name in ('hierarchical_mean','hist_gradient_boosting'):
        ref=reference['predictions'][name]
        for arm in ('JOINT','NUISANCE'):
            if set(ref[arm])!=set(expected):raise ValueError('reference denominator differs')
        output['references'][name]={arm:core.macro_error(ref[arm],new,sd) for arm in ('JOINT','NUISANCE')}
    output['primary_prediction_error']=core.macro_error(predictions['JOINT'],new,sd)
    selected=reference['frozen_selection']['primary_nuisance']
    if selected not in output['references']:raise ValueError('frozen reference')
    output['primary_fixed_reference_gain']=output['references'][selected]['NUISANCE']-output['primary_prediction_error']
    output['candidate_nuisance_error_descriptive']=core.macro_error(predictions['NUISANCE'],new,sd)
    for subset in ('new_image','already_familiar_image_control','unknown_first_image_status'):
        rr=[r for r in rows if r['subset']==subset]
        for celltype in CELL_TYPES:
            cc=[r for r in rr if r['cre_line']==celltype];key=subset+'/'+celltype
            if not cc:output['celltypes'][key]={'status':'no_support','observed':None,'predicted':None};continue
            observed=core.contrasts({r['id']:r['target'] for r in cc},cc);predicted=core.contrasts(predictions['JOINT'],cc)
            output['celltypes'][key]={'status':'observed_matched_support','mice':sorted(observed),'observed_per_mouse':observed,'predicted_per_mouse':predicted,
                'observed_equal_mouse':core.mean(observed.values()),'predicted_equal_mouse':core.mean(predicted.values()),
                'contrast_absolute_error_equal_mouse':core.mean(abs(predicted[m]-observed[m]) for m in observed),'preferred_sign':None}
    output['confirmatory_interval']=None;output['superiority_claim']=None
    return output

def evaluate(*args,**kwargs):require_native_producers()
