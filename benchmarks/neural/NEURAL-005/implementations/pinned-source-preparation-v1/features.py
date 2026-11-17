"""Historical 50/53/57 prefix features, with strict identity validation.

No fitting, source-standardized columns, future rows, or participant predictors.
"""
import math

BEHAVIOR = ('offer', 'rp', 'ep_valence', 'ep_arousal', 'exp_valence', 'exp_arousal')
ERP = ('FRN_N2_offer', 'P2_offer', 'P2_base_offer', 'P3a_offer',
       'P3a_base_offer', 'P3b_offer', 'P3b_base_offer')
BASE = ('P2_base_offer', 'P3a_base_offer', 'P3b_base_offer')
META = ('round', 'trial_global', 'episode', 'partner', 'choice')
RECORD_KEYS = set(BEHAVIOR + ERP + META)
HISTORY_BASE_NAMES = (('round', 'target_round', 'trial_global', 'episode') + BEHAVIOR
    + ('current_reject', 'prefix_reject_fraction', 'prefix_reject_count',
       'offer_mean', 'offer_min', 'offer_max', 'offer_last_change')
    + tuple('prefix_mean_' + x for x in BEHAVIOR[1:])
    + ('reward_error', 'valence_error', 'arousal_error'))
HISTORY_NAMES = HISTORY_BASE_NAMES + tuple('missing_' + x for x in HISTORY_BASE_NAMES)
ARMS = {'history': HISTORY_NAMES, 'prestimulus': HISTORY_NAMES + BASE,
        'all_erp': HISTORY_NAMES + ERP}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def mean(values):
    present = [v for v in values if v is not None]
    return math.fsum(present) / len(present) if present else None


def difference(left, right):
    return None if left is None or right is None else left - right


def validate_prefix(prefix):
    need(type(prefix) is list and 1 <= len(prefix) <= 4, 'prefix rounds 1..4')
    first = prefix[0]
    for i, row in enumerate(prefix):
        need(type(row) is dict and set(row) == RECORD_KEYS, 'exact observed record fields')
        need(all(type(row[k]) is int for k in META), 'integer metadata; no booleans')
        need(row['round'] == i + 1 and row['choice'] in (0, 1), 'round/choice identity')
        need(1 <= row['episode'] <= 36 and 1 <= row['trial_global'] <= 180,
             'source episode/trial range')
        need(row['partner'] == first['partner'] and row['episode'] == first['episode']
             and row['trial_global'] == first['trial_global'] + i, 'consecutive single episode')
        for key in BEHAVIOR + ERP:
            v = row[key]
            need(v is None or (type(v) in (int, float) and math.isfinite(v)),
                 'finite or declared missing measurement')
    need(all(prefix[-1][key] is not None for key in ERP), 'current seven-ERP support')


def vector(prefix, arm):
    # Support is checked before any view masking, even for behavioral history.
    validate_prefix(prefix)
    need(arm in ARMS, 'known view')
    row = prefix[-1]
    offers = [r['offer'] for r in prefix]
    need(all(v is not None for v in offers), 'known offer')
    values = [row['round'], row['round'] + 1, row['trial_global'], row['episode']]
    values += [row[k] for k in BEHAVIOR]
    values += [row['choice'], mean([r['choice'] for r in prefix]),
               sum(r['choice'] for r in prefix), mean(offers), min(offers), max(offers),
               offers[-1] - offers[-2] if len(offers) > 1 else 0.]
    values += [mean([r[k] for r in prefix]) for k in BEHAVIOR[1:]]
    values += [difference(row['offer'], row['rp']),
               difference(row['exp_valence'], row['ep_valence']),
               difference(row['exp_arousal'], row['ep_arousal'])]
    values += [int(v is None) for v in values]
    if arm == 'prestimulus':
        values += [row[k] for k in BASE]
    if arm == 'all_erp':
        values += [row[k] for k in ERP]
    need(len(values) == len(ARMS[arm]), 'fixed feature width')
    return values
