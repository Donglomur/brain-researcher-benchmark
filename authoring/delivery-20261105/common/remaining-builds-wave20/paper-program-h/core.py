"""Fixed H scope, trial-group splits and prospective conditional null; no data reads."""
import hashlib
import hmac
import json
import math
import random

TASK='PAPER-FIND-ADD-003'

ROLES=('A','B','reference')
VARIANTS=('source_preprocessing','no_smoothing_no_flooring')
DAYS=('standard_minus2','standard_minus1','reversal1','reversal2')
FAMILIES=('neural','nuisance_clock','combined','clock_prior','shuffled_combined')
WINDOWS=((94,109),(109,124),(124,139),(139,154),(154,169)) # Python half-open; full 75-frame common delay
NATIVE_FAMILIES={'behavior_accuracy':368,'behavior_lick_latency':368,'sequence_peak_fraction':154,'sequence_index':176,'time_bin_correlation':176,'time_confusion':8624,'odor_accuracy':12056,'odor_information':6512}


def need(ok,message):
    if not ok:raise ValueError(message)


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def identity(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def descriptor(value):
    need(type(value) is dict and set(value)=={'bytes','sha256'},'Exact bytes/hash descriptor')
    need(type(value['bytes']) is int and value['bytes']>=0 and type(value['sha256']) is str and len(value['sha256'])==64 and all(x in '0123456789abcdef' for x in value['sha256']),'Exact bounded descriptor')
    return value


def split(k):
    need(type(k) is int and 0<=k<7,'One of seven full trial folds')
    universe=set(range(140));query=set(range(20*k,20*k+20))
    def neighbors(j):return {20*j-1,20*j+20}&universe
    train=universe-query-neighbors(k)
    inner=[]
    for j in range(7):
        if j==k:continue
        block=set(range(20*j,20*j+20))
        inner.append({'fold':j,'train':sorted(train-block-neighbors(j)),'validation':sorted(train&block)})
    return {'fold':k,'query':sorted(query),'train':sorted(train),'purged':sorted(universe-query-train),'inner':inner}


def atoms(split_value):
    groups={}
    for trial in split_value['train']:
        signature=(trial//20,*(int(trial in row[name]) for row in split_value['inner'] for name in ('train','validation')))
        groups.setdefault(signature,[]).append(trial)
    return [groups[key] for key in sorted(groups)]


def shuffled_targets(labels,split_value,case,private_seed):
    need(type(labels) in (list,tuple) and len(labels)==140 and all(type(x) is int and x in (0,1) for x in labels),'Complete authenticated binary targets')
    need(type(private_seed) is bytes and len(private_seed)==32,'Exactly one private precommitted benchmark randomization seed')
    seed=int.from_bytes(hmac.new(private_seed,encoded({'schema':'h_private_conditional_atom_shuffle_v2','case':case,'fold':split_value['fold']}),hashlib.sha256).digest(),'big')
    rng=random.Random(seed);out={};rows=[]
    for group in atoms(split_value):
        permutation=list(group);rng.shuffle(permutation);values=[labels[i] for i in permutation]
        out.update(zip(group,values));rows.append({'trials':group,'permutation_source_trials':permutation,'class_counts':[values.count(0),values.count(1)],'singleton':len(group)==1,'constant':len(set(values))==1})
    return out,{'schema':'h_conditional_null_v1','private_derived_seed_sha256':hashlib.sha256(seed.to_bytes(32,'big')).hexdigest(),'public_seed_commitment':hashlib.sha256(private_seed).hexdigest(),'atoms':rows,'meaning':'Conditional within eligibility/chunk atoms; association can remain. No chance requirement or reseeding.'}


def cases():
    for variant in VARIANTS:
        for animal in range(11):
            for day in DAYS:
                for fold in range(7):yield {'variant':variant,'animal_ordinal':animal,'day':day,'fold':fold}


def job(action,role,**fields):
    value={'action':action,'role':role,**fields}
    return {'id':identity({'schema':'h_phase_identity_v1',**value}),**value}


def planned_jobs():
    """Complete ordered phase graph. A generator avoids a quadratic full-roster log."""
    yield job('prepare_originals','operator')
    for case in cases():yield job('prepare_fold','operator',case=case)
    for role in ROLES:yield job('native_attempt',role,native_calls=11,slots=56868)
    for case in cases():
        for role in ROLES:
            for family in FAMILIES:yield job('analytic_prior' if family=='clock_prior' else 'train_model',role,case=case,family=family)
    for case in cases():
        for role in ROLES:
            for family in FAMILIES:yield job('evaluate_model','operator',producer_role=role,case=case,family=family)
    yield job('grade','operator')
    yield job('report','operator')


def model_key(case,role,family):
    return identity({'case':case,'role':role,'family':family})


def expected_counts():
    return {'prepare_originals':1,'prepare_fold':616,'native_attempt':3,'native_literal_calls':33,'train_model':7392,'analytic_prior':1848,'evaluate_model':9240,'grade':1,'report':1,'phases':19102,'model_slots':9240,'prediction_records':924000,'independent_reference_fit_attempts':298144,'native_slots_per_role':56868}


def finite(value):return type(value) in (int,float) and math.isfinite(value)
