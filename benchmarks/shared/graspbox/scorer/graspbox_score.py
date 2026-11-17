"""Authored GraspBox full-cohort scorer; stdlib only, no native data reader.

The evaluator supplies an authenticated private manifest. Receipts are checked
declarations, not evidence that a process was actually isolated. No score from
this module confers scientific admission, official parity, or task readiness.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import stat
import statistics

CLASSES = ('PG', 'UG', 'WH')
# Table 1 expectations, never a manufactured authentic label distribution.
COUNTS = ((5,148,148), (4,120,104), (4,120,100), (3,90,88),
          (3,90,80), (3,90,83), (3,90,45), (4,120,110),
          (4,120,109), (4,120,120), (4,120,115), (4,120,120),
          (4,120,120), (3,90,38))
MANIFEST_LIMIT = 2 * 1024**2
PREDICTION_LIMIT = 2 * 1024**2
LINE_LIMIT = 1024 * 1024
HASH = re.compile(r'[0-9a-f]{64}\Z')
IDENTIFIER = re.compile(r'[A-Za-z0-9_-]{1,96}\Z')
QUERY = re.compile(r'q_[0-9a-f]{32}\Z')
GATES = ('native_census', 'scalp_eog_reference_map', 'physical_units',
         'performed_label_mapping', 'frame_alignment', 'session_repeat_grouping',
         'opaque_query_mapping', 'evaluator_label_isolation')


class Invalid(ValueError):
    """A complete run is invalid; no partial score may be emitted."""


def need(condition, message):
    if not condition:
        raise Invalid(message)


def keys(value, expected, where):
    need(type(value) is dict and set(value) == set(expected), where + ': exact fields')


def identifier(value, where):
    need(type(value) is str and IDENTIFIER.fullmatch(value), where + ': identifier')
    return value


def digest(value, where):
    need(type(value) is str and HASH.fullmatch(value), where + ': SHA256')
    return value


def unique(values, where):
    need(type(values) is list, where + ': list')
    for value in values:
        identifier(value, where)
    need(len(set(values)) == len(values), where + ': duplicate')
    return set(values)


def same_ids(values, expected, where):
    need(unique(values, where) == set(expected), where + ': exact coverage')


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def _nonfinite(value):
    raise Invalid('nonfinite JSON number: ' + value)


def strict_json(data):
    try:
        if type(data) is bytes:
            data = data.decode('utf-8')
        need(type(data) is str, 'JSON requires UTF-8 bytes or decoded text')
        value = json.loads(data, object_pairs_hook=_pairs, parse_constant=_nonfinite)
    except Invalid:
        raise
    except (UnicodeError, ValueError, RecursionError) as error:
        raise Invalid('malformed bounded JSON') from error
    # Decimal exponents such as 1e999 also must fail, including unused fields.
    def walk(x, depth=0):
        need(depth <= 32, 'JSON nesting limit')
        if type(x) is float:
            need(math.isfinite(x), 'nonfinite JSON number')
        elif type(x) is dict:
            for y in x.values():
                walk(y, depth + 1)
        elif type(x) is list:
            for y in x:
                walk(y, depth + 1)
    walk(value)
    return value


def bounded_read(path, limit):
    # Refuse symlink final operands, devices and FIFOs before reading. Parent
    # path custody and concurrent mutation require the external evaluator.
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | os.O_NONBLOCK
    try:
        fd = os.open(path, flags)
        with os.fdopen(fd, 'rb') as stream:
            before = os.fstat(stream.fileno())
            need(stat.S_ISREG(before.st_mode), 'ordinary input file required')
            need(before.st_size <= limit, 'input byte limit')
            data = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
            need(len(data) <= limit, 'input byte limit')
            need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns) ==
                 (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),
                 'input changed during read')
            need(len(data) == before.st_size, 'input length changed')
            return data
    except OSError as error:
        raise Invalid('input could not be opened as an ordinary file') from error


def validate_manifest(manifest):
    keys(manifest, ('schema','class_order','evidence_kind','protocol_sha256',
                    'admission','participants','trials','folds'), 'manifest')
    need(manifest['schema'] == 'graspbox_scoring_manifest_v1', 'manifest schema')
    need(manifest['class_order'] == list(CLASSES), 'class order must be PG UG WH')
    need(manifest['evidence_kind'] in ('invented_control','admitted_native_census'), 'evidence kind')
    digest(manifest['protocol_sha256'], 'protocol')
    admission = manifest['admission']
    keys(admission, ('census_sha256','semantic_review_sha256','gates'), 'admission')
    digest(admission['census_sha256'], 'census')
    digest(admission['semantic_review_sha256'], 'semantic review')
    keys(admission['gates'], GATES, 'semantic gates')
    need(all(value == 'verified' for value in admission['gates'].values()), 'unresolved semantic gate')
    people = manifest['participants']
    need(type(people) is list and len(people) == 14, 'all fourteen people required')
    by_person, cohort = {}, {}
    for person in people:
        keys(person, ('participant_id','cohort_index','source_sha256'), 'person')
        pid = identifier(person['participant_id'], 'participant')
        index = person['cohort_index']
        need(type(index) is int and 1 <= index <= 14, 'cohort index')
        need(pid not in by_person and index not in cohort, 'duplicate participant/cohort index')
        digest(person['source_sha256'], 'source')
        by_person[pid], cohort[index] = person, pid
    need(len({p['source_sha256'] for p in people}) == 14, 'distinct original file identities')
    trials = manifest['trials']
    need(type(trials) is list and len(trials) == 1558, 'all 1558 expected trials required')
    queries, person_rows, blocks, sessions = {}, {p:[] for p in by_person}, {}, {}
    for row in trials:
        keys(row, ('query_id','participant_id','block_id','session_id',
                   'source_row_one_based','label','event_complete'), 'trial')
        qid = row['query_id']
        need(type(qid) is str and QUERY.fullmatch(qid), 'opaque query ID syntax')
        need(qid not in queries, 'duplicate query ID in manifest')
        pid = row['participant_id']
        identifier(pid, 'trial participant')
        need(pid in by_person, 'unknown trial participant')
        bid = identifier(row['block_id'], 'block')
        sid = row['session_id']
        need(sid is None or type(sid) is str, 'session must be absent or an identifier')
        if sid is not None:
            identifier(sid, 'session')
            need(sid not in sessions or sessions[sid] == pid, 'session crosses people')
            sessions[sid] = pid
        need(bid not in blocks or blocks[bid] == (pid,sid), 'block crosses people or sessions')
        blocks[bid] = (pid,sid)
        need(type(row['source_row_one_based']) is int and row['source_row_one_based'] > 0, 'original row index')
        need(type(row['label']) is str and row['label'] in CLASSES, 'unknown released grip label')
        need(type(row['event_complete']) is bool, 'event-complete flag must be boolean')
        queries[qid] = row
        person_rows[pid].append(row)
    for index in range(1,15):
        pid, (nblocks,nrows,ncomplete) = cohort[index], COUNTS[index-1]
        rows = person_rows[pid]
        need(len(rows) == nrows, 'per-person trial count')
        need({r['source_row_one_based'] for r in rows} == set(range(1,nrows+1)), 'complete unique original rows')
        need(len({r['block_id'] for r in rows}) == nblocks, 'per-person block count')
        need(sum(r['event_complete'] for r in rows) == ncomplete, 'per-person event census')
        need({r['label'] for r in rows} == set(CLASSES), 'every participant must support all three classes')
    need(len(blocks) == 52, 'all 52 blocks required')
    folds = manifest['folds']
    need(type(folds) is list and len(folds) == 14, 'all fourteen outer folds required')
    by_fold, held, query_fold = {}, set(), {}
    everyone = set(by_person)
    for fold in folds:
        keys(fold, ('fold_id','held_out_participant_id','training_participant_ids',
                    'test_query_ids','inner_folds'), 'outer fold')
        fid = identifier(fold['fold_id'], 'fold')
        pid = identifier(fold['held_out_participant_id'], 'held person')
        need(fid not in by_fold and pid not in held and pid in everyone, 'duplicate/unknown outer fold')
        same_ids(fold['training_participant_ids'], everyone-{pid}, 'outer training people')
        expected = {r['query_id'] for r in person_rows[pid]}
        same_ids(fold['test_query_ids'], expected, 'outer test queries')
        inners = fold['inner_folds']
        need(type(inners) is list and len(inners) == 13, 'all thirteen inner folds required')
        inner_held = set()
        for inner in inners:
            keys(inner, ('held_out_participant_id','training_participant_ids'), 'inner fold')
            val = identifier(inner['held_out_participant_id'], 'inner held person')
            need(val in everyone-{pid} and val not in inner_held, 'inner held-out identity')
            same_ids(inner['training_participant_ids'], everyone-{pid,val}, 'inner training people')
            inner_held.add(val)
        need(inner_held == everyone-{pid}, 'inner complete person coverage')
        held.add(pid)
        by_fold[fid] = fold
        for qid in expected:
            need(qid not in query_fold, 'trial overlaps outer test folds')
            query_fold[qid] = fid
    need(held == everyone and set(query_fold) == set(queries), 'complete outer partition')
    return {'manifest':manifest,'people':by_person,'cohort':cohort,'rows':person_rows,
            'queries':queries,'folds':by_fold,'query_fold':query_fold}


def validate_receipts(receipts, view):
    need(type(receipts) is list and len(receipts) == 14, 'fourteen fold receipts required')
    seen, isolations, conversations, artifacts = set(), set(), set(), set()
    everyone = set(view['people'])
    for receipt in receipts:
        keys(receipt, ('fold_id','held_out_participant_id','training_participant_ids',
                       'isolation_id','conversation_id','input_modalities','network_enabled',
                       'cross_fold_state_reused','query_updates','fit_records'), 'fold receipt')
        fid = identifier(receipt['fold_id'], 'receipt fold')
        need(fid in view['folds'] and fid not in seen, 'receipt fold coverage')
        seen.add(fid)
        fold = view['folds'][fid]
        held = fold['held_out_participant_id']
        need(receipt['held_out_participant_id'] == held, 'receipt held-out person')
        same_ids(receipt['training_participant_ids'], everyone-{held}, 'receipt training people')
        for field, used in (('isolation_id',isolations), ('conversation_id',conversations)):
            value = identifier(receipt[field], field)
            need(value not in used, 'cross-fold reused ' + field)
            used.add(value)
        need(receipt['input_modalities'] == ['scalp_EEG'], 'forbidden input modality')
        for field in ('network_enabled','cross_fold_state_reused','query_updates'):
            need(receipt[field] is False, 'forbidden ' + field)
        fits = receipt['fit_records']
        need(type(fits) is list and len(fits) <= 2048, 'bounded fit provenance')
        fit_ids = set()
        for fit in fits:
            keys(fit, ('fit_id','stage','inner_held_out_participant_id',
                       'training_participant_ids','artifact_id','artifact_sha256',
                       'input_modalities'), 'fit provenance')
            name = identifier(fit['fit_id'], 'fit ID')
            artifact = identifier(fit['artifact_id'], 'artifact ID')
            need(name not in fit_ids and artifact not in artifacts, 'reused fit or cross-fold artifact identity')
            fit_ids.add(name)
            artifacts.add(artifact)
            digest(fit['artifact_sha256'], 'fit artifact')
            need(fit['input_modalities'] == ['scalp_EEG'], 'fit modality leakage')
            if fit['stage'] == 'outer':
                need(fit['inner_held_out_participant_id'] is None, 'outer fit inner identity')
                expected = everyone-{held}
            elif fit['stage'] == 'inner':
                val = identifier(fit['inner_held_out_participant_id'], 'fit validation person')
                need(val in everyone-{held}, 'fit uses outer held-out person')
                expected = everyone-{held,val}
            else:
                raise Invalid('unknown fit stage')
            same_ids(fit['training_participant_ids'], expected, 'fit training leakage/coverage')
    need(seen == set(view['folds']), 'receipt exact fold coverage')


def validate_predictions(header, records, view, manifest_sha256):
    keys(header, ('schema','class_order','manifest_sha256','protocol_sha256','fold_receipts'), 'prediction header')
    need(header['schema'] == 'graspbox_predictions_v1', 'prediction schema')
    need(header['class_order'] == list(CLASSES), 'prediction class order')
    need(header['manifest_sha256'] == manifest_sha256, 'frozen manifest binding')
    need(header['protocol_sha256'] == view['manifest']['protocol_sha256'], 'frozen protocol binding')
    validate_receipts(header['fold_receipts'], view)
    need(type(records) is list and len(records) == 1558, 'complete prediction row count')
    predictions = {}
    for row in records:
        keys(row, ('query_id','fold_id','probabilities','prediction'), 'prediction record')
        qid = row['query_id']
        need(type(qid) is str and qid in view['queries'], 'extra or unknown query ID')
        need(qid not in predictions, 'duplicate prediction query ID')
        need(row['fold_id'] == view['query_fold'][qid], 'wrong held-out fold for query')
        prob = row['probabilities']
        need(type(prob) is list and len(prob) == 3, 'three probabilities required')
        need(all(type(p) in (int,float) and 0 <= p <= 1 and math.isfinite(p) for p in prob),
             'finite probabilities in [0,1] required')
        need(abs(math.fsum(prob)-1.0) <= 1e-6, 'probabilities must sum to one within 1e-6')
        # max returns the first index on ties: PG then UG then WH.
        predicted = max(range(3), key=lambda i:prob[i])
        need(row['prediction'] == CLASSES[predicted], 'prediction disagrees with deterministic argmax')
        predictions[qid] = (tuple(prob),predicted)
    need(set(predictions) == set(view['queries']), 'exact full prediction coverage')
    return predictions


def load_prediction_bytes(data):
    need(type(data) is bytes and len(data) <= PREDICTION_LIMIT, 'prediction byte limit')
    lines = data.splitlines()
    need(len(lines) == 1559, 'one header and 1558 JSONL records required')
    need(all(0 < len(line) <= LINE_LIMIT for line in lines), 'empty/oversized JSONL line')
    values = [strict_json(line) for line in lines]
    return values[0], values[1:]


def _person_metrics(rows, predictions):
    confusion = [[0,0,0] for _ in CLASSES]
    losses, briers = [], []
    bins = [[] for _ in range(10)]
    event = {True:{'trials':0,'class_counts':[0,0,0]}, False:{'trials':0,'class_counts':[0,0,0]}}
    for row in rows:
        truth = CLASSES.index(row['label'])
        prob,predicted = predictions[row['query_id']]
        confusion[truth][predicted] += 1
        losses.append(-math.log(max(prob[truth],1e-15)))
        briers.append(math.fsum((p-int(i==truth))**2 for i,p in enumerate(prob)))
        confidence = max(prob)
        bins[min(9,int(confidence*10))].append((confidence,int(predicted==truth)))
        e = event[row['event_complete']]
        e['trials'] += 1
        e['class_counts'][truth] += 1
    counts = [sum(row) for row in confusion]
    recall = [confusion[i][i]/counts[i] for i in range(3)]
    bin_rows, ece = [], 0.0
    for index, values in enumerate(bins):
        confidence = math.fsum(v[0] for v in values)/len(values) if values else None
        accuracy = math.fsum(v[1] for v in values)/len(values) if values else None
        if values:
            ece += len(values)/len(rows)*abs(confidence-accuracy)
        bin_rows.append({'lower':index/10,'upper':(index+1)/10,'count':len(values),
                         'mean_confidence':confidence,'accuracy':accuracy})
    return {'trials':len(rows),'class_counts':counts,'confusion_true_by_predicted':confusion,
            'recall':recall,'balanced_accuracy':math.fsum(recall)/3,
            'log_loss':math.fsum(losses)/len(rows),'brier_sum_over_classes':math.fsum(briers)/len(rows),
            'ece_10_equal_width':ece,'calibration_bins':bin_rows,
            'event_complete':event[True],'event_incomplete_retained':event[False]}


def score(view, predictions, manifest_sha256):
    people = {view['cohort'][index]:_person_metrics(view['rows'][view['cohort'][index]], predictions)
              for index in range(1,15)}
    pooled = [[sum(p['confusion_true_by_predicted'][i][j] for p in people.values())
               for j in range(3)] for i in range(3)]
    macro = {name:math.fsum(p[name] for p in people.values())/14
             for name in ('balanced_accuracy','log_loss','brier_sum_over_classes','ece_10_equal_width')}
    macro['recall'] = [math.fsum(p['recall'][i] for p in people.values())/14 for i in range(3)]
    return {'schema':'graspbox_score_v1','status':'COMPLETE_AUTHORED_CONTRACT_SCORE',
            'evidence_kind':view['manifest']['evidence_kind'],'manifest_sha256':manifest_sha256,
            'protocol_sha256':view['manifest']['protocol_sha256'],'class_order':list(CLASSES),
            'coverage':{'participants':14,'blocks':52,'trials':1558,'event_complete':1380,
                        'event_incomplete_retained':178,'outer_folds':14,'inner_folds':182},
            'participant_macro':macro,'participants':people,
            'pooled_confusion_diagnostic_only':pooled,
            'pooled_accuracy_diagnostic_only':sum(pooled[i][i] for i in range(3))/1558,
            'semantics':{'probabilities':'validated as submitted; never renormalized',
                         'log_loss':'natural log; true-class probability floor 1e-15 after validity',
                         'calibration':'Brier sums three classes; ten confidence bins [lo,hi), final includes 1; participant macro',
                         'receipts':'structurally checked declarations; no sandbox/isolation attestation'},
            'scientific_qualification':False,'benchmark_count_delta':0}


def evaluate(manifest, header, records, manifest_sha256):
    digest(manifest_sha256, 'manifest bytes')
    view = validate_manifest(manifest)
    predictions = validate_predictions(header, records, view, manifest_sha256)
    return score(view, predictions, manifest_sha256)


def _percentile(sorted_values, fraction):
    position = (len(sorted_values)-1)*fraction
    lower = int(position)
    upper = min(lower+1,len(sorted_values)-1)
    return sorted_values[lower]*(upper-position) + sorted_values[upper]*(position-lower) if lower != upper else sorted_values[lower]


def compare(manifest, first, second, manifest_sha256):
    """Paired first-minus-second differences; no refits or trial bootstrap."""
    a = evaluate(manifest,*first,manifest_sha256)
    b = evaluate(manifest,*second,manifest_sha256)
    ids = [p['participant_id'] for p in sorted(manifest['participants'],key=lambda p:p['cohort_index'])]
    values = {name:[a['participants'][pid][name]-b['participants'][pid][name] for pid in ids]
              for name in ('balanced_accuracy','log_loss')}
    rng = random.Random(20261115)
    samples = {name:[] for name in values}
    for _ in range(10000):
        indexes = [rng.randrange(14) for _ in range(14)]
        for name,delta in values.items():
            samples[name].append(math.fsum(delta[i] for i in indexes)/14)
    result = {}
    for name,delta in values.items():
        ordered = sorted(samples[name])
        result[name] = {'paired_values':[{'participant_id':p,'first_minus_second':v} for p,v in zip(ids,delta)],
                        'mean':math.fsum(delta)/14,'median':statistics.median(delta),
                        'percentile_95_interval':[_percentile(ordered,0.025),_percentile(ordered,0.975)]}
    return {'schema':'graspbox_paired_comparison_v1','first':a,'second':b,'differences':result,
            'bootstrap':{'unit':'participant','resamples':10000,'seed':20261115,
                         'paired':True,'quantile':'linear interpolation at (n-1)*p',
                         'direction':'first-minus-second; positive BA / negative log loss favors first',
                         'limits':'frozen predictions only; excludes method-selection and retraining uncertainty'}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--manifest-sha256',required=True)
    parser.add_argument('--predictions',required=True)
    parser.add_argument('--compare-predictions')
    args = parser.parse_args(argv)
    try:
        digest(args.manifest_sha256, 'expected manifest')
        raw = bounded_read(args.manifest,MANIFEST_LIMIT)
        need(hashlib.sha256(raw).hexdigest() == args.manifest_sha256, 'manifest byte hash mismatch')
        manifest = strict_json(raw)
        first = load_prediction_bytes(bounded_read(args.predictions,PREDICTION_LIMIT))
        if args.compare_predictions:
            second = load_prediction_bytes(bounded_read(args.compare_predictions,PREDICTION_LIMIT))
            result = compare(manifest,first,second,args.manifest_sha256)
        else:
            result = evaluate(manifest,*first,args.manifest_sha256)
        print(json.dumps(result,sort_keys=True,allow_nan=False,separators=(',',':')))
        return 0
    except Invalid as error:
        print(json.dumps({'schema':'graspbox_invalid_run_v1','valid':False,'error':str(error)},sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
