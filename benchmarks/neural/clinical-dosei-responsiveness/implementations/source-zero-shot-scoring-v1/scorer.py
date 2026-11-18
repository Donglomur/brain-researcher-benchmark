"""Pure complete-slot scoring; authentic custody and execution are driver-owned."""
from collections import Counter
import hashlib
import json
import math
import re

POLICY_SHA256 = 'f3d8bc83cfd233fca3882b39a633354837216311a466a2b711056838ad170952'
TRANSPORT_SHA256 = '69fd0c85374240bba63fc212304b4af9882c8afee0ff8b7d0fbeea3e5b6ef048'
CONDITION = 'native_marker_relative_30s_v1'
ARMS = ('viewer_only', 'code_enabled')
CASE_COUNT = 7345
RECORDING_COUNT = 171
ABSTENTION_LOSS = 1.00001


class ScoringRefusal(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ScoringRefusal(message)


def admit_policy(raw):
    require(type(raw) is bytes and len(raw) <= 65536 and
            hashlib.sha256(raw).hexdigest() == POLICY_SHA256,
            'exact adopted policy bytes required')
    policy = json.loads(raw)
    require(policy['schema'] == 'dosei_zero_shot_scoring_policy_v1' and
            policy['transport']['sha256'] == TRANSPORT_SHA256 and
            policy['primary']['labeled_abstention_loss'] == ABSTENTION_LOSS,
            'adopted policy implementation binding differs')
    return policy


def targets_by_case(envelope, expected):
    require(type(envelope) is dict and set(envelope) == {'schema', 'condition', 'cases'} and
            envelope['schema'] == 'dosei_private_zero_shot_targets_v1' and
            envelope['condition'] == CONDITION, 'exact private target envelope required')
    rows = envelope['cases']
    require(type(rows) is list and len(rows) == CASE_COUNT, 'all7345 target slots required')
    found = {}; recordings = set()
    for row in rows:
        require(type(row) is dict and set(row) == {'case_id', 'recording_id', 'category'},
                'exact target fields; no inferred person metadata')
        ident, rid, category = row['case_id'], row['recording_id'], row['category']
        require(type(ident) is str and ident in expected and ident not in found,
                'unique matched target case required')
        require(type(rid) is str and len(rid) <= 64 and re.fullmatch('[1-9][0-9]*', rid),
                'source recording identifier required')
        require(category is None or type(category) is int and 1 <= category <= 5,
                'source grouped category must be null or exact integer1..5')
        found[ident] = (rid, category); recordings.add(rid)
    require(set(found) == set(expected) and len(recordings) == RECORDING_COUNT,
            'complete matched cases and171 recording groups required')
    return found, sorted(recordings, key=int)


def rps(probabilities, category):
    """On transport-admitted vectors, without normalization or clipping."""
    return math.fsum((math.fsum(probabilities[:k]) - int(category <= k))**2
                     for k in (1, 2, 3, 4)) / 4


def lower_median(probabilities):
    for k in (1, 2, 3, 4, 5):
        if math.fsum(probabilities[:k]) >= 0.5:
            return k
    raise ScoringRefusal('admitted vector has no median')


def mean_or_none(values):
    return math.fsum(values) / len(values) if values else None


class _Stats:
    def __init__(self):
        self.slots = 0; self.nulls = 0
        self.ok_labeled = self.abstain_labeled = self.ok_null = self.abstain_null = 0
        self.losses = []; self.answered = []; self.errors = []
        self.correct = 0; self.support = Counter(); self.hits = Counter()

    def add(self, category, row):
        self.slots += 1
        answered = row['status'] == 'ok'
        if category is None:
            self.nulls += 1
            if answered: self.ok_null += 1
            else: self.abstain_null += 1
            return None
        self.support[category] += 1
        if answered:
            self.ok_labeled += 1
            loss = rps(row['probabilities'], category)
            point = lower_median(row['probabilities'])
            self.answered.append(loss); self.errors.append(abs(point-category)/4)
            if point == category:
                self.correct += 1; self.hits[category] += 1
        else:
            self.abstain_labeled += 1; loss = ABSTENTION_LOSS; self.errors.append(1.0)
        self.losses.append(loss)
        return loss

    def report(self):
        n = len(self.losses)
        return {
            'slot_count': self.slots, 'graded_denominator': n, 'null_count': self.nulls,
            'ok_labeled': self.ok_labeled, 'abstain_labeled': self.abstain_labeled,
            'ok_null': self.ok_null, 'abstain_null': self.abstain_null,
            'ok_all_slots': self.ok_labeled+self.ok_null,
            'abstain_all_slots': self.abstain_labeled+self.abstain_null,
            'graded_coverage': self.ok_labeled/n if n else None,
            'all_slot_coverage': (self.ok_labeled+self.ok_null)/self.slots if self.slots else None,
            'primary_loss': mean_or_none(self.losses),
            'answered_loss_component': math.fsum(self.answered)/n if n else None,
            'abstention_loss_component': ABSTENTION_LOSS*self.abstain_labeled/n if n else None,
            'normalized_MAE': mean_or_none(self.errors),
            'exact_accuracy': self.correct/n if n else None,
            'answered_only_RPS': mean_or_none(self.answered),
            'answered_only_denominator': self.ok_labeled,
            'per_category_recall': [
                {'category': c, 'support': self.support[c], 'correct': self.hits[c],
                 'recall': self.hits[c]/self.support[c] if self.support[c] else None}
                for c in (1, 2, 3, 4, 5)],
        }


def score_pair(policy_bytes, public_manifest, private_targets, submitted, *, transport):
    """Score complete decoded objects, without I/O or implicit abstentions.

    The trusted caller authenticates transport source, actual full manifests,
    target custody, sealed predictions, workflow assistance and run status.
    Shape/hash agreement here alone does not establish those scientific facts.
    """
    policy = admit_policy(policy_bytes)
    require(type(public_manifest) is list and len(public_manifest) == CASE_COUNT,
            'all7345 public observation bindings required')
    pair = transport.admit_pair(public_manifest, submitted)
    expected = {row['case_id'] for row in public_manifest}
    targets, recording_ids = targets_by_case(private_targets, expected)
    totals = {arm: _Stats() for arm in ARMS}
    groups = {rid: {arm: _Stats() for arm in ARMS} for rid in recording_ids}
    differences = []; group_differences = {rid: [] for rid in recording_ids}
    references = {item['name']: _Stats() for item in policy['fixed_no_training_references']}
    for i, binding in enumerate(public_manifest):
        rid, category = targets[binding['case_id']]
        loss = {}
        for arm in ARMS:
            row = pair[arm][i]
            loss[arm] = totals[arm].add(category, row)
            groups[rid][arm].add(category, row)
        if category is not None:
            delta = loss['viewer_only']-loss['code_enabled']
            differences.append(delta); group_differences[rid].append(delta)
        for item in policy['fixed_no_training_references']:
            references[item['name']].add(category, {'status': 'ok', 'probabilities': item['probabilities']})
    record_rows = []
    for rid in recording_ids:
        reports = {arm: groups[rid][arm].report() for arm in ARMS}
        shared = reports['viewer_only']
        record_rows.append({'recording_id': rid, 'slot_count': shared['slot_count'],
                            'labeled_count': shared['graded_denominator'], 'null_count': shared['null_count'],
                            'arms': reports, 'paired_difference': mean_or_none(group_differences[rid])})
    supported = [row for row in record_rows if row['labeled_count'] > 0]
    total_reports = {arm: totals[arm].report() for arm in ARMS}
    return {
        'schema': 'dosei_zero_shot_paired_score_report_v1', 'visibility': 'evaluator_private',
        'condition': CONDITION, 'policy_sha256': POLICY_SHA256,
        'transport_source_sha256_required_of_driver': TRANSPORT_SHA256,
        'population': {'slots': CASE_COUNT, 'recordings': RECORDING_COUNT,
                       'labeled': len(differences), 'null_targets_ungraded': CASE_COUNT-len(differences)},
        'arms': total_reports, 'paired_difference': mean_or_none(differences),
        'paired_graded_denominator': len(differences), 'positive_difference_favors': 'code_enabled',
        'recordings': record_rows,
        'equal_record_descriptive': {
            'supported_recordings': len(supported), 'total_recordings': RECORDING_COUNT,
            'arm_primary_losses': {arm: mean_or_none([row['arms'][arm]['primary_loss'] for row in supported]) for arm in ARMS},
            'paired_difference': mean_or_none([row['paired_difference'] for row in supported]),
        },
        'fixed_references': [
            {'name': item['name'], 'probabilities': list(item['probabilities']),
             'label_fitted': False, 'metrics': references[item['name']].report()}
            for item in policy['fixed_no_training_references']],
        'scorer_inserted_abstentions': False, 'probabilities_repaired': False,
        'null_targets_imputed': False, 'source_cases_filtered': False,
        'biological_person_inference': False, 'independent_sampling_assumed': False,
        'confidence_intervals_or_pvalues_computed': False,
        'authentic_manifests_or_transport_source_authenticated_by_scorer': False,
        'operational_abstention_reasons_and_delivery_failures': 'separate authenticated driver report required',
        'participant_isolation_and_assistance_qualified_by_scorer': False,
        'historical_person_weighted_scorer_activated': False,
    }
