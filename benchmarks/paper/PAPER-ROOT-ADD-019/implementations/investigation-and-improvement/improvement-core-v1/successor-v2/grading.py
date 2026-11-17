"""Complete-panel validation followed by independently computed protected loss."""
import math
import sys
from common import STRATA, VARIANTS, ACCESS, need, finite, pin, require_pin
from study import cohort_queries, panel_key, compile_plan

def _sum(values):
    try:return finite(math.fsum(values),'finite grader sum')
    except (OverflowError,ValueError) as error:
        from common import Refusal
        raise Refusal('finite grader sum') from error

def _product(a,b):
    value=finite(a*b,'finite grader product')
    need(value!=0 or a==0 or b==0,'grader nonzero product underflow')
    return value

def _ratio(a,b):
    need(b!=0,'grader positive divisor')
    value=finite(a/b,'finite normalized loss or mean')
    need(value!=0 or a==0,'grader nonzero quotient underflow')
    return value

def validate_complete_predictions(plan, panels, fitted, sources):
    need(type(panels) is dict and set(panels) == set(plan['panels']), 'every full candidate/reference panel')
    need(type(fitted) is dict and set(fitted) == set(plan['final_bundle_ids']), 'every final fitted bundle')
    need(type(sources) is dict and set(sources) == {*ACCESS, 'operator'}, 'frozen source identity for all producers')
    for source in sources.values():
        require_pin(source)
    for key, expected in plan['panels'].items():
        artifact = panels[key]
        need(type(artifact) is dict and set(artifact) == {'panel_key', 'model_id', 'model_record_pin',
                                                       'source_pin', 'predictions'}, 'prediction artifact schema')
        model_id = expected['bundle_fit_id']; model = fitted[model_id]
        need(type(model) is dict and set(model) == {'model_id', 'panel_key', 'source_pin', 'training_animals',
                                                   'state_pin', 'selection_pin', 'feature_schema_pin'}, 'model lineage schema')
        need(model['model_id'] == artifact['model_id'] == model_id and
             model['panel_key'] == artifact['panel_key'] == key and
             model['source_pin'] == artifact['source_pin'] == sources[expected['actor']] and
             model['training_animals'] == expected['training_animals'], 'exact source/fold/model lineage')
        for name in ('state_pin', 'selection_pin', 'feature_schema_pin'):
            require_pin(model[name])
        need(model['feature_schema_pin'] == plan['feature_schema_pin'], 'same predeclared feature schema')
        need(artifact['model_record_pin'] == pin(model), 'prediction binds exact fitted state record')
        values = artifact['predictions']
        need(type(values) is dict and set(values) == set(expected['query_ids']), 'all original query predictions')
        for value in values.values():
            finite(value, 'finite predicted natural-log seconds')
    return {'complete_panels': len(panels), 'fitted_bundles': len(fitted),
            'artifact_index_pin': pin({k: pin(v) for k, v in panels.items()}),
            'source_index_pin': pin(sources), 'labels_accessed': False,
            'semantic_method_or_runtime_custody_certified': False}

def group_variance(study, cohort, training_animals, stratum, labels):
    rows = [q for q in cohort_queries(study, cohort) if q['animal'] in training_animals and q['stratum'] == stratum]
    sessions = {a: sorted({q['session'] for q in rows if q['animal'] == a}) for a in training_animals}
    need(all(sessions.values()), 'nonempty full training support')
    counts = {(a,s): sum(q['animal'] == a and q['session'] == s for q in rows)
              for a in training_animals for s in sessions[a]}
    pairs = []
    for q in rows:
        seconds = finite(labels[q['id']], 'finite private positive seconds'); need(seconds > 0, 'positive time')
        weight = 1.0 / (len(training_animals)*len(sessions[q['animal']])*counts[q['animal'],q['session']])
        pairs.append((weight, math.log(seconds)))
    need(abs(_sum(w for w,_ in pairs)-1.0)<=64*sys.float_info.epsilon,
         'fixed hierarchical weights sum to one; no renormalization')
    # An exactly constant target is undefined even if rounded weights sum just
    # off one; mirror the accepted semantic constant rule independently.
    constant=all(y==pairs[0][1] for _,y in pairs)
    mean=pairs[0][1] if constant else _sum(_product(w,y) for w,y in pairs)
    variance=0.0 if constant else _sum(_product(w,_product(finite(y-mean),finite(y-mean))) for w,y in pairs)
    need(math.isfinite(variance) and variance > 0, 'positive fitting-partition population target variance')
    return {'mean': mean, 'variance': variance, 'rows': len(rows), 'animals': len(training_animals)}

def loss_for_animal(queries, predictions, labels, variances):
    result = {}
    for stratum in STRATA:
        selected = [q for q in queries if q['stratum'] == stratum]
        need(selected, 'all four held strata')
        sessions = {}
        for q in selected:
            truth = finite(labels[q['id']]); need(truth > 0, 'strict positive private target')
            prediction = finite(predictions[q['id']])
            difference=finite(prediction-math.log(truth),'finite log-time error')
            error = _product(difference,difference)
            sessions.setdefault(q['session'], []).append(error)
        session_losses = {s: _ratio(_sum(v),len(v)) for s,v in sorted(sessions.items())}
        raw = _ratio(_sum(session_losses.values()),len(session_losses))
        denominator = finite(variances[stratum]); need(denominator > 0, 'training variance denominator')
        result[stratum] = {'squared_log_error': raw, 'normalized_loss': _ratio(raw,denominator),
                           'training_variance': denominator, 'queries': len(selected),
                           'sessions': len(sessions), 'session_losses': session_losses}
    return result

def grade(plan, study, panels, fitted, sources, private_labels, *, programme_artifacts):
    """Protected source composition; every mandatory gate precedes labels.

    Component dictionaries are untrusted metadata until these source checks.
    Their authentic production/custody still requires independent qualification.
    """
    null_ids=sorted({s['realization'] for s in plan['panels'].values()}-{'observed'})
    need(plan==compile_plan(study,null_ids), 'exact complete plan from admitted study')
    admission = validate_complete_predictions(plan, panels, fitted, sources)
    need(type(programme_artifacts) is dict and set(programme_artifacts)=={
        'native_policy','native_roots','native_panels','reference_fit_records','reference_selections',
        'diagnostics','ed_dispositions','null_reports','candidate_method_admission','reference_final_states'},
        'complete programme artifacts before private labels')
    import completion, native_compare
    native=native_compare.compare(programme_artifacts['native_policy'],programme_artifacts['native_roots'],
                                  programme_artifacts['native_panels'])
    fits=completion.validate_reference_fit_records(plan,study,programme_artifacts['reference_fit_records'],
        programme_artifacts['reference_selections'],programme_artifacts['reference_final_states'],fitted)
    diagnostics=completion.validate_diagnostics(plan,programme_artifacts['diagnostics'])
    prerequisites=completion.validate_programme_prerequisites(plan,native,programme_artifacts['ed_dispositions'],
        programme_artifacts['null_reports'],fits,diagnostics,programme_artifacts['candidate_method_admission'])
    result=_score_admitted_panels(plan,study,panels,private_labels,admission)
    result['programme_prerequisites']=prerequisites
    return result

def _score_admitted_panels(plan, study, panels, private_labels, admission):
    """Private arithmetic component; not a standalone protected grading entry."""
    # No label read occurs before the entire candidate/reference panel admission.
    need(type(private_labels) is dict and set(private_labels) == {q['id'] for q in study['queries']},
         'complete private label keys')
    aliases={}
    for q in study['queries']:
        value=finite(private_labels[q['id']]);need(value>0,'positive protected target')
        key=q['target_key']
        need(key not in aliases or aliases[key]==value, 'same protected target alias truth')
        aliases[key]=value
    losses = {}
    variances = {}
    for key, spec in plan['panels'].items():
        group = (spec['cohort'], spec['animal'])
        if group not in variances:
            variances[group] = {k: group_variance(study, spec['cohort'], spec['training_animals'], k, private_labels)['variance']
                                for k in STRATA}
        queries = cohort_queries(study, spec['cohort'], spec['animal'])
        losses[key] = loss_for_animal(queries, panels[key]['predictions'], private_labels, variances[group])
    gains = {}
    for key, spec in plan['panels'].items():
        if spec['actor'] == 'operator':
            continue
        reference_key = panel_key('operator', spec['cohort'], spec['animal'], spec['variant'], spec['realization'])
        by_stratum = {k: finite(losses[reference_key][k]['normalized_loss']-losses[key][k]['normalized_loss'],
                               'finite gain') for k in STRATA}
        learning = _ratio(_sum((by_stratum['offer_CPIn'],by_stratum['reward_SideOff'])),2)
        movement = _ratio(_sum((by_stratum['side_on'],by_stratum['opt_out'])),2)
        gains[key] = {'stratum_gains': by_stratum, 'learning_gain': learning,
                      'movement_gain': movement, 'animal_gain': _ratio(_sum((learning,movement)),2)}
    summaries = {}
    for realization in sorted({s['realization'] for s in plan['panels'].values()}):
        for access in ACCESS:
            for cohort in ('full', 'paired'):
                for variant in VARIANTS:
                    selected = {spec['animal']: gains[key]['animal_gain'] for key,spec in plan['panels'].items()
                                if spec['realization']==realization and spec['actor']==access and
                                spec['cohort']==cohort and spec['variant']==variant}
                    need(selected, 'complete summary group')
                    summaries['|'.join((realization,access,cohort,variant))] = {
                        'animal_values': selected, 'equal_animal_gain': _ratio(_sum(selected.values()),len(selected)),
                        'is_primary': cohort=='full' and variant=='F'}
    return {'schema': 'ach_complete_crossfitted_loss_v1', 'admission': admission,
            'losses': losses, 'gains': gains, 'summaries': summaries,
            'whole_paper_reproduced': False, 'scientific_qualified': False,
            'remaining_complete_program_gates': ['native_comparison', 'mandatory_diagnostics',
                'null_policy_and_results', 'ED_dispositions', 'actual_runtime_custody', 'reference_competence']}

def conditional_resampling(animal_values, frozen_table):
    need(type(animal_values) is dict and animal_values, 'complete fixed animal effects')
    animals = sorted(animal_values); values = [finite(animal_values[a]) for a in animals]
    need(type(frozen_table) is dict and set(frozen_table) == {'animals','indices','selection_pin'}, 'frozen resampling table')
    need(frozen_table['animals'] == animals, 'same fixed animal ordering'); require_pin(frozen_table['selection_pin'])
    samples = frozen_table['indices']; need(type(samples) is list and samples, 'predeclared nonempty table')
    out = []
    for row in samples:
        need(type(row) is list and len(row) == len(values) and
             all(type(i) is int and 0 <= i < len(values) for i in row), 'complete resampling draw')
        out.append(_ratio(_sum(values[i] for i in row),len(values)))
    return {'means': out, 'table_pin': pin(frozen_table), 'refitted': False,
            'interpretation': 'conditional fixed-prediction stability; not a pipeline confidence interval'}

def paired_sign_flips(animal_values):
    need(type(animal_values) is dict and len(animal_values) == 4, 'four authentic simultaneous effects')
    values = [finite(animal_values[a]) for a in sorted(animal_values)]
    return {'means': [_ratio(_sum((1 if mask & (1<<i) else -1)*v for i,v in enumerate(values)),4)
                      for mask in range(16)], 'patterns': 16, 'inferential_p_value': None,
            'interpretation': 'diagnostic only; exchangeability and symmetry not established'}
