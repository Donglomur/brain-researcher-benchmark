"""Prespecified grouped uncertainty; no independence inferred from row counts."""
import random
from . import numerics
from .validation import need, integer, finite, matrix, ident


def percentile(values, q):
    ordered = sorted(values)
    x = (len(ordered) - 1) * q
    lo = int(x); hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (x - lo)


def paired_behavior_bootstrap(truth, candidate, reference, cluster_ids, parameters, *, seed, resamples, alpha):
    """Resample entire operator-bound trials/sessions/blocks, recomputing R2.

    This is conditional on fitted predictions. It does not estimate retraining or
    cross-animal variation when the supplied clusters do not support that claim.
    """
    matrix(truth); matrix(candidate, len(truth), len(truth[0])); matrix(reference, len(truth), len(truth[0]))
    need(len(cluster_ids) == len(truth), 'source-bound cluster identity for every row')
    integer(seed, 0, 2**32-1); integer(resamples, 2, 5000); finite(alpha)
    need(0 < alpha < 1, 'prespecified confidence level')
    groups = {}
    for index, cluster in enumerate(cluster_ids):
        ident(cluster); groups.setdefault(cluster, []).append(index)
    need(len(groups) >= 2, 'at least two exchangeable clusters, no fabricated independent observations')
    rng, draws = random.Random(seed), {name: [] for name in parameters['groups']}
    clusters = sorted(groups)
    for _ in range(resamples):
        indexes = [i for _ in clusters for i in groups[rng.choice(clusters)]]
        y = [truth[i] for i in indexes]
        a = numerics.evaluate('behavior', dict(parameters, truth=y, prediction=[candidate[i] for i in indexes]))['value']['groups']
        b = numerics.evaluate('behavior', dict(parameters, truth=y, prediction=[reference[i] for i in indexes]))['value']['groups']
        for group in draws:
            draws[group].append(a[group] - b[group])
    return {'intervals': {group: [percentile(values, alpha / 2), percentile(values, 1-alpha/2)] for group, values in draws.items()},
            'clusters': len(groups), 'resamples': resamples, 'seed': seed,
            'conditioning': 'fixed fitted predictions; original cluster interpretation required',
            'undefined_resample_policy': 'fail explicit; never drop unfavorable or undefined draws'}


def holm(p_values):
    need(type(p_values) is dict and p_values, 'prespecified family of p-values')
    for key, value in p_values.items():
        ident(key); finite(value); need(0 <= value <= 1, 'probability')
    order = sorted(p_values, key=lambda key: (p_values[key], key))
    adjusted, maximum = {}, 0
    for index, key in enumerate(order):
        maximum = max(maximum, min(1.0, (len(order)-index)*p_values[key]))
        adjusted[key] = maximum
    return adjusted


AGGREGATE_TARGETS = {
    **{f'factorial:{factor}:historical':('factorial_ablations','historical_paired_t',factor)
       for factor in ('readout','interpolation','direction')},
    **{f'factorial:{factor}:cluster':('factorial_ablations','prospective_cluster_gain',factor)
       for factor in ('readout','interpolation','direction')},
    'threshold:historical_SE':('threshold_crossings','historical_mean_SE',None),
}
HISTORICAL_FAMILY = sorted(k for k in AGGREGATE_TARGETS if k.endswith(':historical'))


def validate_aggregate_plan(plan):
    """Closed target-to-estimator and paired-family joins before any execution.

    Holm here is the benchmark's three-contrast confirmatory family. It does not
    relabel the paper's historical unadjusted tests as multiplicity-corrected.
    Prospective cluster intervals are intervals, not manufactured p-values.
    """
    from .validation import exact,sha
    from .bindings import validate_identity,dimensions
    from .catalog import ablation_cells
    records=plan['aggregate_uncertainty'];need(type(records) is list,'aggregate uncertainty matrix')
    ids=[r['id'] for r in records]
    need(len(ids)==len(set(ids)) and set(ids)==set(AGGREGATE_TARGETS),
         'exact seven source-defined uncertainty targets, no label substitution')
    by_key={}
    for case in plan['cases']:
        for item in case['output_identities']:
            need(item['key'] not in by_key,'one producer for each scientific output')
            by_key[item['key']]=(case,item)
    keys=set(ablation_cells())
    for record in records:
        exact(record,('id','kind','module','pairs','cluster_draws','alpha','policy_sha256',
                     'multiplicity_family','family_members','unit_aggregation','quantile_policy'),
              'aggregate uncertainty')
        module,kind,factor=AGGREGATE_TARGETS[record['id']]
        need((record['module'],record['kind'])==(module,kind),'required ID binds its real module and estimator')
        sha(record['policy_sha256']);finite(record['alpha']);need(0<record['alpha']<1,'fixed confidence level')
        need(record['unit_aggregation'] in ('source_bound_mean','unresolved'),'explicit original unit aggregation')
        need(type(record['pairs']) is list and record['pairs'],'paired complete source support')
        for pair in record['pairs']:
            exact(pair,('left','right','unit_id','cluster_id'),'paired source outcomes')
            ident(pair['unit_id']);ident(pair['cluster_id'])
            need(pair['left'] in by_key and pair['right'] in by_key,'no unjoined scalar substitution')
            for key in ('left','right'):
                case,item=by_key[pair[key]]
                need(case['module']==module,'pair producer belongs to declared scientific module')
                validate_identity(case,item)
        if module=='factorial_ablations':
            slot={'readout':1,'interpolation':2,'direction':3}[factor]
            high,low={'readout':('direct','linear'),'interpolation':('on','off'),
                      'direction':('acausal','causal')}[factor]
            expected=set()
            for key in keys:
                parts=key.split(':')
                if parts[slot]==high:
                    other=list(parts);other[slot]=low;other=':'.join(other)
                    if other in keys:expected.add((key,other))
            need({(pair['left'],pair['right']) for pair in record['pairs']}==expected
                 and len(record['pairs'])==len(expected),'complete original matched factorial contrast')
        else:
            seen=[]
            for pair in record['pairs']:
                left,li=by_key[pair['left']];right,ri=by_key[pair['right']]
                need(left['factors']['spike_type']=='threshold' and right['factors']['spike_type']=='sorted',
                     'original threshold-minus-sorted comparison')
                need(li['dimensions']==ri['dimensions'] and len(li['dimensions'])==1,'matched threshold variable')
                seen+=li['dimensions']
            need(len(seen)==13 and set(seen)==set(dimensions('MC_Cycle')),'all13 threshold paired variables')
        if kind=='historical_paired_t':
            need(record['multiplicity_family']=='factorial:confirmatory_holm'
                 and record['family_members']==HISTORICAL_FAMILY,'mandatory complete three-contrast confirmatory family')
        else:
            need(record['multiplicity_family'] is None and record['family_members']==[],
                 'SE and cluster intervals cannot stand in for p-value family members')
        if kind=='prospective_cluster_gain':
            need(record['quantile_policy'] in ('linear_interpolation','unresolved'), 'explicit interval convention')
            need(type(record['cluster_draws']) is list and len(record['cluster_draws'])>=2,'fixed cluster draws')
        else:
            need(record['quantile_policy']=='not_applicable' and record['cluster_draws']==[],
                 'historical paired tests and SE do not use interval draws')
    # Historical and prospective versions must describe the same pair/unit target.
    by_id={row['id']:row for row in records}
    for factor in ('readout','interpolation','direction'):
        historical=by_id[f'factorial:{factor}:historical'];cluster=by_id[f'factorial:{factor}:cluster']
        need(historical['pairs']==cluster['pairs'] and
             historical['unit_aggregation']==cluster['unit_aggregation'],
             'historical/prospective comparisons share exact pairs, units and clusters')


def validate_interval_policy(case,recipe,req,policy,sample_ids):
    """Same target/metric admission used by actual bootstrap execution."""
    from .validation import digest,exact
    need(digest(policy)==req['policy_sha256'],'original uncertainty policy commitment')
    exact(policy,('sample_ids','cluster_ids','draws','alpha','target','selector','metric_parameters','quantile_policy'),'protected bootstrap policy')
    rule=next(r for r in recipe['outputs'] if r['key']==req['target'])
    identity=next(i for i in case['output_identities'] if i['key']==req['target'])
    need(rule['kind']==identity['kind']=='behavior' and case['mode'].startswith('behavior'), 'interval applies to the same behavior prediction output')
    need(policy['selector']==rule['value_selector']==identity['selector'] and
         policy['metric_parameters']==rule['parameters'], 'uncertainty uses exact assessed output selector and metric parameters')
    need(policy['quantile_policy']=='linear_interpolation','original quantile policy unresolved or unsupported')
    need(policy['sample_ids']==sample_ids and len(policy['cluster_ids'])==len(sample_ids),'complete original uncertainty source-row join')
    need(req['kind'] in ('historical_absolute_trial_bootstrap','prospective_paired_gain'), 'supported uncertainty kind')
    target={'historical_absolute_trial_bootstrap':'absolute_R2','prospective_paired_gain':'paired_gain'}[req['kind']]
    need(policy['target']==target,'historical absolute interval distinct from prospective gain')
    if req['kind']=='historical_absolute_trial_bootstrap':need(len(policy['draws'])==1000 and policy['alpha']==.05,'published1000trial bootstrap95percent intervals')
    finite(policy['alpha']);need(0<policy['alpha']<1,'prespecified confidence level')
    need(type(policy['draws']) is list and len(policy['draws'])>=2,'at least two complete draws')
    return target


def case_uncertainty(case,packet,predicted,reference,recipe,trusted,clock):
    from .scoring import protected_prediction_join
    from .validation import digest,exact
    from .bindings import validate_case,validate_recipe
    from .new_numerics import evaluate as extension
    requirements=case['uncertainty_requirements'];answers=[]
    if not requirements:return answers
    validate_case(case);validate_recipe(case,recipe)
    need(digest(recipe)==case['metric_recipe_sha256'],'same assessment recipe commitment')
    truth,left=protected_prediction_join(packet,predicted);_,right=protected_prediction_join(packet,reference)
    sample_ids=[row['sample_id'] for stream in packet.streams('target') for row in packet.rows(stream)]
    limit=packet.admission.value['limits']['numerical_bytes']
    for req in requirements:
        clock()
        try:
            policy=trusted['uncertainty'][req['id']]
            target=validate_interval_policy(case,recipe,req,policy,sample_ids)
            clusters={}
            for i,name in enumerate(policy['cluster_ids']):ident(name);clusters.setdefault(name,[]).append(i)
            need(len(clusters)>=2,'original exchangeable clusters required')
            draws=[];undefined=[]
            for ordinal,draw in enumerate(policy['draws']):
                clock();need(type(draw) is list and len(draw)==len(clusters) and all(k in clusters for k in draw),'complete supplied original cluster draw')
                indexes=[i for key in draw for i in clusters[key]]
                try:
                    values=[]
                    for source in (left,right) if target=='paired_gain' else (left,):
                        value=numerics.evaluate('behavior',dict(policy['metric_parameters'],truth=[truth[i] for i in indexes],prediction=[source[i] for i in indexes]),maximum_bytes=limit)['value']
                        for component in policy['selector']:value=value[component]
                        finite(value);values.append(value)
                    draws.append(values[0]-values[1] if target=='paired_gain' else values[0])
                except ValueError as error:
                    draws.append(None);undefined.append({'draw':ordinal,'reason':str(error)})
            interval=extension('draw_interval',{'draws':draws,'alpha':policy['alpha']},maximum_bytes=limit)['value']
            answers.append({'id':req['id'],'target':req['target'],'kind':req['kind'],'status':interval['status'],'interval':interval,'draw_values':draws,'draw_membership':policy['draws'],'undefined':undefined,'policy_sha256':req['policy_sha256']})
        except Exception as error:
            answers.append({'id':req['id'],'target':req['target'],'kind':req['kind'],'status':'unscorable','reason':type(error).__name__+': '+str(error),'policy_sha256':req['policy_sha256']})
    return answers


def aggregate_assessments(plan,assessed,*,maximum_bytes,clock):
    from .new_numerics import evaluate as extension
    validate_aggregate_plan(plan)
    values={r['key']:r for case in assessed for r in case['outputs']};results=[]
    for specification in plan['aggregate_uncertainty']:
        clock()
        try:
            left=[];right=[];units=[];clusters=[]
            for pair in specification['pairs']:
                entries=[values[pair[key]] for key in ('left','right')]
                need(all(v['status']=='numerically_assessed' for v in entries),'all required paired outputs numerically defined')
                scalars=[v['selected_candidate'] for v in entries]
                for value in scalars:finite(value)
                left.append(scalars[0]);right.append(scalars[1]);units.append(pair['unit_id']);clusters.append(pair['cluster_id'])
            need(specification['unit_aggregation']=='source_bound_mean','original paired-unit aggregation unresolved')
            grouped_units={}
            for a,b,unit,cluster in zip(left,right,units,clusters):
                item=grouped_units.setdefault(unit,{'left':[],'right':[],'cluster':cluster})
                need(item['cluster']==cluster,'one original dependence cluster per declared test unit');item['left'].append(a);item['right'].append(b)
            left=[sum(u['left'])/len(u['left']) for u in grouped_units.values()];right=[sum(u['right'])/len(u['right']) for u in grouped_units.values()]
            units=list(grouped_units);clusters=[u['cluster'] for u in grouped_units.values()]
            if specification['kind'].startswith('historical'):
                value=extension('paired_test',{'left':left,'right':right,'unit_ids':units},maximum_bytes=maximum_bytes)['value']
                status='complete' if specification['kind']=='historical_mean_SE' or value['undefined_reason'] is None else 'undefined'
            else:
                need(specification['quantile_policy']=='linear_interpolation','original quantile policy unresolved')
                grouped={}
                for difference,cluster in zip([a-b for a,b in zip(left,right)],clusters):grouped.setdefault(cluster,[]).append(difference)
                need(len(grouped)>=2,'dependence-aware clusters need original support')
                draws=[]
                for draw in specification['cluster_draws']:
                    clock();need(len(draw)==len(grouped) and all(k in grouped for k in draw),'precommitted complete cluster draw')
                    items=[value for key in draw for value in grouped[key]];draws.append(sum(items)/len(items))
                value=extension('draw_interval',{'draws':draws,'alpha':specification['alpha']},maximum_bytes=maximum_bytes)['value'];value['draw_values']=draws;value['draw_membership']=specification['cluster_draws'];status=value['status']
            results.append({'id':specification['id'],'kind':specification['kind'],'module':specification['module'],'status':status,'value':value,'policy_sha256':specification['policy_sha256'],'raw_pair_count':len(specification['pairs']),'source_bound_unit_count':len(units)})
        except Exception as error:
            results.append({'id':specification['id'],'kind':specification['kind'],'module':specification['module'],'status':'unscorable','reason':type(error).__name__+': '+str(error),'policy_sha256':specification['policy_sha256']})
    by_id={r['id']:r for r in results};families={}
    for spec in plan['aggregate_uncertainty']:
        family=spec['multiplicity_family']
        if family is None:continue
        members=spec['family_members']
        if family in families:need(families[family]['members']==members,'one prespecified family membership')
        else:
            defined=all(by_id[k]['status']=='complete' and by_id[k].get('value',{}).get('two_sided_p') is not None for k in members)
            families[family]={'members':members,'status':'complete' if defined else 'unscorable','holm':holm({k:by_id[k]['value']['two_sided_p'] for k in members}) if defined else None}
    return {'requirements':results,'multiplicity':families,'complete':all(r['status']=='complete' for r in results) and all(f['status']=='complete' for f in families.values()),'historical_dependence_warning':'Published paired-variable test is reproduced as specified; variables/seeds are not independent animals.'}
