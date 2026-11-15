"""Opaque split structure only; the owner authenticates canonical assignment.

The owner must admit a root-pinned private preparation receipt and exact manifest
bytes before any fold. Structure alone cannot prove original deterministic splits.
"""
import hashlib
import json
import re

OPAQUE_ID = re.compile(r'animal_[0-9a-f]{64}\Z')
SCHEMA = 'abr-background-opaque-split-manifest/v1'
STATE_POLICY = {
    'fresh_agent_process_storage_per_outer_fold': True,
    'cohort_derived_state_shared_between_outer_folds': False,
    'shared_assets': 'frozen_method_and_predeclared_cohort_independent_assets_only',
    'references_use_identical_isolation': True,
    'feedback': 'all_104_out_of_fold_predictions_committed_before_any_aggregate_feedback',
    'enforcement': 'required_of_external_runner_not_provided_by_this_module',
}

class SplitError(ValueError):
    pass

def _need(condition, message):
    if not condition:
        raise SplitError(message)

def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'),
                          ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, OverflowError) as exc:
        raise SplitError('manifest must be finite JSON') from exc

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def _ids(value, universe, message):
    _need(type(value) is list and all(type(x) is str and x in universe for x in value), message)
    _need(value == sorted(set(value)), 'canonical unique IDs: ' + message)
    return set(value)

def validate_manifest(manifest):
    """Check opaque structure; this is not private preparation authentication.

    The selected owner first admits a root-pinned prepared_manifest receipt and
    exact operands. Direct calls to this pure function prove structure only.
    """
    keys = {'schema', 'outer_fold_count', 'inner_fold_count', 'animal_count',
            'class_counts', 'animals', 'folds', 'state_policy'}
    _need(type(manifest) is dict and set(manifest) == keys, 'closed opaque manifest')
    counts = manifest['class_counts']
    _need(type(counts) is dict and set(counts) == {'0', '1'} and
          all(type(value) is int for value in counts.values()), 'literal class-count integers')
    _need(manifest['schema'] == SCHEMA and type(manifest['outer_fold_count']) is int and
          manifest['outer_fold_count'] == 5 and type(manifest['inner_fold_count']) is int and
          manifest['inner_fold_count'] == 4 and type(manifest['animal_count']) is int and
          manifest['animal_count'] == 104 and manifest['class_counts'] == {'0':54, '1':50} and
          canonical(manifest['state_policy']) == canonical(STATE_POLICY), 'fixed counts and state policy')
    animals = manifest['animals']
    _need(type(animals) is list and len(animals) == 104, 'complete opaque animal roster')
    labels = {}; assignments = {}
    for animal in animals:
        _need(type(animal) is dict and set(animal) == {'animal_id', 'label', 'outer_fold'},
              'opaque animal row only')
        aid = animal['animal_id']; label = animal['label']; fold = animal['outer_fold']
        _need(type(aid) is str and OPAQUE_ID.fullmatch(aid) is not None and aid not in labels,
              'unique opaque animal ID')
        _need(type(label) is int and label in (0, 1) and type(fold) is int and 0 <= fold < 5,
              'literal label and fold')
        labels[aid] = label; assignments[aid] = fold
    _need(list(labels) == sorted(labels) and list(labels.values()).count(0) == 54 and
          list(labels.values()).count(1) == 50, 'canonical animal order and class totals')
    universe = set(labels); folds = manifest['folds']; all_test = set()
    _need(type(folds) is list and len(folds) == 5, 'five complete outer folds')
    for outer, fold in enumerate(folds):
        _need(type(fold) is dict and set(fold) == {'outer_fold', 'train_animal_ids',
              'test_animal_ids', 'inner_folds'} and type(fold['outer_fold']) is int and
              fold['outer_fold'] == outer, 'ordered closed outer fold')
        train = _ids(fold['train_animal_ids'], universe, 'outer train')
        test = _ids(fold['test_animal_ids'], universe, 'outer test')
        _need(train == universe - test and not train & test and
              test == {a for a in universe if assignments[a] == outer} and not all_test & test,
              'complete disjoint assigned outer partition')
        _need(sum(labels[a] == 0 for a in test) == (11 if outer < 4 else 10) and
              sum(labels[a] == 1 for a in test) == 10, 'fixed outer stratification')
        all_test |= test
        inner = fold['inner_folds']; validation_seen = set()
        _need(type(inner) is list and len(inner) == 4, 'four complete inner folds')
        for index, row in enumerate(inner):
            _need(type(row) is dict and set(row) == {'inner_fold', 'train_animal_ids',
                  'validation_animal_ids'} and type(row['inner_fold']) is int and
                  row['inner_fold'] == index, 'ordered closed inner fold')
            fitting = _ids(row['train_animal_ids'], train, 'inner train')
            validation = _ids(row['validation_animal_ids'], train, 'inner validation')
            _need(fitting == train - validation and not fitting & validation and
                  not validation_seen & validation, 'training-only disjoint inner partition')
            expected_zero = 11 if outer == 4 or index < 3 else 10
            _need(sum(labels[a] == 0 for a in validation) == expected_zero and
                  sum(labels[a] == 1 for a in validation) == 10, 'fixed inner stratification')
            validation_seen |= validation
        _need(validation_seen == train, 'every outer-training animal validated once')
    _need(all_test == universe, 'complete out-of-fold universe')
    return json.loads(canonical(manifest))

def public_fold_view(manifest, outer_fold):
    _need(type(outer_fold) is int and 0 <= outer_fold < 5, 'outer fold integer0..4')
    checked = validate_manifest(manifest)
    return {'schema': 'abr-background-public-fold-view/v1', **checked['folds'][outer_fold]}
