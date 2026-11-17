"""Fixed trusted-operator bindings; ordinary source imports, no runtime injection.

Future preparation/metric calls consume operator-private inputs. They do not
register generic execution or establish scientific qualification or isolation.
"""
import importlib
import json
from pathlib import Path

SOURCE = Path(__file__).resolve().parent / 'source'
ONE = 1048576
MATRIX_DESCRIPTOR = {'path': 'RUN_MATRIX.json', 'bytes': 111805, 'sha256': 'cd3b55e879470f9b435025e391ccf968a555fa7713f67da60a1b0bb5ed64681c'}

def require(value, message):
    if not value:
        raise ValueError(message)

def parse(body):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate metadata key')
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite metadata')))

def positive(value, name):
    require(type(value) is int and value > 0, name + ' must be an explicit positive integer')
    return value

class Metadata:
    def __init__(self, root, maximum):
        self.root = Path(root)
        require(self.root.is_absolute() and not any(p.is_symlink() for p in (self.root, *self.root.parents)),
                'operator asset root must be absolute without aliases')
        self.maximum = positive(maximum, 'metadata limit')
        self.used = 0

    def read(self, descriptor):
        require(type(descriptor) is dict and set(descriptor) == {'path', 'bytes', 'sha256'},
                'exact metadata descriptor required')
        n = positive(descriptor['bytes'], 'metadata extent')
        require(n <= ONE and n <= self.maximum - self.used, 'metadata allocation bound')
        native = importlib.import_module('native_dataset')
        body = native.capture(self.root, descriptor, n)
        self.used += n
        return parse(body)

def matrix():
    return importlib.import_module('run_composition').build_matrix(SOURCE)

def verify_source():
    return importlib.import_module('author_source').verify()

def recipe(condition, seed):
    return importlib.import_module('native_plan').plan(condition, seed)

def prepare_inputs(request, array_root):
    # No caller source root or numerical/runtime override reaches this function.
    return importlib.import_module('native_dataset').prepare(request, array_root, source_root=SOURCE)

def pearson_runtime():
    from scipy.stats import pearsonr
    return pearsonr

def generation_runtime():
    from types import SimpleNamespace
    import numpy as np
    import pandas as pd
    from sklearn.metrics import precision_recall_fscore_support
    return SimpleNamespace(np=np, pd=pd, precision_recall_fscore_support=precision_recall_fscore_support)

def saved_matrix():
    native = importlib.import_module('native_dataset')
    return parse(native.capture(SOURCE / 'operator', MATRIX_DESCRIPTOR, MATRIX_DESCRIPTOR['bytes']))

def _cell(definition, cell_id, condition, kinds):
    found = [(row['case'], cell) for row in definition['rows'] for cell in row['cells']
             if cell['id'] == cell_id]
    require(len(found) == 1, 'declared complete-matrix cell required')
    case, cell = found[0]
    require(cell['condition'] == condition and case['kind'] in kinds,
            'source metric cell/condition/kind identity')
    require(condition in ('released_computational_path_10ms', 'protected_support_source_amended_10ms'),
            'no native metric substitution for prospective5ms')
    return case

def behavior_metrics(asset_root, predictions, expected, targets, max_metadata_bytes, max_values):
    reader = Metadata(asset_root, max_metadata_bytes)
    packets = reader.read(predictions)
    specs = reader.read(expected)
    cap = positive(max_values, 'scalar bound')
    require(type(specs) is list and 0 < len(specs) <= 85, 'bounded selected native metric roster')
    ids = []
    total = 0
    definition = saved_matrix()
    for spec in specs:
        require(type(spec) is dict and set(spec) == {'cell_id', 'row_ids', 'modes', 'condition'},
                'exact source behavior metric specification')
        case = _cell(definition, spec['cell_id'], spec['condition'], ('regression', 'joint'))
        require(spec['modes'] == (['speed', 'phi', 'th'] if case['kind'] == 'joint' else ['speed']),
                'complete original behavioral mode identity')
        require(type(spec['row_ids']) is list and spec['row_ids'] and
                all(type(x) is str and x for x in spec['row_ids']), 'explicit ordered row IDs')
        total += len(spec['row_ids']) * len(spec['modes'])
        require(total <= cap, 'aggregate scalar admission bound')
        ids.append(spec['cell_id'])
    require(len(ids) == len(set(ids)), 'one metric packet per selected cell')
    metrics = importlib.import_module('run_metrics')
    # Real source function freezes every prediction before invoking this loader.
    result = metrics.grade_behavior(packets, specs, lambda: reader.read(targets), pearson_runtime())
    return {'result': result, 'source_amended_profiles_explicit': True,
            'metadata_bytes': reader.used, 'independent_truth_producer_complete': False,
            'scientifically_qualified': False, 'generic_score_admitted': False}

def generation_metrics(asset_root, prediction, truth, cell_id, condition,
                       max_metadata_bytes, max_events, max_windows):
    _cell(saved_matrix(), cell_id, condition, ('counts',))
    event_cap = positive(max_events, 'event bound')
    window_cap = positive(max_windows, 'window bound')
    reader = Metadata(asset_root, max_metadata_bytes)
    predicted = reader.read(prediction)
    require(type(predicted) is dict and set(predicted) == {'ID', 'dt', 'Trial', 'Interval'},
            'only independently predicted source columns allowed')
    def truth_loader():
        rows = reader.read(truth)
        require(type(rows) is list and 0 < len(rows) <= window_cap, 'complete bounded truth-window list')
        result = []
        count = 0
        for row in rows:
            require(type(row) is dict and set(row) == {'interval', 'trial', 'ids'} and
                    type(row['ids']) is list, 'exact JSON representation of source window truth')
            count += len(row['ids'])
            require(count <= event_cap, 'complete truth-event capacity')
            result.append({'interval': row['interval'], 'trial': row['trial'], 'ids': tuple(row['ids'])})
        return tuple(result)
    native = importlib.import_module('native_dataset')
    metrics = importlib.import_module('run_metrics')
    bodies = native.source_snapshot(SOURCE)
    # Existing grade_generation freezes predicted columns before truth_loader.
    result = metrics.grade_generation(predicted, truth_loader, bodies, generation_runtime(),
                                      max_events=event_cap, max_windows=window_cap)
    return {'cell_id': cell_id, 'condition': condition, 'result': result,
            'metadata_bytes': reader.used, 'selected_paper_figure6_metric': None,
            'independent_window_truth_producer_complete': False,
            'scientifically_qualified': False, 'generic_score_admitted': False}
