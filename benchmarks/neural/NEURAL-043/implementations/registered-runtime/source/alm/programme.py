"""Concrete scientific composition; deployment entry stays inactive until admission."""
from .contracts import require,metadata_contract,digest,readiness,Refusal
from .nwb import load_recording
from .qc import validate_recording,inventory_dispositions
from .features import prediction_rows
from .splits import prediction_folds
from .prediction import reference_predictions
from .tuning import tuning_maps
from .perturbation import fit_responses,join_tuning
from .inference import partial_effect,held_mouse_improvement,crossfit_matched,distance_sensitivity,uncertainty,response_class_contrast
from .controls import tuning_rotation

def load_population(root,manifest,mappings,budget):
    rows=metadata_contract(manifest)
    records=[];qc=[]
    for row in rows:
        if row['disposition']=='exclude':
            continue
        record=load_recording(root,row,mappings[row['asset_id']],budget)
        require(bool(record['stimuli'])==(row['scope']=='behavior_and_stimulation'),
                'loaded stimulus scope disagrees with full source disposition')
        qc.append(validate_recording(record));records.append(record)
    return records,{'population':inventory_dispositions(manifest,records),'qc':qc}

def construct_prediction(records,protocol,track):
    from .protocol import prediction
    prediction(protocol)
    require(track in ('held_block','held_mouse'),'prediction track')
    representation='session_rois' if track=='held_block' else 'anatomical_bins'
    if track=='held_mouse':
        require(protocol['atlas_alignment_evidence'],'new-mouse identity/alignment missing')
    rows=[];excluded=[]
    for record in records:
        r,e=prediction_rows(record,protocol,representation)
        rows.extend(r)
        excluded.extend([{'mouse':record['mouse'],'session':record['session'],**x} for x in e])
    folds=list(prediction_folds(rows,track))
    predictions,dispositions=reference_predictions(rows,folds,protocol['logistic_c'])
    return {'rows':rows,'folds':folds,'reference_predictions':predictions,
            'trial_exclusions':excluded,'fold_dispositions':dispositions,'track':track}

def construct_perturbation(records,protocol):
    from .protocol import perturbation
    perturbation(protocol)
    pairs=[];all_responses=[];dispositions=[];designs=[]
    for record in records:
        if not record['stimuli']:
            dispositions.append({'mouse':record['mouse'],'session':record['session'],'status':'no_stimulation'})
            continue
        key=record['mouse']+'/'+record['session']
        split=protocol['tuning_splits'][key]
        tuning,tuning_dispositions=tuning_maps(record,split['allowed'],split['held'],
                          protocol['tuning_window'],protocol['minimum_frames'])
        response,audit=fit_responses(record,protocol)
        joined,excluded=join_tuning(record,response,tuning,protocol['minimum_distance'])
        pairs.extend(joined);all_responses.extend(response);designs.extend(audit)
        dispositions.append({'mouse':record['mouse'],'session':record['session'],
                             'tuning':tuning_dispositions,'pairs':excluded})
    outputs={}
    for control in ('lagged','lead_null'):
        rows=[r for r in pairs if r['control']==control]
        if not rows:
            outputs[control]={'status':'not_estimable','reason':'no fully joined pairs'}
            continue
        effect=partial_effect(rows)
        improvement=held_mouse_improvement(rows,protocol['response_alpha'])
        matched=crossfit_matched(rows,protocol['distance_edges'],protocol['caliper_scale'])
        values=[x['effect'] for x in effect if x['effect'] is not None]
        outputs[control]={'effect':effect,'improvement':improvement,'matched':matched,
                          'site_class_association':response_class_contrast(rows),
                          'uncertainty':uncertainty(values) if len(values)>=2 else None,
                          'distance_sensitivity':distance_sensitivity(rows),
                          'response_selected_site_sensitivity':partial_effect([
                              r for r in rows if r['classification_basis']!='independent_pretest']),
                          'estimand':'conditional_tuning_response_association'}
        rotated,coverage=tuning_rotation(rows)
        outputs[control]['tuning_rotation_null']={'effect':partial_effect(rotated),'coverage':coverage,
                                                  'randomization_pvalue_claimed':False}
    sham=[r for r in all_responses if r['condition']=='true_sham']
    outputs['true_sham']={'status':'available_requires_design_matched_interpretation' if sham else 'unavailable',
                          'n_response_rows':len(sham),'substitute_nonresponding_site':False}
    return {'outputs':outputs,'rows':pairs,'all_response_rows':all_responses,
            'dispositions':dispositions,'designs':designs,
            'disposition_digest':digest(dispositions),
            'unsupported_claims':['randomized_response_class_contrast','monosynaptic_strength']}

def run(task,*args,**kwargs):
    require(task in readiness()['tasks'],'task')
    raise Refusal('Inactive source construction: genuine mapping, deployment, resource owner and scientific admission absent')

def score(*args,**kwargs):
    raise Refusal('Inactive source construction: no admitted private packets or qualified scorer')
