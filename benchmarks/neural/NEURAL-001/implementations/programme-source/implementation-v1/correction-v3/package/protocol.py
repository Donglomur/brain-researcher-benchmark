"""Complete NEURAL-001 plan and metadata invariants. No data/provider I/O."""
from dataclasses import dataclass
import hashlib
import json
import math
import re

TASK = 'NEURAL-001'
CONTROL_INTERPRETATION = 'disclosed_transform_robustness_inversion_allowed_v1'
DESIGN_SHA256 = '5e3d4a16233e0aa83f14dce6d5b8bae83f7444f1fa19e5dd7e5c8eb284bee806'
MODES = ('frozen_program', 'adaptive_case')
ARMS = ('neural', 'no_neural', 'within_query_half_shift')
PEOPLE = tuple(f'sub-{n:02}' for n in range(1, 25))
REFERENCES = ('R1', 'R2', 'R0')
REFERENCE_ARMS = {'R1': ('neural', 'within_query_half_shift'),
                  'R2': ('neural', 'within_query_half_shift'), 'R0': ('no_neural',)}
GATES = ('root_design_acceptance', 'sole_peer_design_acceptance',
         'source_complete_24_people_94_runs', 'sub02_standard_audio_actual_alignment',
         'native_preprocessing_clocks_channels_trim_lineage',
         'all_120_queries_each_and_70_protected_identity_groups',
         'private_alias_target_and_source_order_custody',
         'exact_dependencies_images_and_source', 'native_reference_numerical_compatibility',
         'independent_training_only_reference_competence', 'bounded_method_conformance_review',
         'provider_one_query_reset_and_no_network_isolation',
         'original_clock_process_custody_and_complete_telemetry',
         'full_workload_resource_profile', 'protected_scoring_authority')


class Refusal(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Refusal(message)


def finite_number(x, name, *, positive=False):
    require(type(x) in (int, float) and math.isfinite(x) and x >= 0,
            f'{name}: finite nonnegative non-Boolean number required')
    require(not positive or x > 0, f'{name}: positive value required')
    return x


def exact_int(x, name, minimum=0):
    require(type(x) is int and x >= minimum, f'{name}: integer >= {minimum} required')
    return x


def canonical(payload):
    return json.dumps(payload, sort_keys=True, ensure_ascii=True,
                      separators=(',', ':'), allow_nan=False).encode('ascii')


def pin_bytes(body):
    require(type(body) is bytes, 'bytes required')
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def check_pin(pin):
    require(type(pin) is dict and set(pin) == {'bytes', 'sha256'}, 'exact pin fields required')
    exact_int(pin['bytes'], 'pin bytes', 1)
    require(type(pin['sha256']) is str and re.fullmatch('[0-9a-f]{64}', pin['sha256']),
            'SHA256 hex required')


def panels():
    for mode in MODES:
        for arm in ARMS:
            yield f'candidate/{mode}/{arm}'
    for family in REFERENCES:
        for arm in REFERENCE_ARMS[family]:
            yield f'reference/{family}/{arm}'


@dataclass(frozen=True)
class Subject:
    """Operator-only roster, never serialize this object into a provider view."""
    canonical_id: str
    public_alias: str
    run_ids: tuple
    epoch_ids: tuple
    epoch_runs: tuple
    epoch_lengths: tuple
    query_ids: tuple
    query_lengths: tuple

    def __post_init__(self):
        require(self.canonical_id in PEOPLE, 'original canonical participant required')
        require(type(self.public_alias) is str and 1 <= len(self.public_alias) <= 32,
                'bounded public alias required')
        expected = 2 if self.canonical_id == 'sub-01' else 4
        for name in ('run_ids', 'epoch_ids', 'epoch_runs', 'epoch_lengths',
                     'query_ids', 'query_lengths'):
            require(type(getattr(self, name)) is tuple, f'{name}: immutable tuple required')
        require(len(self.run_ids) == len(set(self.run_ids)) == expected, 'all released runs required')
        require(len(self.epoch_ids) == len(self.epoch_runs) == len(self.epoch_lengths) > 0,
                'complete epoch roster required')
        require(len(set(self.epoch_ids)) == len(self.epoch_ids), 'unique epochs required')
        require(set(self.epoch_runs) == set(self.run_ids), 'each original run must contribute')
        require(len(self.query_ids) == len(set(self.query_ids)) == len(self.query_lengths) == 120,
                'exact120 unique trials required')
        for ident in (*self.run_ids, *self.epoch_ids, *self.query_ids):
            require(type(ident) is str and 1 <= len(ident) <= 32, 'bounded opaque IDs required')
        for n in (*self.epoch_lengths, *self.query_lengths):
            exact_int(n, 'interval samples', 4)
        require(sum(self.epoch_lengths) <= 250000, 'original training cap exceeded; no crop allowed')
        require(sum(self.query_lengths) <= 61440, 'original query cap exceeded; no crop allowed')

    def support(self):
        offsets = [0]
        for n in self.query_lengths:
            offsets.append(offsets[-1] + n)
        return {'id': self.canonical_id, 'query_ids': list(self.query_ids),
                'query_offsets': offsets, 'query_samples': offsets[-1]}


def validate_roster(subjects):
    require(type(subjects) is tuple and len(subjects) == 24, 'all24 immutable subjects required')
    require(all(type(s) is Subject for s in subjects), 'exact Subject records required')
    require(tuple(s.canonical_id for s in subjects) == PEOPLE, 'complete canonical ordering required')
    require(len({s.public_alias for s in subjects}) == 24, 'unique participant aliases required')
    require(sum(len(s.run_ids) for s in subjects) == 94, '94 released training runs required')
    require(len({q for s in subjects for q in s.query_ids}) == 2880,
            'globally unique opaque query IDs required')
    # Opacity/source correspondence requires separate trusted admission, not this syntax check.
    return subjects


@dataclass(frozen=True)
class Phase:
    sequence: int
    operation: str
    actor: str
    mode: str
    arm: str
    person: str
    query_id: str
    family: str

    def internal_key(self):
        """Internal audit identity; do NOT expose canonical person/order to provider."""
        return '/'.join(map(str, (self.sequence, self.operation, self.actor, self.mode,
                                 self.arm, self.person, self.query_id, self.family)))


def full_plan(subjects):
    """Generator covers complete agreed programme; no array access or execution."""
    validate_roster(subjects)
    seq = 0
    for mode in MODES:
        for arm in ('neural', 'no_neural'):
            seq += 1
            yield Phase(seq, 'author', 'candidate', mode, arm, '', '', '')
    # All global programs/recipes seal before any numeric study view is requested.
    for s in subjects:
        for family in REFERENCES:
            seq += 1
            arm = 'no_neural' if family == 'R0' else 'neural'
            yield Phase(seq, 'train', 'reference', '', arm, s.canonical_id, '', family)
        for mode in MODES:
            for arm in ('neural', 'no_neural'):
                seq += 1
                yield Phase(seq, 'train', 'candidate', mode, arm, s.canonical_id, '', '')
        # Every trained state for this person seals before first query.
        for panel in panels():
            parts = panel.split('/')
            actor, kind, arm = parts
            mode, family = (kind, '') if actor == 'candidate' else ('', kind)
            for qid in s.query_ids:
                seq += 1
                yield Phase(seq, 'predict', actor, mode, arm, s.canonical_id, qid, family)
            seq += 1
            yield Phase(seq, 'assemble', actor, mode, arm, s.canonical_id, '', family)
    seq += 1
    yield Phase(seq, 'grade', 'operator', '', '', '', '', '')


def workload_counts(subjects):
    counts = {}
    for p in full_plan(subjects):
        key = (p.actor, p.operation)
        counts[key] = counts.get(key, 0) + 1
    expected = {('candidate', 'author'): 4, ('reference', 'train'): 72,
                ('candidate', 'train'): 96, ('candidate', 'predict'): 17280,
                ('reference', 'predict'): 14400, ('candidate', 'assemble'): 144,
                ('reference', 'assemble'): 120, ('operator', 'grade'): 1}
    require(counts == expected, 'complete workload arithmetic mismatch')
    return {'phases': sum(counts.values()),
            'phase_counts': {f'{a}/{b}': n for (a, b), n in counts.items()},
            'query_predictions': 31680, 'panels': 11, 'person_panel_outputs': 264,
            'R1_ridge_fits': 682, 'R2_ridge_fits': 2280, 'R0_means': 24,
            'maximum_R2_PCA_fits': 236, 'new_benchmarks': 0}
