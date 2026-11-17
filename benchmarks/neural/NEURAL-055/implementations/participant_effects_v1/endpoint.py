"""Retain the ten paired people behind NEURAL-055's aggregate endpoints.

Operator-only extension of the preserved reporting module. No targets, files,
fitting, resampling, or participant operations are opened or dispatched here.
"""
import copy
import math


def require(value, message):
    if not value:
        raise ValueError(message)


def _identity(core, expected, terminals):
    """Bind one opaque case to each person before reporting matched effects."""
    people = tuple(core.PEOPLE)
    require(len(people) == len(set(people)) == 10, "exact ten-person roster")
    require(len({core.token(c) for c in expected}) == len(expected),
            "duplicate expected cells cannot become replicates")
    cases = {}
    replicates = {}
    for cell in expected:
        person = cell['outer_person']
        require(person in people, "unknown independent person")
        terminal = terminals[core.token(cell)]
        require(terminal['cell_key'] == cell, "terminal belongs to this exact cell")
        case = terminal.get('public_case_identity')
        if case is not None:
            require(type(case) is str and bool(case), "nonempty opaque case identity")
            require(person not in cases or cases[person] == case,
                    "same person must retain its case across conditions and seeds")
            cases[person] = case
        if terminal['status'] in core.VALID:
            require(case is not None, "completed cell requires its public case")
        key = core.condition_key(cell)
        counts = replicates.setdefault(key, {})
        counts[person] = counts.get(person, 0) + 1
    require(len(set(cases.values())) == len(cases), "distinct people require distinct public cases")
    return people, cases, replicates


def _person_points(core, metrics):
    require(set(metrics) == set(core.METRICS), "all original endpoint metrics")
    result = {}
    for metric in core.METRICS:
        rows = metrics[metric]
        require(len(rows) == 10 and all(len(row) == 200 for row in rows),
                "complete ten-person by 200-image outcome support")
        for row in rows:
            require(all(type(v) in (int, float) and not math.isnan(v) and
                        (math.isfinite(v) or metric == 'NLL' and v == math.inf)
                        for v in row), "finite endpoints or positive infinite NLL only")
        result[metric] = [core.mean(row) for row in rows]
    return result


def participant_endpoints(core, system, expected, terminals, outcomes, pairing,
                          contrast_registry):
    """Use the original replicate averaging and image join, then retain people.

    A single unavailable required cell excludes its entire condition, exactly
    as in the original report. There is no observed-subset primary estimate.
    """
    people, cases, replicates = _identity(core, expected, terminals)
    values, missing = core.complete_conditions(expected, terminals, outcomes, pairing)
    rows = contrast_registry['contrasts']
    require(contrast_registry['count'] == 32 and
            [row['id'] for row in rows] == ['C%02d' % i for i in range(1, 33)],
            "preserve the complete registered 32-contrast family")
    points = {key: _person_points(core, value) for key, value in values.items()}
    conditions = []
    for key, metrics in points.items():
        require(set(replicates[key]) == set(people) and set(cases) == set(people),
                "complete independently identified people")
        conditions.append({
            'key': list(key),
            'participants': [
                {'case_id': cases[person], 'queries': 200,
                 'replicate_cells_averaged': replicates[key][person],
                 'metrics': {metric: core.extended(value[i])
                             for metric, value in metrics.items()}}
                for i, person in enumerate(people)]})
    contrasts = []
    for row in rows:
        left, right = core.contrast_terms(row, system)
        entry = {'id': row['id'], 'status': 'unavailable'}
        contrasts.append(entry)
        if left[0] not in points or right[0] not in points:
            entry['reason'] = 'required_complete_condition_unavailable'
            continue
        # The primary contrast may compare assignment against independent
        # accuracy within a person, rather than the same metric across arms.
        pairs = {'assignment_accuracy_contrast': (left, right)}
        if row['kind'] != 'assignment_minus_independent':
            pairs.update({metric: ((left[0], metric), (right[0], metric))
                          for metric in ('independent_accuracy', 'NLL', 'Brier', 'Top5')})
        effects = []
        for i, person in enumerate(people):
            metrics = {}
            for name, (a, b) in pairs.items():
                av = points[a[0]][a[1]][i]
                bv = points[b[0]][b[1]][i]
                metrics[name] = {'left': core.extended(av), 'right': core.extended(bv),
                                 'left_minus_right': core.extended(core.difference(av, bv))}
            effects.append({'case_id': cases[person], 'metrics': metrics})
        entry.update(status='available', independent_people=10, participants=effects)
    return {'schema': 'neural055-participant-endpoints-v1',
            'independent_unit': 'person', 'required_people': 10,
            'shared_candidate_images': 200,
            'replicate_aggregation': 'mean across required cells within person before image mean',
            'condition_scores': conditions,
            'unavailable_conditions': [{'key': list(k), **v} for k, v in missing.items()],
            'paired_person_effects': contrasts,
            'scope': 'Descriptive effects for ten people on the fixed shared image panel; no population inference.',
            'raw_query_outcomes_or_targets_included': False,
            'scientific_qualification_claim': False}


def paired_report(core, system, expected, terminals, outcomes, pairing, schedule,
                  contrast_registry, interpretation_records, guard):
    """Explicit successor API; preserve every original numerical report field.

    A qualified operator supplies its authenticated original reporting module.
    This does not select, modify or bypass the protected target-last route.
    """
    guard('before participant endpoint identity and support checks')
    extension = participant_endpoints(core, system, expected, terminals, outcomes,
                                     pairing, contrast_registry)
    original = core.paired_report(system, expected, terminals, outcomes, pairing,
                                 schedule, contrast_registry, interpretation_records, guard)
    require(original['schema'] == 'neural055-complete-paired-report-v1',
            "exact original paired report schema")
    require('participant_endpoints' not in original, "extension must not overwrite prior evidence")
    require({tuple(row['key']) for row in original['conditions']} ==
            {tuple(row['key']) for row in extension['condition_scores']},
            "same complete conditions as original numerical report")
    require([(row['id'], row['status']) for row in original['contrasts']] ==
            [(row['id'], row['status']) for row in extension['paired_person_effects']],
            "same available full-family contrasts as original numerical report")
    result = copy.deepcopy(original)
    result['participant_endpoints'] = extension
    guard('after complete participant endpoint report')
    return result
