"""Protected complete-support scoring and independent reference contrasts."""
import bisect
import math
from . import catalog
from . import numerics
from .neural_state import rate_metric_payload
from .validation import exact, need, vector, matrix, ident, digest, bound_bytes, decode, finite


def load_predictions(root, descriptor, case, maximum):
    raw = bound_bytes(root, descriptor, maximum)
    need(raw.endswith(b'\n'), 'complete output newline')
    by_stream = {}
    for line in raw.splitlines():
        value = decode(line)
        exact(value, ('case', 'stream', 'index', 'sample_id', 'value'), 'captured output row')
        need(value['case'] == case['id'], 'case/output identity')
        ident(value['stream']); ident(value['sample_id'])
        stream = by_stream.setdefault(value['stream'], [])
        need(type(value['index']) is int and value['index'] == len(stream), 'no output reordering/gaps/duplicate indices')
        need(value['sample_id'] not in {r['sample_id'] for r in stream}, 'no duplicate output sample IDs')
        stream.append(value)
    return by_stream


def protected_prediction_join(packet, predicted):
    """Only operator scoring may read targets. Query truth never enters transport."""
    query = packet.streams('query')
    training_keys = {'training:' + s['id'] for s in packet.streams('train')} if packet.index['output_schema']['training_rates_required'] else set()
    need(set(predicted) == {s['id'] for s in query} | training_keys, 'complete exact train/query output streams')
    for stream in packet.streams('train') if training_keys else []:
        rows = predicted['training:' + stream['id']]
        need(len(rows) == stream['rows'], 'all NLB training-rate rows')
        for index, actual in enumerate(packet.rows(stream)):
            need(rows[index]['sample_id'] == actual['sample_id'], 'training rate source identity')
            vector(rows[index]['value'], packet.index['output_schema']['width'])
    truth, prediction = [], []
    for stream in query:
        target = next(s for s in packet.streams('target') if s['trial'] == stream['trial'])
        rows = predicted[stream['id']]
        need(len(rows) == target['rows'], 'complete target support, no candidate masking')
        for index, actual in enumerate(packet.rows(target)):
            answer = rows[index]
            need(answer['sample_id'] == actual['sample_id'], 'original sample ID join')
            truth.append(vector(actual['truth'], target['width']))
            complete = vector(answer['value'], packet.index['output_schema']['width'])
            prediction.append([complete[column] for column in packet.index['output_schema']['target_columns']])
    return truth, prediction


def distribution(values, edges):
    """Explicit source-bound bin edges; no fitted test histogram edges."""
    vector(values); vector(edges)
    need(len(edges) >= 2 and all(a < b for a, b in zip(edges, edges[1:])), 'strict histogram edges')
    counts = [0] * (len(edges) - 1)
    under = over = 0
    for value in values:
        if value < edges[0]:
            under += 1
        elif value > edges[-1]:
            over += 1
        else:
            counts[min(len(counts) - 1, bisect.bisect_right(edges, value) - 1)] += 1
    return {'edges': edges, 'counts': counts, 'underflow': under, 'overflow': over, 'observations': len(values)}


def _assess_case(case, packet, predicted, reference, recipe, trusted_payloads):
    """Metric recipes and private payloads are operator-frozen, never candidate fields.

    A result key may map to one declared statistic. Exact original support/rosters
    are checked by the whole plan and separately reviewed recipe commitments.
    """
    need(digest(recipe) == case['metric_recipe_sha256'], 'precommitted metric recipe')
    exact(recipe, ('module', 'outputs', 'policy_evidence_sha256','experiment_sha256','uncertainty_requirements'), 'metric recipe')
    need(recipe['module'] == case['module'] and type(recipe['outputs']) is list and
         [r['key'] for r in recipe['outputs']] == case['outputs'], 'complete exact output recipe')
    shared = None
    if case['mode'] != 'analysis':
        ct, cp = protected_prediction_join(packet, predicted)
        rt, rp = protected_prediction_join(packet, reference)
        need(ct == rt, 'paired protected target support')
        shared = (ct, cp, rp)
    else:
        need(set(predicted) == {'analysis'} and set(reference) == {'analysis'}, 'analysis output container')
        need([r['sample_id'] for r in predicted['analysis']] == case['outputs'] and
             [r['sample_id'] for r in reference['analysis']] == case['outputs'], 'all original analysis outputs')
    results = []
    for position, rule in enumerate(recipe['outputs']):
        exact(rule, ('key', 'kind', 'payload_id', 'parameters', 'value_selector'), 'metric output rule')
        need(rule['kind'] in catalog.KINDS[case['module']], 'metric belongs to full-paper module')
        key, kind = rule['key'], rule['kind']
        parameters = rule['parameters']
        need(type(parameters) is dict and type(rule['value_selector']) is list, 'frozen metric parameters/selector')
        if kind == 'documentary':
            results.append({'key': key, 'kind': kind, 'submitted': True,
                            'status': 'requires_independent_scientific_review',
                            'candidate_sha256': digest(predicted['analysis'][position]['value']),
                            'reference_sha256': digest(reference['analysis'][position]['value'])})
            continue
        if kind == 'cost':
            observed = trusted_payloads[rule['payload_id']]
            exact(observed, ('candidate_attempts', 'reference_attempts', 'sha256'), 'external all-attempt costs')
            need(digest({'candidate_attempts': observed['candidate_attempts'], 'reference_attempts': observed['reference_attempts']}) == observed['sha256'], 'independently captured cost ledger')
            payload, ref_payload = {'attempts': observed['candidate_attempts']}, {'attempts': observed['reference_attempts']}
        elif kind=='cycle_geometry':
            from .geometry import payload as geometry_payload
            common=trusted_payloads[rule['payload_id']]
            need(digest(common['payload'])==common['sha256'],'protected Cycle policy commitment')
            payload=geometry_payload(predicted['analysis'][position]['value'],common['payload'])
            ref_payload=geometry_payload(reference['analysis'][position]['value'],common['payload'])
        elif shared is not None:
            truth, candidate, ref = shared
            if case['mode'] == 'neural_acausal' and kind in ('psth', 'behavior'):
                need(rule['payload_id'] in trusted_payloads, 'original PSTH/readout binding required')
                payload = rate_metric_payload(packet, predicted, kind, trusted_payloads[rule['payload_id']], parameters)
                ref_payload = rate_metric_payload(packet, reference, kind, trusted_payloads[rule['payload_id']], parameters)
            elif kind == 'behavior':
                payload = dict(parameters, truth=truth, prediction=candidate)
                ref_payload = dict(parameters, truth=truth, prediction=ref)
            elif kind == 'neural_state':
                # Published NLB floor applies identically to candidate/reference.
                payload = dict(parameters, spikes=truth, rates=[[max(.1,x) for x in row] for row in candidate])
                ref_payload = dict(parameters, spikes=truth, rates=[[max(.1,x) for x in row] for row in ref])
            else:
                raise ValueError('prediction mode metric must operate on protected predictions')
        else:
            need(rule['payload_id'] in trusted_payloads, 'independent protected analysis payload')
            common = trusted_payloads[rule['payload_id']]
            exact(common, ('field', 'payload', 'sha256'), 'trusted analysis recipe input')
            need(digest(common['payload']) == common['sha256'], 'trusted analysis input commitment')
            need(type(common['payload']) is dict and type(common['field']) is str, 'one declared prediction field')
            payload = dict(common['payload'], **parameters)
            ref_payload = dict(common['payload'], **parameters)
            need(common['field'] not in payload, 'candidate cannot overwrite protected metric inputs')
            payload[common['field']] = predicted['analysis'][position]['value']
            ref_payload[common['field']] = reference['analysis'][position]['value']
        if kind == 'distribution':
            candidate_value, reference_value = distribution(**payload), distribution(**ref_payload)
            agreement = 'explicit_edge_arithmetic_not_dual_bank'
        else:
            limit = packet.admission.value['limits']['numerical_bytes']
            from .new_numerics import evaluate as new_evaluate
            evaluate=new_evaluate if kind=='cycle_geometry' else numerics.evaluate
            a = evaluate(kind, payload, maximum_bytes=limit)
            b = evaluate(kind, ref_payload, maximum_bytes=limit)
            candidate_value, reference_value = a['value'], b['value']
            agreement = a['bank_agreement'] and b['bank_agreement']
        selected, selected_ref = candidate_value, reference_value
        for component in rule['value_selector']:
            selected, selected_ref = selected[component], selected_ref[component]
        if type(selected) in (int, float) and type(selected_ref) in (int, float):
            finite(selected); finite(selected_ref)
            gain = selected - selected_ref
        else:
            gain = None
        diagnostics = None
        if kind == 'behavior':
            diagnostics = {'candidate': behavior_diagnostics(payload), 'reference': behavior_diagnostics(ref_payload),
                           'arithmetic': 'explicit secondary MAE/correlation; not dual-bank native equivalence'}
        results.append({'key': key, 'kind': kind, 'secondary_diagnostics': diagnostics, 'candidate': candidate_value,
                        'reference': reference_value, 'selected_candidate':selected,'selected_reference':selected_ref,'signed_gain': gain,
                        'absolute_deviation': None if gain is None else abs(gain),
                        'bank_agreement': agreement, 'status': 'numerically_assessed',
                        'historical_equivalence': 'requires_admitted_original_policy_evidence'})
    return {'case': case['id'], 'module': case['module'], 'outputs': results,
            'scope_complete_for_case': True, 'scientifically_qualified': False}


def behavior_diagnostics(payload):
    """Published trace MAE/Pearson ingredients; no circular Pearson invented."""
    truth, prediction = payload['truth'], payload['prediction']
    matrix(truth); matrix(prediction, rows=len(truth), columns=len(truth[0]))
    rows = []
    for column in range(len(truth[0])):
        y = [r[column] for r in truth]; p = [r[column] for r in prediction]
        if column in payload['circular_columns']:
            period = payload['phase_period']
            errors = [abs((a-b+period/2)%period-period/2) for a,b in zip(y,p)]
            correlation, reason = None, 'Circular correlation requires independently bound native policy'
        else:
            errors = [abs(a-b) for a,b in zip(y,p)]
            my, mp = sum(y)/len(y), sum(p)/len(p)
            sy = sum((v-my)**2 for v in y); sp = sum((v-mp)**2 for v in p)
            correlation = sum((a-my)*(b-mp) for a,b in zip(y,p))/math.sqrt(sy*sp) if sy>0 and sp>0 else None
            reason = None if correlation is not None else 'Undefined constant truth/prediction variance'
        rows.append({'mean_absolute_error':sum(errors)/len(errors), 'pearson':correlation, 'undefined_reason':reason})
    return {'per_dimension':rows, 'original_units_preserved':True}


def _failure_status(error):
    message=str(error).lower()
    if 'disagreement' in message:return 'bank_disagreement'
    if any(term in message for term in ('undefined','variance','denominator','zero spike','constant','zero standard')):return 'undefined_metric'
    if isinstance(error,(ValueError,KeyError,IndexError,TypeError)):return 'invalid_assessment'
    return 'assessment_failure'


def assessment_denominators(truth, *, neural):
    """Two linear passes per dimension; arithmetic and undefined SST retained."""
    rows=len(truth)
    means=[sum(row[j] for row in truth)/rows for j in range(len(truth[0]))]
    sst=[sum((row[j]-mean)**2 for row in truth) for j,mean in enumerate(means)]
    return {'rows':rows,'per_dimension_SST':sst,
            'total_spike_count':sum(sum(row) for row in truth) if neural else None}


def assess_case(case,packet,predicted,reference,recipe,trusted_payloads,*,clock=lambda:None,persist=lambda row:None,artifact_commitments=None):
    """Durable per-output outcomes; no undefined score is a zero or dropped row."""
    from .bindings import validate_recipe
    from .uncertainty import case_uncertainty
    import traceback
    commitments={'input_index':case.get('input_index_sha256'),'recipe':case.get('metric_recipe_sha256'),'source_recipe':case.get('source_recipe_sha256'),'artifacts':artifact_commitments}
    denominators=None;outputs=[];initial=None
    try:
        clock();validate_recipe(case,recipe)
        need(digest(recipe)==case['metric_recipe_sha256'],'whole selected recipe before output decomposition')
        if case['mode']!='analysis':
            truth,_=protected_prediction_join(packet,predicted)
            denominators=assessment_denominators(truth, neural=case['mode']=='neural_acausal')
    except Exception as error:initial=error
    for rule in recipe.get('outputs',[]) if initial is None else [{'key':k,'kind':None} for k in case['outputs']]:
        try:
            clock()
            if initial is not None:raise initial
            subrecipe=dict(recipe,outputs=[rule],uncertainty_requirements=[])
            subcase=dict(case,outputs=[rule['key']],metric_recipe_sha256=digest(subrecipe))
            subpred,subref=predicted,reference
            if case['mode']=='analysis':
                subpred={'analysis':[r for r in predicted['analysis'] if r['sample_id']==rule['key']]}
                subref={'analysis':[r for r in reference['analysis'] if r['sample_id']==rule['key']]}
            outcome=_assess_case(subcase,packet,subpred,subref,subrecipe,trusted_payloads)['outputs'][0]
        except Exception as error:
            outcome={'key':rule['key'],'kind':rule['kind'],'status':_failure_status(error),'reason':type(error).__name__+': '+str(error),'original_traceback_prefix':traceback.format_exc()[:8192],'absolute_deviation':None,'signed_gain':None}
        outcome['commitments']=commitments;outcome['denominators']=denominators
        persist({'case':case['id'],'output':outcome});outputs.append(outcome)
    try:uncertainty=case_uncertainty(case,packet,predicted,reference,recipe,trusted_payloads,clock) if initial is None else []
    except Exception as error:uncertainty=[{'id':r['id'],'target':r['target'],'status':'unscorable','reason':str(error)} for r in case['uncertainty_requirements']]
    existing={r['id'] for r in uncertainty}
    uncertainty += [{'id':r['id'],'target':r['target'],'status':'unscorable','reason':'required assessment input unavailable'} for r in case['uncertainty_requirements'] if r['id'] not in existing]
    persist({'case':case['id'],'uncertainty':uncertainty})
    return {'case':case['id'],'module':case['module'],'outputs':outputs,'uncertainty':uncertainty,
            'scope_complete_for_case':all(r['status']=='numerically_assessed' for r in outputs) and all(r['status']=='complete' for r in uncertainty),'scientifically_qualified':False}
