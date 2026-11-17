"""Operator-side A0 participant endpoint from the existing late-target score.

Import after the pinned persistent-state runtime has been authenticated/loaded.
This is a report projection, not a target issuer, participant input, or native
qualification bypass. No recording, target, prediction, receipt, or fitted state
is traversed or serialized here.
"""
import json
import math
from numbers import Real

from n061.contracts import need
from n061.grading import paired_records
from n061.outputs import Disposition
from n061.policy import panel_name
from n061.production import Production
from n061.scoring import reduce_common


FIELDS = ('BR_improvement', 'BC_improvement', 'candidate_BR_loss',
          'candidate_BC_loss', 'reference_BR_loss', 'reference_BC_loss')


def _loss(value):
    need(isinstance(value, Real) and not isinstance(value, bool), 'real loss')
    try:
        number = float(value)
    except (ValueError, OverflowError):
        raise ValueError('representable binary64 loss') from None
    need(math.isfinite(number) and number >= 0, 'finite nonnegative MSE')
    return number


def _index_records(scored, cat, common):
    """Reject partial, duplicated or independently selected session summaries."""
    panels = ('REFERENCE', panel_name(cat.policy.panels[0]))
    records = scored['session_records']
    need(type(records) is dict and set(records) == set(panels), 'exact selected A0 panels')
    support = {(s.region, s.session): s for s in common.sessions}
    expected = {(s.region, s.session, seed) for s in common.sessions for seed in cat.policy.seeds}
    indexed = {}
    for panel in panels:
        rows = {}
        for row in records[panel]:
            key = (row['region'], row['session'], row['match_seed'])
            need(key in expected and key not in rows, 'unique complete selected session/seed census')
            need(type(row['match_seed']) is int, 'integer matching seed')
            ss = support[key[:2]]
            need(row['support'] is ss and row['status'] == ss.status.value,
                 'original common support; no independent exclusions')
            need((row['panel'], row['head'], row['budget'], row['realization'], row['animal']) ==
                 (panel, cat.policy.head, 10, 'anatomy', ss.animal), 'exact selected axes and animal')
            losses = row['arm_losses']
            if ss.status is Disposition.COMPLETE:
                need(type(losses) is dict and set(losses) == set(cat.required_arms(panel)),
                     'six reference or two participant arm losses')
                # Copy only known scalar operands. Unrelated score objects stay private.
                losses = {arm: _loss(losses[arm]) for arm in cat.required_arms(panel)}
            else:
                need(ss.status is Disposition.UNAVAILABLE and losses is None,
                     'scientific unavailable has no selectively retained arm loss')
            rows[key] = {**{k: row[k] for k in ('support', 'status')}, 'arm_losses': losses}
        need(set(rows) == expected, 'every region/session/seed disposition required')
        indexed[panel] = rows
    return indexed


def participant_report(production, scored):
    """Return JSON-safe participant metrics, without a pooled regional ranking.

    ``scored`` must be the operator's result of n061.grading.score with this
    exact Production. Caller-created scores are not authenticated by this
    projection; the preceding preparation/production/late-target gates remain
    mandatory. Generated controls can exercise the pure report path separately.
    """
    need(type(production) is Production, 'actual typed production')
    production.validate()
    cat = production.catalogue
    cat.policy.require_selected()
    need(scored['task'] == 'NEURAL-061' and scored['policy'] is cat.policy and
         scored['support'] is production.support, 'same task/policy/common-support score')
    common = production.support
    indexed = _index_records(scored, cat, common)
    panel = panel_name(cat.policy.panels[0])
    records = paired_records(indexed, panel, 'REFERENCE', common, 'competence')
    animal_alias = {a: f'animal_{i + 1:02d}' for i, a in enumerate(cat.animals)}
    session_alias = {s: f'session_{i + 1:02d}' for i, s in enumerate(cat.evaluation)}
    by_region = {r: [] for r in cat.regions}
    for row in records:
        by_region[row['region']].append(row)
    regions = []
    for region in cat.regions:
        aggregate = reduce_common(by_region[region], common, region, 'competence:' + panel, FIELDS)
        session_rows = tuple(s for s in common.sessions if s.region == region)
        coverage = []
        for ss in session_rows:
            # Keep every unavailable operand; detailed source causes remain in
            # the operator-owned CommonSupport and are not raw report payloads.
            missing = [{'seed': key.cell[3], 'panel': key.panel, 'arm': key.arm}
                       for key, _cause in ss.causes]
            coverage.append({'session': session_alias[ss.session], 'animal': animal_alias[ss.animal],
                             'status': ss.status.value, 'required_seed_count': 10,
                             'completed_seed_count': len(ss.complete_seeds),
                             'complete_seeds': list(ss.complete_seeds),
                             'included_in_every_comparison': ss.status is Disposition.COMPLETE,
                             'unavailable_operands': missing})
        animals = []
        for animal in cat.animals:
            included = [s for s in session_rows if s.animal == animal and s.status is Disposition.COMPLETE]
            animals.append({'animal': animal_alias[animal], 'included_session_count': len(included),
                            'planned_session_count': sum(s.animal == animal for s in session_rows),
                            'status': 'complete' if included else 'scientific_unavailable',
                            'metrics': aggregate['animals'].get(animal)})
        means = aggregate['means']
        regions.append({'region': region, 'n_animals': aggregate['n_animals'],
                        'planned_animal_count': 13, 'primary': means['candidate_BR_loss'],
                        'metrics': {field: means[field] for field in FIELDS},
                        'animals': animals, 'session_coverage': coverage})
    return {
        'schema': 'neural061-participant-endpoint/v1', 'task': 'NEURAL-061',
        'condition': 'frozen_program', 'selected_tier': cat.policy.tier.value, 'panel': panel,
        'primary': {'metric': 'candidate_BR_loss', 'name': 'Signed wheel velocity MSE',
                    'direction': 'lower', 'reporting_unit': 'region',
                    'units': 'squared source wheel_velocity units; physical units not yet qualified',
                    'aggregation': 'equal timestamps within window, equal windows, all ten seeds, '
                                   'equal eligible sessions within animal, equal animals'},
        'paired_improvement_direction': 'reference loss minus participant loss; higher is better',
        'planned_evaluation_sessions': 29, 'planned_evaluation_animals': 13,
        'matching_seed_count': 10, 'region_count': len(cat.regions), 'regions': regions,
        'operator_reference_inference': {'source_field': 'primary_family',
                                        'role': 'reference-only regional replacement Holm family',
                                        'is_participant_score': False},
        'qualification': {'report_source_only': True, 'scientific_qualification': False,
                          'direct_observation_delivered': False, 'typed_viewer_delivered': False,
                          'adaptive_or_trained_tool_condition_selected': False},
        'limitations': ['Per-region animal support can differ; no anatomical ranking or pooled score.',
                        'Ten matching seeds and nested sessions do not increase biological n.',
                        'Participant competence is descriptive; reference inference remains separate.',
                        'Detailed exclusion causes remain in operator-owned CommonSupport.',
                        'Relative aliases preserve support joins; this is not a privacy guarantee.'],
    }


def report_bytes(production, scored):
    """Strict JSON serialization only; storage/publication authority is external."""
    return (json.dumps(participant_report(production, scored), sort_keys=True,
                       separators=(',', ':'), allow_nan=False) + '\n').encode('utf8')
