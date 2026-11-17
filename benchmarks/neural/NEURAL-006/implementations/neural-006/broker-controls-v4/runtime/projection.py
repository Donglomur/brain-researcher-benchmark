"""Trusted original-row projection; candidate packets never receive source CSVs or held outcomes."""
import csv
import io
import math
from collections import Counter
from protocol import ACTIVE, SOURCE, RESERVE, TARGETS, PRIMITIVES, FEATURES, INPUTS, need

def numeric(token):
    if token in ('','NA','NaN'):
        return None
    value = float(token)
    need(math.isfinite(value), 'nonfinite_source_number')
    return value

def integer(token):
    value = numeric(token)
    need(value is not None and value == int(value), 'identity_integer')
    return int(value)

def project(read_pinned, root, stage):
    """read_pinned owns extent/hash/resource checks; no caller-supplied unpinned source accepted."""
    need(stage in ('development_lopo33','reserved_frozen33_test8'), 'projection_stage')
    frames = {}
    for name, (size, sha) in INPUTS.items():
        body = read_pinned(root / name, size, sha)
        reader = csv.DictReader(io.StringIO(body.decode('utf-8-sig'), newline=''))
        need(reader.fieldnames is not None and len(set(reader.fieldnames)) == len(reader.fieldnames), 'source_columns')
        rows = list(reader)
        need(len(rows) == 7380 and all(None not in row for row in rows), 'source_extent')
        frames[name] = rows
    result = {p:[] for p in (SOURCE if stage == 'reserved_frozen33_test8' else ACTIVE)}
    seen = Counter(); identities = set()
    for source_index, original in enumerate(frames['BEH_ug.csv'], 1):
        person = str(integer(original['sub'])); trial = integer(original['trialGlobal'])
        local = integer(original['trialLocal'])
        need(person in SOURCE and 1 <= local <= 5, 'source_identity')
        seen[person] += 1
        need(trial == seen[person] and (person,trial) not in identities, 'source_trial_order')
        identities.add((person,trial))
        if person not in result:
            continue  # No reserved measurement conversion or missingness inspection in development.
        row = {name:numeric(original[name]) for name in PRIMITIVES}
        row.update(participant=person, source_row=source_index, trialGlobal=trial, trialLocal=local)
        for suffix, source, left, right in (
            ('R','rpe','offer','rp'),('V','epe_valence','exp_valence','ep_valence'),
            ('A','epe_arousal','exp_arousal','ep_arousal')):
            expected = None if row[left] is None or row[right] is None else row[left]-row[right]
            actual = numeric(original[source])
            need((actual is None) == (expected is None), 'prediction_error_missingness')
            need(actual is None or abs(actual-expected) < 1e-8, 'prediction_error_equation')
            row['abs_'+suffix] = None if expected is None else abs(expected)
        for target in TARGETS:
            row[target] = numeric(frames['df_'+target+'.csv'][source_index-1][target])
        result[person].append(row)
    need(set(seen) == set(SOURCE) and all(n == 180 for n in seen.values()), 'complete41_identity_roster')
    return result

def eligible(row):
    return all(row[key] is not None for key in FEATURES + TARGETS)

def permute_targets(data, permutation):
    need(sorted(permutation) == list(ACTIVE), 'whole_participant_permutation')
    need(set(data) == set(ACTIVE), 'no_reserve_in_permutation')
    out = {}
    for destination, origin in zip(ACTIVE, permutation):
        rows = []
        for a,b in zip(data[destination],data[origin]):
            need(a['trialGlobal'] == b['trialGlobal'], 'trajectory_ordinal_join')
            row = dict(a)
            for target in TARGETS:
                row[target] = b[target]
            rows.append(row)
        out[destination] = rows
    return out

def make_case(data, person, draw, stage):
    need(person in (ACTIVE if stage == 'development_lopo33' else RESERVE), 'held_stage')
    need(len(draw) == 33 and all(p in ACTIVE for p in draw), 'complete_resample_draw')
    training = []
    copies = []
    for index, original_person in enumerate(draw):
        if original_person == person:
            continue  # Every duplicate of the original held person is excluded.
        rows = [r for r in data[original_person] if eligible(r)]
        need(bool(rows), 'training_person_has_no_paired_rows')
        copy_id = 'cluster_%02d' % index
        copies.append({'fit_id':copy_id,'original_participant':original_person})
        for row in rows:
            value = {key:row[key] for key in FEATURES + TARGETS}
            value.update(participant=copy_id, original_participant=original_person, source_row=row['source_row'])
            training.append(value)
    need(len(copies) >= 2, 'insufficient_resampled_training_clusters')
    query = [{key:row[key] for key in FEATURES + ('source_row',)} for row in data[person]
             if all(row[key] is not None for key in FEATURES)]
    truth = {row['source_row']:{target:row[target] for target in TARGETS}
             for row in data[person] if eligible(row)}
    need(bool(query) and bool(truth), 'held_person_has_no_query_or_paired_rows')
    return {'schema':'neural006-case-v1','participant':person,'training':training,
            'query':query,'clusters':copies}, truth

def reserve_packets(data):
    """One common training projection and all8 unlabeled queries; reserve truth stays separate."""
    need(set(data)==set(SOURCE),'reserve_source_roster')
    training_case=None;queries=[];per_person={};truth={}
    for person in sorted(RESERVE):
        case,held=make_case(data,person,list(ACTIVE),'reserved_frozen33_test8')
        if training_case is None:
            training_case={'schema':'neural006-case-v1','participant':'training33',
                'training':case['training'],'query':[],'clusters':case['clusters']}
        else:
            need(case['training']==training_case['training'] and case['clusters']==training_case['clusters'],'one_common33_training_projection')
        per_person[person]={'schema':'neural006-case-v1','participant':person,'training':[],
                            'query':case['query'],'clusters':[]}
        truth[person]=held;queries.extend(case['query'])
    batch={'schema':'neural006-case-v1','participant':'reserved8',
        'training':training_case['training'],'query':queries,'clusters':training_case['clusters']}
    return training_case,batch,per_person,truth
