"""Voltron V3 native-frame event scoring; pure standard-library component.

No signal acquisition, clock inference, ROI/reference construction, candidate
execution or process isolation. The trusted caller qualifies native dtypes and
freezes complete inputs before using this independently specified successor.
"""
from bisect import bisect_right
from fractions import Fraction
import hashlib
import json
import math
from statistics import median

TASK = 'NEURAL-DISC-20261114-VOLTRON-SPIKES'
PROFILE = 'voltron-six-subject-native-frame-events/v1'
ROLES = ('candidate', 'optical_mad', 'optical_matched_filter', 'metadata_rate')
TOLERANCE = Fraction(1, 200)
MAX_FRAMES = 10000000
MAX_EVENTS = 1000000
MAX_CORES = 200000
MAX_TIME = 2**63


class ContractError(ValueError): pass
class SubmissionError(ValueError): pass
class ReferenceError(ValueError): pass


def need(ok, message, error=ContractError):
    if not ok: raise error(message)


def fields(value, names, message, error=ContractError):
    need(type(value) is dict and set(value) == set(names), message, error)


def name(value, error=ContractError):
    need(type(value) is str and 1 <= len(value) <= 96 and
         all(c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in value),
         'opaque identifier', error)
    return value


def digest(value, error=ContractError):
    need(type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value), 'SHA-256 identity', error)
    return value


def exact_time(value, error=ContractError):
    """Exact represented scalar, never Decimal(str(float)) or a nominal clock.

    A qualified adapter can supply an integer ratio from any supported dtype.
    No generic float coercion or NumPy dtype assumption occurs here.
    """
    if type(value) is int:
        n, d = value, 1
    elif type(value) is float:
        need(math.isfinite(value), 'finite represented time', error)
        n, d = value.as_integer_ratio()
    elif type(value) is Fraction:
        n, d = value.numerator, value.denominator
    elif type(value) in (list, tuple) and len(value) == 2:
        n, d = value
    else: raise error('literal int, finite float or exact integer-ratio time')
    need(type(n) is int and type(d) is int and d > 0 and
         n.bit_length() <= 4096 and d.bit_length() <= 4096, 'bounded exact rational time', error)
    result = Fraction(n, d)
    need(abs(result) <= MAX_TIME, 'time magnitude format ceiling', error)
    return result


def ratio(value): return [value.numerator, value.denominator]


def identity(public):
    """Identity of the source JSON contract; rationals use [numerator,denominator]."""
    try:
        raw = json.dumps(public, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    except (ValueError, TypeError) as error:
        raise ContractError('public contract must be finite JSON; encode exact ratios as lists') from error
    return hashlib.sha256(raw).hexdigest()


def _intervals(value, start, end, error):
    need(type(value) is list and len(value) <= MAX_CORES, 'bounded validity intervals', error)
    spans = []
    for item in value:
        need(type(item) is list and len(item) == 2, 'half-open interval pair', error)
        left, right = (exact_time(x, error) for x in item)
        need(start <= left < right <= end and (not spans or spans[-1][1] <= left), 'sorted nonoverlapping bounded intervals', error)
        if spans and spans[-1][1] == left: spans[-1] = (spans[-1][0], right)
        else: spans.append((left, right))
    return tuple(spans)


def _contains(t, spans):
    i = bisect_right(spans, (t, Fraction(MAX_TIME + 1))) - 1
    return i >= 0 and spans[i][0] <= t < spans[i][1]


def _covered(left, right, spans):
    i = bisect_right(spans, (left, Fraction(MAX_TIME + 1))) - 1
    return i >= 0 and spans[i][0] <= left < right <= spans[i][1]


def _times(value, start, end, error, limit):
    need(type(value) is list and len(value) <= limit, 'bounded complete time vector', error)
    captured = tuple(exact_time(v, error) for v in value)
    need(all(start <= t < end for t in captured) and all(a < b for a,b in zip(captured,captured[1:])),
         'strictly increasing unique times within movie', error)
    return captured


def public_contract(value):
    fields(value, ('schema','task_id','profile','release_manifest_sha256','cells','expected_subjects','movies'), 'public fields')
    need(value['schema']=='voltron-native-frame-public/v1' and value['task_id']==TASK and value['profile']==PROFILE, 'native profile')
    digest(value['release_manifest_sha256'])
    need(type(value['expected_subjects']) is int and value['expected_subjects']==6, 'six-subject V3 scope')
    cells=value['cells'];need(type(cells) is list and len(cells)==12, 'complete twelve-cell roster')
    cells=tuple(name(c) for c in cells);need(len(set(cells))==12,'unique cells')
    movies=value['movies'];need(type(movies) is dict and len(movies)==34,'complete 34-movie V3 roster')
    for mid in movies:name(mid)
    captured={};cores={};seen=set();frames_total=0
    for mid,row in sorted(movies.items()):
        name(mid)
        fields(row,('cell_id','fold_id','nominal_optical_rate_hz','start_time','end_time','frame_times',
                    'input_disposition','optical_valid_intervals','cores'),'movie fields')
        need(row['cell_id'] in cells,'rostered cell');seen.add(row['cell_id']);name(row['fold_id'])
        nominal=row['nominal_optical_rate_hz']
        need(type(nominal) is int and nominal in (400,1000),'nominal stratum label, not a clock')
        start,end=exact_time(row['start_time']),exact_time(row['end_time']);need(start<end,'positive movie duration')
        times=_times(row['frame_times'],start,end,ContractError,MAX_FRAMES)
        need(bool(times),'native frame population retained even when optical extraction fails')
        frames_total+=len(times);need(frames_total<=MAX_FRAMES,'whole-frame format ceiling; never truncate')
        disposition=row['input_disposition'];need(disposition in ('ready','optical_extraction_failed'),'optical disposition')
        optical=_intervals(row['optical_valid_intervals'],start,end,ContractError)
        need(bool(optical)==(disposition=='ready'),'failed extraction retains empty optical support')
        need(type(row['cores']) is list and 1<=len(row['cores'])<=MAX_CORES,'complete frame cores')
        at=0;movie_cores=[]
        for core in row['cores']:
            fields(core,('core_id','start_frame','end_frame'),'frame-core fields')
            cid=name(core['core_id']);a,b=core['start_frame'],core['end_frame']
            need(type(a) is int and type(b) is int and a==at and a<b<=len(times) and cid not in cores,
                 'unique contiguous complete frame cores')
            cores[cid]=(mid,a,b);movie_cores.append((cid,a,b));at=b
        need(at==len(times) and len(cores)<=MAX_CORES,'no omitted frame tail or core population')
        captured[mid]={'cell_id':row['cell_id'],'fold_id':row['fold_id'],'nominal_optical_rate_hz':nominal,
            'start':start,'end':end,'frame_times':times,'cores':tuple(movie_cores),
            'input_disposition':disposition,'optical_valid_intervals':optical}
    need(seen==set(cells),'no omitted cell')
    return {'identity':identity(value),'cells':cells,'movies':captured,'cores':cores,'frame_count':frames_total}


def capture_predictions(value, contract):
    fields(value,('schema','task_id','public_sha256','roles'),'prediction fields',SubmissionError)
    need(value['schema']=='voltron-native-frame-predictions/v1' and value['task_id']==TASK and
         value['public_sha256']==contract['identity'],'prediction task/source identity',SubmissionError)
    need(type(value['roles']) is dict and set(value['roles'])==set(ROLES),'all four matched roles',SubmissionError)
    captured={};commitments={}
    for role in ROLES:
        row=value['roles'][role];fields(row,('program_sha256','calibration_sha256','cores'),'role fields',SubmissionError)
        commitments[role]={k:digest(row[k],SubmissionError) for k in ('program_sha256','calibration_sha256')}
        need(type(row['cores']) is dict and set(row['cores'])==set(contract['cores']),'complete identical core coverage',SubmissionError)
        by_movie={};total=0
        for mid,movie in contract['movies'].items():
            whole=[]
            for cid,left,right in movie['cores']:
                indices=row['cores'][cid]
                need(type(indices) is list and len(indices)<=MAX_EVENTS,'bounded frame-event list',SubmissionError)
                previous=left-1
                for index in indices:
                    need(type(index) is int and left<=index<right and previous<index,'one sorted unique core-owned event per frame',SubmissionError)
                    whole.append(index);previous=index
                total+=len(indices);need(total<=MAX_EVENTS,'whole-role event ceiling',SubmissionError)
            by_movie[mid]=tuple(whole)
        captured[role]=by_movie
    return captured,commitments


def capture_reference(value,contract):
    fields(value,('schema','task_id','public_sha256','census_evidence_sha256','mapping_evidence_sha256',
                  'cell_to_subject','outer_folds','movies'),'reference fields',ReferenceError)
    need(value['schema']=='voltron-native-frame-reference/v1' and value['task_id']==TASK and
         value['public_sha256']==contract['identity'],'reference task/source identity',ReferenceError)
    digest(value['census_evidence_sha256'],ReferenceError);digest(value['mapping_evidence_sha256'],ReferenceError)
    mapping=value['cell_to_subject'];need(type(mapping) is dict and set(mapping)==set(contract['cells']),'complete biological map',ReferenceError)
    mapping={c:name(a,ReferenceError) for c,a in mapping.items()};subjects=set(mapping.values())
    need(len(subjects)==6,'exact six biological subjects',ReferenceError)
    folds=value['outer_folds'];need(type(folds) is dict and len(folds)==6,'six complete outer folds',ReferenceError)
    queries=set();captured_folds={}
    for fid,row in folds.items():
        name(fid,ReferenceError);fields(row,('query_subject','train_cells'),'fold fields',ReferenceError)
        a=name(row['query_subject'],ReferenceError);need(a in subjects and a not in queries,'one fold per subject',ReferenceError);queries.add(a)
        train=row['train_cells'];need(type(train) is list and all(type(c) is str for c in train) and
            len(set(train))==len(train) and set(train)=={c for c in mapping if mapping[c]!=a},'complete subject-separated training roster',ReferenceError)
        captured_folds[fid]=a
    need(queries==subjects,'complete subject fold population',ReferenceError)
    need(type(value['movies']) is dict and set(value['movies'])==set(contract['movies']),'complete reference movie coverage',ReferenceError)
    captured={};total=0
    for mid,public in contract['movies'].items():
        need(captured_folds.get(public['fold_id'])==mapping[public['cell_id']],'every movie follows its subject fold',ReferenceError)
        row=value['movies'][mid];fields(row,('valid_intervals','spikes'),'reference movie fields',ReferenceError)
        spans=_intervals(row['valid_intervals'],public['start'],public['end'],ReferenceError)
        need(all(_covered(a,b,public['optical_valid_intervals']) for a,b in spans),'private support within public optical validity',ReferenceError)
        spikes=_times(row['spikes'],public['start'],public['end'],ReferenceError,MAX_EVENTS)
        total+=len(spikes);need(total<=MAX_EVENTS and all(_contains(t,spans) for t in spikes),'all reference events inside declared scored support',ReferenceError)
        captured[mid]={'valid_intervals':spans,'spikes':spikes}
    return captured,mapping


def _match_sorted(predictions,truth):
    i=j=0;latencies=[]
    while i<len(predictions) and j<len(truth):
        delta=predictions[i]-truth[j]
        if delta < -TOLERANCE:i+=1
        elif delta > TOLERANCE:j+=1
        else:latencies.append(delta);i+=1;j+=1
    tp=len(latencies)
    return tp,len(predictions)-tp,len(truth)-tp,tuple(latencies)


def match_events(predictions,truth):
    """Earliest-compatible maximum cardinality; latency is not optimized.

    For earliest compatible p,t, an optimal ordered matching can exchange its
    first pair(s) for p,t without losing a match. If p is too early, no later
    truth can match it (and symmetrically for t). Repeating gives the optimum.
    Public helper validates all inputs; the scorer uses captured exact tuples.
    """
    def sequence(xs):
        need(type(xs) in (list,tuple) and len(xs)<=MAX_FRAMES,'bounded matching vector')
        ys=tuple(exact_time(t) for t in xs)
        need(all(a<b for a,b in zip(ys,ys[1:])),'strictly sorted unique matching events')
        return ys
    return _match_sorted(sequence(predictions),sequence(truth))


def _match_intervals(predicted,truth,spans):
    p=q=tp=fp=fn=valid_predictions=0;latencies=[]
    for left,right in spans:
        while p<len(predicted) and predicted[p]<left:p+=1
        p0=p
        while p<len(predicted) and predicted[p]<right:p+=1
        while q<len(truth) and truth[q]<left:q+=1
        q0=q
        while q<len(truth) and truth[q]<right:q+=1
        a,b,c,delta=_match_sorted(predicted[p0:p],truth[q0:q])
        tp+=a;fp+=b;fn+=c;valid_predictions+=p-p0;latencies.extend(delta)
    return tp,fp,fn,tuple(latencies),len(predicted)-valid_predictions


def _f1(tp,fp,fn):
    den=2*tp+fp+fn
    return Fraction(2*tp,den) if den else None


def metric(tp,fp,fn,duration,latencies):
    f1=_f1(tp,fp,fn);n=len(latencies)
    burden=60*fp/duration if duration else None
    try:burden_float=float(burden) if burden is not None else None
    except OverflowError:burden_float=None
    mean=1000*sum(latencies,Fraction())/n if n else None
    middle=1000*median(latencies) if n else None
    absolute=1000*sum(map(abs,latencies),Fraction())/n if n else None
    return {'tp':tp,'fp':fp,'fn':fn,'precision':tp/(tp+fp) if tp+fp else None,
        'recall':tp/(tp+fn) if tp+fn else None,'f1':float(f1) if f1 is not None else None,
        'valid_duration_seconds':float(duration),'valid_duration_ratio_seconds':ratio(duration),
        'false_events_per_minute':burden_float,
        'false_events_per_minute_ratio':ratio(burden) if burden is not None else None,
        'false_events_per_minute_presentation':'undefined_no_valid_time' if burden is None else 'overflow_exact_ratio_retained' if burden_float is None else 'finite',
        'matched_latency_mean_ms':float(mean) if mean is not None else None,
        'matched_latency_mean_ratio_ms':ratio(mean) if mean is not None else None,
        'matched_latency_median_ms':float(middle) if middle is not None else None,
        'matched_latency_median_ratio_ms':ratio(middle) if middle is not None else None,
        'matched_absolute_latency_mean_ms':float(absolute) if absolute is not None else None,
        'matched_absolute_latency_mean_ratio_ms':ratio(absolute) if absolute is not None else None}


def score_movie(indices,gold,public):
    predicted=tuple(public['frame_times'][i] for i in indices)
    tp,fp,fn,latencies,excluded=_match_intervals(predicted,gold['spikes'],gold['valid_intervals'])
    duration=sum((b-a for a,b in gold['valid_intervals']),Fraction());total=public['end']-public['start']
    result=metric(tp,fp,fn,duration,latencies)
    result.update(cell_id=public['cell_id'],frame_count=len(public['frame_times']),
        nominal_optical_rate_hz=public['nominal_optical_rate_hz'],input_disposition=public['input_disposition'],
        total_duration_seconds=float(total),total_duration_ratio_seconds=ratio(total),valid_duration_fraction=float(duration/total),
        predictions_outside_valid_support=excluded,
        support_disposition='unscorable' if not duration else 'complete_validity' if duration==total else 'partial_validity')
    return result,latencies


def representation_ceiling(reference,contract):
    """Evaluator-only aggregate ceiling. Never emit oracle frame indices."""
    movies={};cells={}
    def result(m,n,eligible):
        return {'reference_events':n,'maximum_matches':m,'eligible_frame_centers':eligible,
                'attainable_recall':m/n if n else None,
                'representation_only_f1':2*m/(m+n) if n else None}
    for mid,public in contract['movies'].items():
        gold=reference[mid];m,fp,fn,_,excluded=_match_intervals(public['frame_times'],gold['spikes'],gold['valid_intervals'])
        movies[mid]=result(m,len(gold['spikes']),len(public['frame_times'])-excluded)
    for cid in contract['cells']:
        rows=[movies[mid] for mid,p in contract['movies'].items() if p['cell_id']==cid]
        cells[cid]=result(*(sum(r[k] for r in rows) for k in ('maximum_matches','reference_events','eligible_frame_centers')))
    return {'scope':'private output-representation ceiling, not optical recoverability','movies':movies,'cells':cells}


def role_result(by_movie,reference,contract,mapping):
    movies={};cells={};latencies={c:[] for c in contract['cells']}
    for mid,p in contract['movies'].items():
        row,delta=score_movie(by_movie[mid],reference[mid],p);movies[mid]=row;latencies[p['cell_id']].extend(delta)
    for cid in contract['cells']:
        rows=[r for r in movies.values() if r['cell_id']==cid]
        duration=sum((Fraction(*r['valid_duration_ratio_seconds']) for r in rows),Fraction())
        total=sum((Fraction(*r['total_duration_ratio_seconds']) for r in rows),Fraction())
        row=metric(*(sum(r[k] for r in rows) for k in ('tp','fp','fn')),duration,latencies[cid])
        row.update(movie_count=len(rows),frame_count=sum(r['frame_count'] for r in rows),
            optical_extraction_failed_movies=sum(r['input_disposition']=='optical_extraction_failed' for r in rows),
            partial_validity_movies=sum(r['support_disposition']=='partial_validity' for r in rows),
            unscorable_movies=sum(r['support_disposition']=='unscorable' for r in rows),
            complete_validity=all(r['support_disposition']=='complete_validity' for r in rows),
            total_duration_seconds=float(total),total_duration_ratio_seconds=ratio(total),valid_duration_fraction=float(duration/total),
            predictions_outside_valid_support=sum(r['predictions_outside_valid_support'] for r in rows))
        cells[cid]=row
    subjects={}
    for subject in sorted(set(mapping.values())):
        members=sorted(c for c in cells if mapping[c]==subject)
        defined=[_f1(*(cells[c][k] for k in ('tp','fp','fn'))) for c in members]
        observed=[v for v in defined if v is not None]
        equal=sum(observed,Fraction())/len(members) if len(observed)==len(members) else None
        subjects[subject]={'cells':members,'cell_count':len(members),'defined_cell_count':len(observed),
            'equal_cell_f1':float(equal) if equal is not None else None,
            'equal_cell_f1_ratio':ratio(equal) if equal is not None else None,
            'observed_only_equal_cell_f1':float(sum(observed,Fraction())/len(observed)) if observed else None,
            'complete_validity':all(cells[c]['complete_validity'] for c in members),
            'optical_extraction_failed_movies':sum(cells[c]['optical_extraction_failed_movies'] for c in members)}
        duration=sum((Fraction(*cells[c]['valid_duration_ratio_seconds']) for c in members),Fraction())
        total=sum((Fraction(*cells[c]['total_duration_ratio_seconds']) for c in members),Fraction())
        subjects[subject].update(movie_count=sum(cells[c]['movie_count'] for c in members),
            frame_count=sum(cells[c]['frame_count'] for c in members),valid_duration_seconds=float(duration),
            valid_duration_ratio_seconds=ratio(duration),total_duration_seconds=float(total),
            total_duration_ratio_seconds=ratio(total),valid_duration_fraction=float(duration/total),
            partial_validity_movies=sum(cells[c]['partial_validity_movies'] for c in members),
            unscorable_movies=sum(cells[c]['unscorable_movies'] for c in members),
            predictions_outside_valid_support=sum(cells[c]['predictions_outside_valid_support'] for c in members))
    strata={}
    for nominal in (400,1000):
        rows=[r for r in movies.values() if r['nominal_optical_rate_hz']==nominal]
        duration=sum((Fraction(*r['valid_duration_ratio_seconds']) for r in rows),Fraction())
        strata[str(nominal)]={'movie_count':len(rows),'tp':sum(r['tp'] for r in rows),'fp':sum(r['fp'] for r in rows),
            'fn':sum(r['fn'] for r in rows),'valid_duration_seconds':float(duration),'valid_duration_ratio_seconds':ratio(duration),
            'meaning':'metadata nominal stratum; never a generated or measured cadence'}
    return {'movies':movies,'cells':cells,'subjects':subjects,'nominal_sampling_strata':strata}


def grade(public,predictions,private_loader):
    """Freeze every complete role before one trusted private callback.

    This is a scoring library, not a process boundary. Reference/loader failures
    propagate as operational/reference errors, never synthetic zero scores.
    """
    contract=public_contract(public)
    try:captured,commitments=capture_predictions(predictions,contract)
    except SubmissionError as error:
        return {'status':'invalid_submission','reason':str(error),'private_reference_loads':0,
                'scientific_qualified':False,'new_benchmark_ids':0,'task_id':TASK,'profile':PROFILE}
    reference,mapping=capture_reference(private_loader(),contract)
    results={role:role_result(captured[role],reference,contract,mapping) for role in ROLES}
    contrasts={}
    for baseline in ROLES[1:]:
        delta={}
        for subject in results['candidate']['subjects']:
            a=results['candidate']['subjects'][subject]['equal_cell_f1_ratio']
            b=results[baseline]['subjects'][subject]['equal_cell_f1_ratio']
            delta[subject]=float(Fraction(*a)-Fraction(*b)) if a is not None and b is not None else None
        contrasts[baseline]={'candidate_minus_baseline_subject_f1':delta}
    return {'status':'scored_source_component','task_id':TASK,'profile':PROFILE,'public_sha256':contract['identity'],
        'private_reference_loads':1,'commitments':commitments,'roles':results,'contrasts':contrasts,
        'private_representation_ceiling':representation_ceiling(reference,contract),
        'primary':'six subject-specific equal-cell F1 values; no cross-subject scalar',
        'support':'complete roster; metrics only on declared valid optical/electrical intersection',
        'matching_rule':'earliest-compatible maximum-cardinality inclusive exact 1/200 second within connected validity',
        'physical_clock_or_reference_authenticity_established':False,'scientific_qualified':False,'new_benchmark_ids':0}
