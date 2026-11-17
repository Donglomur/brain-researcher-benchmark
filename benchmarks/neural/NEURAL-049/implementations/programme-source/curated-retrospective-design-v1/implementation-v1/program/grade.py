"""Complete target-last scoring; no fitted-output callback or empirical claim at import."""
from pathlib import Path
import hashlib
import math
from core import need, canonical, capture, parse, encoded, publish, finite
from contracts import PEOPLE, ENDPOINTS, FAMILIES, cells
from authority import grading_selection
from admission import admit
from array_io import load
from reference_adapter import primitive, host_descriptor


def person_score(targets, predictions):
    """Event-pooled within-person OOF SSE/SST; empty/constant support stays undefined."""
    need(len(targets) == len(predictions), 'complete paired score rows')
    y = [finite(x) for x in targets]; p = [finite(x) for x in predictions]
    if not y: return {'status':'undefined_empty_person','n':0,'sse':0.,'sst':0.,'r2':None}
    mean = math.fsum(y)/len(y)
    sse = math.fsum((a-b)**2 for a,b in zip(y,p)); sst = math.fsum((a-mean)**2 for a in y)
    need(math.isfinite(sse) and math.isfinite(sst), 'finite full SSE/SST')
    return {'status':'defined' if sst > 0 else 'undefined_constant_person','n':len(y),'sse':sse,'sst':sst,
            'r2':1.-sse/sst if sst > 0 else None}


def macro(rows):
    need(set(rows) == set(PEOPLE), 'all twelve people; no surviving subset')
    values = [rows[p]['r2'] for p in PEOPLE]
    return {'status':'defined' if all(x is not None for x in values) else 'undefined_complete_endpoint',
            'value':math.fsum(values)/12 if all(x is not None for x in values) else None,
            'people':rows,'weighting':'equal_people_of_event_pooled_within_person_OOF_R2'}


def contrasts(selected):
    # Named model identifiers are stable, and all are scored on identical rows.
    core = [('F_NC','F_C'),('I_NC','I_C')]
    core += [('I_'+v,'F_'+v) for v in ('C','N','NC')]
    core += [('ref_'+f+'_NC','ref_'+f+'_C') for f in FAMILIES]
    core += [('ref_strong_NC','ref_strong_C'),('F_NC','ref_strong_NC'),('I_NC','ref_strong_NC')]
    result = {'core':core}
    if 'T1' in selected:
        result['T1'] = [('F_NC_T1','F_NC'),('I_NC_T1','I_NC'),
                        ('F_NC_T1','ref_strong_NC'),('I_NC_T1','ref_strong_NC')]
    if 'D' in selected:
        result['D'] = [('F_NC','F_NC_D'),('I_NC','I_NC_D')]
        result['D'] += [('ref_'+f+'_NC','ref_'+f+'_NC_D') for f in (*FAMILIES,'strong')]
    return result


def bootstrap_draw(b, k):
    """Selected counter/rejection rule, independent of language RNG implementations."""
    threshold = (1<<64)//12*12
    for rejection in range(1024):
        message = ['NEURAL049.curated-retrospective.v1.person-bootstrap.angle',b,k,rejection]
        value = int.from_bytes(hashlib.sha256(encoded(message)).digest()[:8],'big')
        if value < threshold: return value % 12
    raise ValueError('counter bootstrap rejection qualification failed')


def effect_rows(scores, selected):
    result = {}
    for family,pairs in contrasts(selected).items():
        rows = []
        for left,right in pairs:
            l,r = scores[left],scores[right]
            defined = l['value'] is not None and r['value'] is not None
            diffs = [l['people'][p]['r2']-r['people'][p]['r2'] for p in PEOPLE] if defined else None
            rows.append({'left':left,'right':right,'status':'defined' if defined else 'undefined_full_support',
                         'value':math.fsum(diffs)/12 if defined else None,'person_differences':diffs})
        result[family] = rows
    return result


def intervals(effects, budget, limits):
    """Three separately named simultaneous families, not one joint/author-variance claim."""
    result = {}
    for family,rows in effects.items():
        if any(x['value'] is None for x in rows):
            result[family] = {'status':'undefined_complete_family','bands':None}; continue
        limits.reserve('allocation_bytes',10000*40+len(rows)*12*32)
        limits.reserve('work',10000*12*len(rows)); deviations = []
        for b in range(10000):
            budget.tick(); draws = [bootstrap_draw(b,k) for k in range(12)]
            deviations.append(max(abs(math.fsum(row['person_differences'][k] for k in draws)/12-row['value']) for row in rows))
        deviations.sort(); radius = deviations[9499]
        result[family] = {'status':'approximate_simultaneous_band','replicates':10000,'order_index_zero_based':9499,
            'radius':radius,'bands':[[row['value']-radius,row['value']+radius] for row in rows],
            'resampling_unit':'whole_person','same_counter_draws_across_families':True,
            'not_joint_across_families':True,'not_author_policy_variance':True,'not_population_random_sample_guarantee':True}
    return result


def verify_selection_values(a, admitted, targets, budget):
    """Recompute the retained inner SSE algebra after target access is permitted.

    This reads only already captured predictions, never refits or changes a
    selection. All 25 configurations and both independent banks are checked.
    """
    from selection_worker import choose
    from contracts import CONFIGS
    records = admitted['records']['references']; limits = admitted['limits']
    for (impl,endpoint,view,person,held),value in admitted['selections'].items():
        sums = {c:[] for c in CONFIGS}; counts = {c:0 for c in CONFIGS}
        for row in value['consumer_rows']:
            budget.tick(); d = row['day']; ordinal = row['configuration']
            actual = records[row['prediction_operation']]
            desc = host_descriptor(primitive(actual['joined']['tree']['projected'],impl),actual['produced'])
            pred = load(desc,[a['roots']['reference']],limits); y = targets[(person,d,endpoint)]
            need(pred.shape == y.shape, 'complete inner labels and predictions')
            limits.reserve('work',len(y)*4)
            sse = math.fsum((float(t)-float(p))**2 for t,p in zip(y,pred))
            need(math.isfinite(sse), 'finite independent selection SSE')
            sums[ordinal].append(sse); counts[ordinal] += len(y)
        scores = {c:{'sse':math.fsum(sums[c]),'n':counts[c]} for c in CONFIGS}
        need(all(x['n'] > 0 for x in scores.values()), 'complete nonempty total inner selection')
        selected,strongest = choose(scores)
        need(value['scores'] == scores and value['selected'] == selected and value['strongest'] == strongest,
             'actual train-only complete inner selection values; no post-outcome reselection')


def evaluate(a, admitted, budget):
    """Only called after every public panel/source/process/shape/finite check has closed."""
    need(admitted['public_output_admission_complete'] is True and admitted['protected_target_bodies_read'] is False,
         'complete independent admission before first private label body')
    limits = admitted['limits']; table = admitted['table']; targets = {}
    for row in admitted['packet']['manifest']['days']:
        for endpoint in ENDPOINTS:
            d = row['labels'][endpoint]; path = canonical(a['roots']['packet'])/d['path']
            need(canonical(a['roots']['targets']) in path.parents, 'exact protected label subtree')
            desc = {'path':str(path),'pin':{k:d[k] for k in ('bytes','sha256')},'shape':d['shape'],'dtype':d['dtype']}
            values = load(desc,[a['roots']['targets']],limits)
            need(values.dtype.str == '<f8' and values.shape == (len(row['ids']),), 'complete protected target rows')
            targets[(row['person'],row['day'],endpoint)] = values
    admitted['protected_target_bodies_read'] = True
    verify_selection_values(a,admitted,targets,budget)
    lookup = {}
    for key,row in admitted['reference_rows'].items():
        kind,endpoint,view,person,held,query,configuration,family,axis = key
        if kind == 'reference_outer_predict': lookup[(endpoint,view,person,held,family)] = row
    scores = {}; points = {}
    for column,endpoint in enumerate(ENDPOINTS):
        model_people = {}
        for person in PEOPLE:
            days = [x['day'] for x in table[person]]; target = []
            rows_n = sum(len(x['ids']) for x in table[person])
            model_n = len(cells(a['modules']))+4*(4 if 'D' in a['modules'] else 3)+1
            limits.reserve('allocation_bytes',rows_n*(model_n+5)*160)
            models = {c['id']:[] for c in cells(a['modules'])}
            views = ['C','N','NC']+(['NC_D'] if 'D' in a['modules'] else [])
            models.update({'ref_'+f+'_'+v:[] for v in views for f in (*FAMILIES,'strong')}); models['train_mean'] = []
            for day in days:
                y = targets[(person,day,endpoint)]; target.extend(float(x) for x in y)
                training = [targets[(person,d,endpoint)] for d in days if d != day]
                n = sum(len(x) for x in training); need(n > 0, 'complete outer training support, no mean fallback')
                mean = math.fsum(float(z) for x in training for z in x)/n
                mean = min(90.,max(-90.,mean)) if endpoint == 'angle' else max(0.,mean)
                models['train_mean'].extend([mean]*len(y))
                for cell in cells(a['modules']):
                    row = admitted['candidate_rows'][(cell['id'],person,day)]
                    pred = load(row['array'],[a['roots']['output']],limits)
                    need(len(row['ids']) == len(y), 'same complete scored candidate support')
                    models[cell['id']].extend(float(x) for x in pred[:,column])
                for view in views:
                    selected = admitted['selections'][('r1',endpoint,view,person,day)]['strongest']
                    for family in FAMILIES:
                        row = lookup[(endpoint,view,person,day,family)]
                        pred = load(row['projected'],[a['roots']['reference']],limits)
                        values = [float(x) for x in pred]; need(len(values) == len(y), 'same complete reference support')
                        models['ref_'+family+'_'+view].extend(values)
                        if family == selected: models['ref_strong_'+view].extend(values)
            for name,pred in models.items(): model_people.setdefault(name,{})[person] = person_score(target,pred)
        scores[endpoint] = {name:macro(rows) for name,rows in model_people.items()}
        points[endpoint] = effect_rows(scores[endpoint],a['modules'])
    return {'scores':scores,'contrasts':points,'angle_intervals':intervals(points['angle'],budget,limits),
            'secondary_endpoint_intervals':None,'reference_anchor':'R1 after independent R2 agreement',
            'qualified_neural_contribution':None,'causal_or_continuous_forecast_claim':False,
            'policy_realizations':1,'actual_census':admitted['producer']['census']}


def execute(a, captured, declaration, budget):
    # The late declaration path is operator-only before it is opened.
    need(canonical(a['roots']['operator']) in canonical(declaration['path']).parents, 'protected late authority namespace')
    q = grading_selection(a,declaration,budget)
    d = q['observation']; path = canonical(a['roots']['observation'])/'OBSERVATION.json'
    need(canonical(d['path']) == path, 'fixed original observation before capture')
    raw,_ = capture(path,d['pin'],a['resources']['producer_bytes'],budget,readonly=True); observed = parse(raw)
    need(observed['schema'] == 'neural049_observation_v1' and observed['status'] == 'complete'
         and observed['source'] == captured['pin'] and observed['authority'] == captured['authority_pin']
         and observed['original_origin'] == budget.origin, 'same externally completed original collection')
    admitted = admit(a,captured,observed['producer'],budget)
    result = evaluate(a,admitted,budget)
    report = {'schema':'neural049_protected_score_v1','status':'complete','source':captured['pin'],
              'authority':captured['authority_pin'],'late_authority':declaration,'observation':d,
              'original_origin':budget.origin,'results':result,'costs_before_publication':budget.record(),
              'numeric_costs':admitted['limits'].record(),'own_outer_exit_not_self_certified':True}
    desc = publish(q['output'],encoded(report),budget,readonly=True); budget.tick()
    return {'status':'scored','score':{'path':q['output'],'pin':desc},'source':captured['pin']}
