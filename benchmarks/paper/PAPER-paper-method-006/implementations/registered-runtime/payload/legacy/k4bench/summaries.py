"""Complete-support summary algorithms; explicit unresolved-policy boundary.

Only tiny invented inputs are used in construction controls. Neither historical
policy selection nor native parity follows from these implementations.
"""
import math
from fractions import Fraction
from .protocol import require, integer, fraction, rational, unique, digest


class Work:
    def __init__(self, limits):
        self.limit = integer(limits['max_work'], 'max_work', 1)
        self.points = integer(limits['max_points'], 'max_points', 1)
        self.used = 0

    def charge(self, n):
        self.used += integer(n, 'work')
        require(self.used <= self.limit, 'resource-limit', 'summary work')

    def vector(self, xs):
        require(isinstance(xs, list) and len(xs) <= self.points, 'point-limit', 'vector')
        self.charge(len(xs))
        require(all(type(x) in (int, float) and math.isfinite(x) for x in xs),
                'nonfinite-or-nonnumeric-operand', 'vector')
        return xs


def quantile(xs, p, method, work):
    """Five explicit interpolation modes; none is inferred as paper default."""
    xs = work.vector(xs)
    require(xs and method in {'linear', 'lower', 'higher', 'nearest-even', 'midpoint'},
            'unsupported-percentile-policy', method)
    require(isinstance(p, Fraction) and 0 <= p <= 1, 'percentile', str(p))
    work.charge(len(xs) * max(1, len(xs).bit_length()))
    s = sorted(xs)
    q = p * (len(s) - 1)
    lo, hi = q.numerator // q.denominator, -(-q.numerator // q.denominator)
    if method == 'lower': return s[lo]
    if method == 'higher': return s[hi]
    if method == 'nearest-even': return s[round(q)]
    if method == 'midpoint': return (s[lo] + s[hi]) / 2
    return s[lo] + float(q - lo) * (s[hi] - s[lo])


def drift512(rows, selected_ids, policies, work, *, control_size=None):
    expected = 512 if control_size is None else control_size
    require(len(selected_ids) == len(set(selected_ids)) == expected, 'incomplete-drift-roster', '512 roots')
    by_id = unique(rows)
    require(set(by_id) == set(selected_ids), 'drift-support-mismatch', 'all selected roots')
    out = []
    for key in selected_ids:
        row = by_id[key]
        require(row['boundary'] == 'original-pyKilosort-processed-nine-position-drift'
                and row['batch_samples'] == 65536, 'drift-source-boundary', key)
        require(len(row['depths_um']) == row['complete_batch_count'] > 0,
                'drift-batch-support', key)
        medians = []
        for batch in row['depths_um']:
            require(len(batch) == 9, 'nine-drift-positions-required', key)
            work.vector(batch); work.charge(36)
            medians.append(sorted(batch)[4])
        lo = quantile(medians, Fraction(1,20), policies['percentile_method'], work)
        hi = quantile(medians, Fraction(19,20), policies['percentile_method'], work)
        out.append({'id': key, 'batch_count': len(medians), 'median_depth_um': medians,
                    'q05_um': lo, 'q95_um': hi, 'drift_range_um': hi-lo,
                    'source_role': row['boundary'], 'source_lineage_digest': row['source_lineage_digest']})
    return {'records': out, 'complete_count': len(out), 'regenerated_pyKilosort': False}


def _pick(indices, rule, label):
    require(indices, 'empty-extremum', label)
    require(rule in {'require-unique', 'first-index'}, 'unsupported-tie-policy', label)
    require(rule != 'require-unique' or len(indices) == 1, 'unresolved-extremum-tie', label)
    return indices[0]


def waveform_statistics(rows, selected_ids, policies, work):
    by_id = unique(rows)
    require(set(by_id) == set(selected_ids) and len(selected_ids) == len(set(selected_ids)),
            'waveform-support-mismatch', 'all source units')
    require(policies['T2P_index'] in {'first-decreasing-sample', 'preceding-peak-sample'},
            'unresolved-T2P-convention', 'Sec36 does not establish index convention')
    require(policies['missing_decrease'] == 'required-unscorable', 'missing-decrease-policy', 'no invented endpoint')
    require(policies['distance_geometry'] in {'euclidean-xy', 'vertical-only'},
            'unresolved-distance-geometry', 'MDHM')
    result = []
    for key in selected_ids:
        row = by_id[key]; waves = row['time_by_channel']; xy = row['channel_xy_um']
        require(len(waves) > 1 and len(xy) > 0, 'empty-waveform', key)
        require(len(waves) == row['complete_sample_count'] and len(xy) == row['complete_channel_count'],
                'waveform-window-loss', key)
        for w in waves: require(len(work.vector(w)) == len(xy), 'waveform-shape', key)
        for coord in xy: require(len(work.vector(coord)) == 2, 'channel-geometry', key)
        fs = fraction(row['sample_frequency']);require(fs > 0, 'waveform-clock', key)
        norms = [math.fsum(w[c]*w[c] for w in waves) for c in range(len(xy))]
        work.charge(len(waves)*len(xy))
        require(all(math.isfinite(x) for x in norms), 'numeric-overflow', key)
        best = _pick([c for c,n in enumerate(norms) if n == max(norms)], policies['best_channel_ties'], 'best channel')
        trace = [w[best] for w in waves]; m = min(trace)
        require(m < 0, 'nonnegative-waveform-trough', key)
        trough = _pick([t for t,v in enumerate(trace) if v == m], policies['trough_ties'], 'trough')
        descent = next((t for t in range(trough+1,len(trace)) if trace[t] < trace[t-1]), None)
        if descent is None:
            t2p = None; status = 'required-unscorable-no-decrease'
        else:
            peak = descent if policies['T2P_index'] == 'first-decreasing-sample' else descent-1
            t2p = rational(Fraction(peak-trough)/fs);status = 'defined-under-selected-policy'
        support = [c for c in range(len(xy)) if min(w[c] for w in waves) < m/2]
        work.charge(len(waves)*len(xy))
        distances = []
        for c in support:
            dx,dy = xy[c][0]-xy[best][0],xy[c][1]-xy[best][1]
            distances.append(abs(dy) if policies['distance_geometry']=='vertical-only' else math.hypot(dx,dy))
        result.append({'id':key,'best_channel_index':best,'trough_index':trough,
                       'first_decreasing_sample':descent,'T2P_seconds':t2p,
                       'T2P_status':status,'MDHM_um':max(distances),'half_min_channel_indices':support,
                       'source_lineage_digest':row['source_lineage_digest']})
    return {'units':result,'complete_count':len(result)}


def runtime_mean_sem(rows, methods, case_ids, policies, work, evidence=()):
    require(len(case_ids)==len(set(case_ids))==6,'runtime-six-simulations','Fig4l')
    ddof=policies['variance_ddof'];require(type(ddof) is int and ddof in (0,1),'variance-policy','SEM')
    keyed={(r['method_id'],r['case_id']):r for r in rows}
    require(len(keyed)==len(rows) and set(keyed)=={(m,c) for m in methods for c in case_ids},
            'runtime-support-mismatch','failures cannot be dropped')
    require(len(methods)==len(set(methods)) and methods,'runtime-method-support','complete comparator roster')
    boundary=policies.get('timing_boundary')
    by_evidence={(r['method_id'],r['case_id']):r for r in evidence}
    require(len(by_evidence)==len(evidence),'duplicate-runtime-evidence','method/case')
    reasons=[]
    if not isinstance(boundary,dict) or not boundary:
        reasons.append({'id':'timing-boundary-not-admitted'})
    for key,row in keyed.items():
        work.charge(1)
        ev=by_evidence.get(key)
        if row['runtime_boundary']!=boundary:
            reasons.append({'id':'noncomparable-timing-boundary','method_id':key[0],'case_id':key[1],
                            'observed_boundary':row['runtime_boundary'],'selected_boundary':boundary})
        if row['status']!='complete':
            reasons.append({'id':'incomplete-timing','method_id':key[0],'case_id':key[1]})
        if ev is None or any(row.get(k)!=ev.get(k) for k in
                             ('wall_seconds','runtime_boundary','telemetry_receipt_digest','measurement_id','status')):
            reasons.append({'id':'timing-not-joined-to-authenticated-evidence','method_id':key[0],'case_id':key[1]})
        elif ev['runtime_boundary']!=boundary:
            reasons.append({'id':'telemetry-boundary-not-comparable','method_id':key[0],'case_id':key[1]})
    require(set(by_evidence)<=set(keyed),'unselected-runtime-evidence','method/case')
    if reasons:
        return {'comparison_status':'required-unscorable-noncomparable','methods':[],
                'raw_rows':rows,'raw_authenticated_evidence':list(evidence),'reasons':reasons,
                'selected_timing_boundary':boundary,'normalized_or_rescaled':False}
    out=[]
    for m in methods:
        rs=[keyed[m,c] for c in case_ids]
        require(all(r['status']=='complete' and r['runtime_boundary']==rs[0]['runtime_boundary']
                    and r['telemetry_receipt_digest'] for r in rs), 'runtime-not-comparable',m)
        xs=work.vector([r['wall_seconds'] for r in rs]); require(all(x>=0 for x in xs),'negative-runtime',m)
        mean=math.fsum(xs)/6; var=math.fsum((x-mean)**2 for x in xs)/(6-ddof)
        out.append({'method_id':m,'n':6,'mean_seconds':mean,'SEM_seconds':math.sqrt(var/6),
                    'variance_ddof':ddof,'cases':case_ids,'runtime_boundary':rs[0]['runtime_boundary']})
    return {'comparison_status':'comparable-under-selected-boundary','methods':out,
            'raw_rows':rows,'raw_authenticated_evidence':list(evidence),'reasons':[],
            'selected_timing_boundary':boundary,'normalized_or_rescaled':False}


def score_curves(rows, selected_case_units, work):
    """Exact unit support and fractions; never recompute paper40 from source20."""
    keyed={(r['case_id'],r['unit_id']):r for r in rows}
    require(all(len(us)==len(set(us)) for us in selected_case_units.values()),
            'duplicate-SU-support','case rosters')
    expected={(c,u) for c,units in selected_case_units.items() for u in units}
    require(len(keyed)==len(rows) and set(keyed)==expected,'score-curve-support','complete SU roster')
    scopes={r['numerical_scope'] for r in rows};require(len(scopes)==1,'score-profile-collapse','curves')
    points=[]
    for key in sorted(expected):
        r=keyed[key];require(r['role']=='single-unit-target','MUA-not-evaluation-target',str(key))
        require(r['status']=='defined','undefined-score','no favorable zero filling')
        score=fraction(r['score']);require(score<=1,'invalid-score','upper bound')
        points.append((score,key));work.charge(1)
    work.charge(len(points)*max(1,len(points).bit_length()));points.sort(key=lambda x:(x[0],x[1]))
    return {'numerical_scope':next(iter(scopes)), 'points':[{'case_id':k[0],'unit_id':k[1],
             'score':rational(s),'recovered_independently':s>Fraction(4,5)} for s,k in points],
             'injective_I_assignment_not_inferred_from_independent_curve':True}


def ablation_deltas(rows, ablations, case_ids, work):
    require(len(ablations)==len(set(ablations))==6 and len(case_ids)==len(set(case_ids))==6,
            'ablation-complete-grid','six named ablations and six simulations')
    keyed={(r['ablation'],r['case_id']):r for r in rows}
    require(len(keyed)==len(rows) and set(keyed)=={(a,c) for a in ablations for c in case_ids},
            'ablation-incidence-loss','Fig5 original full grid')
    out=[]
    for key in sorted(keyed):
        r=keyed[key];b=r['baseline'];a=r['modified'];work.charge(1)
        require(b['support_digest']==a['support_digest'] and b['numerical_scope']==a['numerical_scope']
                and b['status']==a['status']=='complete','ablation-pairing',str(key))
        for x in (b,a):
            integer(x['misses'],'misses');integer(x['false_positive_units'],'FP units')
        out.append({'ablation':key[0],'case_id':key[1],'delta_misses':a['misses']-b['misses'],
                    'delta_false_positive_units':a['false_positive_units']-b['false_positive_units'],
                    'support_digest':b['support_digest'],'numerical_scope':b['numerical_scope']})
    return {'rows':out}


def dispatch_summary(request, operands, *, allow_invented=False):
    from .scientific import request_contract
    request_contract(request,allow_invented=allow_invented)
    op=request['operation'];w=Work(request['limits']);p=request['definition']['policies'];s=request['support']
    require(request['support_digest']==digest(s),
        'support-digest','constructor')
    if op=='drift512_processed':result=drift512(operands['drift_records'],s['recording_ids'],p,w)
    elif op=='waveform_statistics':result=waveform_statistics(operands['waveforms'],s['unit_ids'],p,w)
    elif op=='runtime_mean_sem':result=runtime_mean_sem(operands['runtime_rows'],s['method_ids'],s['case_ids'],p,w,operands['runtime_evidence'])
    elif op=='score_curves':result=score_curves(operands['case_score_rows'],s['case_unit_ids'],w)
    elif op=='ablation_deltas':result=ablation_deltas(operands['ablation_rows'],s['ablation_ids'],s['case_ids'],w)
    else:raise ValueError('Not a summary constructor: '+op)
    if op=='score_curves':
        require(result['numerical_scope']==request['numerical_scope'],'curve-scope-substitution',op)
    if op=='ablation_deltas':
        require(all(row['numerical_scope']==request['numerical_scope'] for row in result['rows']),
                'ablation-scope-substitution',op)
    return {'result':result,'work':w.used,'definition':request['definition'],
            'historical_parity':False,'scientific_pass':None}
