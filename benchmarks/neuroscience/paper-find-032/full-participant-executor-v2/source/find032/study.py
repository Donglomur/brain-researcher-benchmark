"""Complete participant scientific composition; definitions only during BUILD."""
from dataclasses import dataclass
from .core import Custody, Refusal
from .roster import PARTICIPANTS, CONDITIONS
from .preparation import load_recording, select_events, epochs, empirical_recording, subset
from .decoding import cross_validate, stratified_plan, omission_generalize
from .products import ProductKey
from .transitions import most_likely_labels, lag_coverage, theoretical_accuracy


@dataclass
class ParticipantResult:
    participant: str
    products: dict
    axes: tuple
    support: dict
    unavailable: tuple


def stimulus_chain(recording):
    indices = tuple(i for i, e in enumerate(recording.events)
                    if int(e[2]) in (1, 2, 3, 4, 10, 20, 30, 40))
    return (tuple(int(recording.events[i, 0]) - int(recording.raw.first_samp) for i in indices),
            tuple(int(recording.events[i, 2]) for i in indices), indices)


def participant(plan, person, input_root_fd, budget, custody, operation):
    """No child report is accepted as a substitute for any calculated product.

    The operation context is a controller accounting boundary, NOT a native
    execution grant. Deployment/qualification must occur before this internal API.
    All recordings, original and reordered, retire before the result returns.
    """
    if person not in PARTICIPANTS:
        raise Refusal('unselected participant')
    local = Custody(custody)
    owned = []
    output, evidence, unavailable = {}, {}, []
    with local.attempt('participant'):
        try:
            # Same original Budget/operation ledger; failures flow through this
            # participant owner before reaching the campaign and its Outcome.
            operation = operation.scoped(local)
            originals = {}
            for condition in CONDITIONS:
                rec = load_recording(plan, person, condition, input_root_fd, budget, local, operation)
                owned.append(rec)
                originals[condition] = rec
            views = {}
            for stimulus in ('sound', 'omission'):
                nulls = {'random': originals['random']}
                for condition in CONDITIONS[1:]:
                    if stimulus == 'sound':
                        rid, _ = select_events(originals['random'], 'sound')
                        tid, _ = select_events(originals[condition], 'sound')
                    else:
                        rid = stimulus_chain(originals['random'])[2]
                        tid = stimulus_chain(originals[condition])[2]
                    rec, selected = empirical_recording(originals['random'], originals[condition],
                        stimulus=stimulus, random_indices=rid, target_indices=tid, operation=operation, custody=local)
                    owned.append(rec)
                    nulls[condition] = rec
                    evidence[stimulus + '/reorder/' + condition] = {'source_events': selected,
                        'pieces': rec.support.pieces}
                route = {}
                for pipeline, records in (('replication', originals), ('empirical_null', nulls)):
                    for condition, rec in records.items():
                        selected, removed = select_events(rec, stimulus)
                        route[pipeline, condition] = epochs(rec, selected, stimulus, operation)
                        evidence[stimulus + '/' + pipeline + '/' + condition] = {
                            'eligible_event_indices': selected, 'pre_fit_removed': removed}
                count = min(len(v.labels) for v in route.values())
                # Matched truncation is the selected source convention, fixed
                # before any fit; retain every original and omitted row identity.
                for key, view in route.items():
                    evidence[stimulus + '/matched/' + '/'.join(key)] = {
                        'selected': view.event_indices[:count],
                        'matched_excess': view.event_indices[count:], 'denominator': count}
                    views[stimulus, *key] = subset(view, count)
                evidence['structural_random/' + stimulus] = random_identity_evidence(
                    originals['random'], nulls['random'],
                    views[stimulus, 'replication', 'random'],
                    views[stimulus, 'empirical_null', 'random'])
            train = views['sound', 'replication', 'random']
            for condition in CONDITIONS:
                tests = {'oof_random': (train, train.labels)}
                for pipeline in ('replication', 'empirical_null'):
                    view = views['sound', pipeline, condition]
                    tests[pipeline] = (view, view.labels)
                    if condition != 'random':
                        tests[pipeline + '/most_likely'] = (view, most_likely_labels(view.labels, condition))
                # Paired original/null tests of ONE condition share fits and a
                # common purge. Different conditions are distinct fit jobs. A
                # global union of unrelated test folds must not erase all training.
                plan_folds = stratified_plan(train, tests)
                results = cross_validate(train, tests, splits=plan_folds, operation=operation)
                for name, result in results.items():
                    if name == 'oof_random':
                        continue
                    pipeline = name.split('/')[0]
                    score = 'most_likely' if '/' in name else 'accuracy'
                    output[ProductKey(person, 'sound', pipeline, condition, score)] = result['accuracy']
                    evidence['sound/folds/' + condition + '/' + name] = result['support']
                output[ProductKey(person, 'sound', 'random_oof', condition, 'confusion')] = results['oof_random']['fold_confusion']
                evidence['oof_confusion/' + condition] = {'fold_counts': results['oof_random']['fold_counts'],
                                                         'support': results['oof_random']['support']}
            for condition in CONDITIONS:
                tests = {pipeline: views['omission', pipeline, condition]
                         for pipeline in ('replication', 'empirical_null')}
                results = omission_generalize(train, tests, operation=operation)
                for pipeline, row in results.items():
                    output[ProductKey(person, 'omission', pipeline, condition, 'accuracy')] = row['accuracy']
                    evidence['omission/fit/' + condition + '/' + pipeline] = {
                        'test_count': row['test_count'], 'training_indices': row['training_indices']}
            # Protected analysis tail only: never feed the future event map to a
            # participant's prediction function or use it to select training data.
            for condition in CONDITIONS:
                confusion = output[ProductKey(person, 'sound', 'random_oof', condition, 'confusion')]
                samples, codes, chain_indices = stimulus_chain(originals[condition])
                index = {original: chain for chain, original in enumerate(chain_indices)}
                targets = tuple(index[i] for i in views['sound', 'replication', condition].event_indices)
                import numpy as np
                plans = evidence['oof_confusion/' + condition]['support']
                fold_coverage = []
                for fold, plan_row in enumerate(plans):
                    selected_targets = tuple(targets[i] for i in plan_row['test']['replication'])
                    coverage = lag_coverage(samples, codes, selected_targets, tuple(range(-70, 71)),
                                            tuple(range(-70, 71)))
                    fold_coverage.append(coverage)
                evidence['theoretical_coverage/' + condition] = tuple(fold_coverage)
                if not all(x['complete'] for x in fold_coverage):
                    counts = {}
                    for row in fold_coverage:
                        for reason, count in row['reason_counts'].items():
                            counts[reason] = counts.get(reason, 0) + count
                    unavailable.append({'endpoint': 'theoretical_null/' + condition,
                        'reason': 'complete observed theoretical support unavailable',
                        'planned_cells': sum(x['planned_cells'] for x in fold_coverage),
                        'reason_counts': counts})
                else:
                    fold_theory = [theoretical_accuracy(confusion[fold], train.times, row['cells'], condition)
                                   for fold, row in enumerate(fold_coverage)]
                    theory = np.stack(fold_theory).mean(axis=0)
                    output[ProductKey(person, 'sound', 'theoretical_null', condition, 'accuracy')] = theory
            result = ParticipantResult(person, output, (train.times, train.times), evidence, tuple(unavailable))
        except BaseException as error:
            if local.first is None:
                local.catch('participant body', error)
        finally:
            for rec in reversed(owned):
                local.close('recording retirement', rec.close)
        local.raise_first()
    return result


def random_identity_evidence(original, null, original_view, null_view):
    """Source-produced identity-control provenance, never native authority.

    Random is the original recording in both branches. Check actual selected
    event/sample/label/data/time support before calling the shared fit consumer.
    Group additionally checks paired fit support and exact returned products.
    """
    import numpy as np
    if original is not null:
        raise Refusal('random empirical control must use the identical recording')
    if (original_view.event_indices != null_view.event_indices or
            original_view.supports != null_view.supports or
            any(not np.array_equal(a, b) for a, b in (
                (original_view.labels, null_view.labels),
                (original_view.data, null_view.data),
                (original_view.times, null_view.times)))):
        raise Refusal('random identity control has different actual support')
    if not original_view.event_indices:
        raise Refusal('random identity control requires nonempty complete support')
    return {'kind': 'same_original_random_recording',
            'input_sha256': original.input_capture.sha256,
            'event_indices': original_view.event_indices,
            'support_checked': 'exact events/original-samples/labels/data/times',
            'fit_route': 'paired_condition_random'}
