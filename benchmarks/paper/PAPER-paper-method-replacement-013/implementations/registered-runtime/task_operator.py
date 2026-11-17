"""Inactive Neuroformer task integration; the central CLI only inspects source.

The Python API is for a trusted serial operator, never a candidate process.
Source availability does not confer execution permission or qualification.
"""
import argparse
from contextlib import contextmanager
import hashlib
import importlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import threading

ROOT = Path(__file__).resolve().parent
TASK = 'PAPER-paper-method-replacement-013'
ONE = 1048576
INVENTORY = (16042, '151a9734eecaf0c6aeff89abc287e45ba9fdc648038c8ce98807f9d65dce589f')
OWNED = {'task_bindings': 'task_bindings.py', 'author_source': 'source/operator/author_source.py', 'collect': 'source/operator/collect.py', 'fixtures': 'source/operator/fixtures.py', 'native_dataset': 'source/operator/native_dataset.py', 'native_plan': 'source/operator/native_plan.py', 'paper_asset': 'source/operator/paper_asset.py', 'prepare': 'source/operator/prepare.py', 'protected_rollout': 'source/operator/protected_rollout.py', 'run_composition': 'source/operator/run_composition.py', 'run_metrics': 'source/operator/run_metrics.py', 'score': 'source/operator/score.py', 'stage': 'source/operator/stage.py', 'stage_pretraining': 'source/operator/stage_pretraining.py', 'test_generated': 'source/operator/test_generated.py', 'test_paper_asset': 'source/operator/test_paper_asset.py', 'array_io': 'source/public/array_io.py', 'contract': 'source/public/contract.py', 'io_contract': 'source/public/io_contract.py', 'metrics': 'source/public/metrics.py', 'panel': 'source/public/panel.py', 'reference_linear': 'source/public/reference_linear.py'}
LOCK = threading.Lock()
AVAILABLE = {
    'inspect_source_matrix': (),
    'verify_original_source': (),
    'plan_native_recipe': ('condition', 'seed'),
    'prepare_native_inputs': ('request', 'array_root'),
    'grade_source_behavior': ('asset_root', 'predictions', 'expected', 'targets', 'max_metadata_bytes', 'max_values'),
    'grade_source_generation_diagnostics': ('asset_root', 'prediction', 'truth', 'cell_id', 'condition', 'max_metadata_bytes', 'max_events', 'max_windows'),
}
MISSING = {'native_fit_and_behavior_execution': 'No fixed original model/Trainer/decoder/RNG/DataLoader runtime factory or configuration/training/selection/query providers bind operator assets to ReleasedCalls and dispatch_native. The existing dispatcher structurally admits five continuous cells; no missing recipe is filled by metadata.', 'protected_rollout_execution': 'Protected generated-history source is implemented, but the file-to-protected split/exogenous query provider and owned fitted config/run/checkpoint identity binder are missing. Ten component-available count cells are not accepted by dispatch_native.', 'produce_independent_evaluation_truth': 'window_truth exists for an original dataset/tokenizer; no fixed file-to-selected protected evaluation dataset/window factory or independent target issuance is installed.', 'medial_original_configuration': 'Only lateral configurations are captured. Explicit lateral-on-medial source paths are not authenticated original medial configurations.', 'comparator_fitting': 'Original Lasso/GLM fitting recipes and exact MLP/bidirectional-GRU configuration/run mappings remain missing; flags do not supply those methods.', 'classification': 'Original class quantizer, native classification decode and paper metric/support mapping remain missing; no prospective25-class substitution.', 'fewshot_pretrained_scratch': 'Actual paired pretrained/scratch fine-tuning and10percent recipe remain missing; released training still uses train_dataset.', 'original_neural_ablations': 'Current/past/video/behavior/contrastive labels do not bind original configurations, runs or neural metric selection.', 'figure6_paper_metric_selection': 'Both original source diagnostic branches are available, but Figure6 branch/window/token/event conversion and paper run support remain unselected.', 'prospective_candidate_execution': 'The existing5ms dispatcher requires a full46-case query/submission and a fixed operator runner/bridge admission binding. It is not a10ms-to5ms conversion or a seven-case task.', 'paired_candidate_contexts': 'Equal paper/data versus approved author-code contexts, independent process/mount isolation and protected target exclusion are not assembled by this package.', 'run': 'No complete fixed native/candidate scientific benchmark controller is installed.', 'score': 'Source metric APIs are available; complete protected benchmark scoring/independent reference issuance and qualification are not installed.', 'wider_simulation': 'Complete original simulation family remains in scope; its task-specific recipe/caller/data/reference qualification is not assembled here.', 'wider_passive_control': 'Complete original passive control family remains in scope; its task-specific recipe/caller/data/reference qualification is not assembled here.', 'wider_variability': 'Complete original variability family remains in scope; its task-specific recipe/caller/data/reference qualification is not assembled here.', 'wider_geometry': 'Complete original geometry family remains in scope; its task-specific recipe/caller/data/reference qualification is not assembled here.', 'wider_representation_probing': 'Complete original representation probing family remains in scope; its task-specific recipe/caller/data/reference qualification is not assembled here.', 'wider_cebra': 'Complete original CEBRA family remains in scope; its task-specific recipe/caller/data/reference qualification is not assembled here.', 'wider_training_curves': 'Complete original training curves family remains in scope; its task-specific recipe/caller/data/reference qualification is not assembled here.'}
HOLDS = ['All46 slots,85 cells and seven wider families remain unqualified; source availability is not a scientific result.', 'Historical10ms released behavior, protected source-amended10ms, and existing prospective5ms conditions remain distinct.', 'Original generated-history override defect and original test-selection/first200 metric behavior remain preserved.', 'Protected empty initial history, generated ID/time pairing, episode resets and target-free current tokens are explicit source amendments, not recovered ablation recipes.', 'Authentic complete inputs/provenance, physical clocks/units, original run/seed/config/split identity and native numerical parity remain unqualified.', 'Normal Python imports reopen verified trusted source paths; immutable coherent source/input/checkpoint consumption and native environment identity remain external holds.', 'Physical candidate/query/target containment, trusted checkpoint ownership and independent reference issuance remain unqualified.', 'Source-code publication does not grant data, paper or weight redistribution/exposure rights; the external paper body is not bundled.', 'No fixed full fit/query/checkpoint provider is inferred from source signatures or lack of a scientific run.']

class UnavailableRoute(RuntimeError):
    pass

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
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite metadata')))

def capture(path, expected):
    path = Path(path)
    require(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)),
            'absolute ordinary source path without aliases required')
    n, sha = expected
    require(type(n) is int and 0 <= n <= ONE, 'bounded ordinary source extent required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        first = os.fstat(fd)
        require(stat.S_ISREG(first.st_mode) and first.st_nlink == 1 and first.st_size == n,
                'exact regular single-link source extent required')
        with os.fdopen(fd, 'rb', closefd=False) as handle:
            body = handle.read(n + 1)
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        require(identity(first) == identity(os.fstat(fd)) == identity(path.lstat()), 'source changed during capture')
        require(len(body) == n and hashlib.sha256(body).hexdigest() == sha, 'exact source hash required')
        body.decode('utf8');require(b'\0' not in body, 'ordinary text source required')
        return body
    finally:
        os.close(fd)

def admit_source():
    inventory = parse(capture(ROOT / 'TASK_SOURCE_INVENTORY.json', INVENTORY))
    require(inventory['count'] == len(inventory['files']) == 89, 'all87 source roles plus canonical and fixed binding required')
    selected = set()
    for row in inventory['files']:
        name = row['path'];p = PurePosixPath(name)
        require(not p.is_absolute() and p.as_posix() == name and '\\' not in name and
                all(x not in ('', '.', '..') for x in name.split('/')) and name not in selected,
                'unique canonical source member')
        capture(ROOT / name, (row['bytes'], row['sha256']));selected.add(name)
    actual = set()
    for current, directories, files in os.walk(ROOT / 'source', followlinks=False):
        require(not any((Path(current) / n).is_symlink() for n in directories), 'source directory alias')
        actual.update(str((Path(current) / n).relative_to(ROOT)) for n in files)
    require(actual == {n for n in selected if n.startswith('source/')}, 'exact source tree, no extra source/pyc files')
    return inventory

@contextmanager
def normal_operator_modules():
    """Fixed ordinary imports in a trusted source tree; no sandbox/custody claim.

    Source was authenticated before normal Python import reopens it. External
    immutability/containment and native environment identity remain explicit holds.
    """
    require(LOCK.acquire(blocking=False), 'serial non-reentrant operator required')
    old_path = list(sys.path);old_bytecode = sys.dont_write_bytecode
    before = set(sys.modules)
    try:
        require(not any(n in sys.modules for n in OWNED), 'preloaded task source namespace refused')
        admit_source()
        sys.path[:0] = [str(ROOT), str(ROOT / 'source/operator'), str(ROOT / 'source/public')]
        sys.dont_write_bytecode = True
        yield importlib.import_module('task_bindings')
        for name in set(sys.modules) - before:
            if name in OWNED:
                require(Path(sys.modules[name].__file__).resolve() == ROOT / OWNED[name], 'task import outside fixed owned layout')
    finally:
        for name in set(sys.modules) - before:
            if name in OWNED:
                del sys.modules[name]
        sys.path[:] = old_path
        sys.dont_write_bytecode = old_bytecode
        LOCK.release()

def dispatch(operation, request):
    if operation in MISSING:
        raise UnavailableRoute(MISSING[operation])
    require(operation in AVAILABLE, 'unknown source route')
    require(type(request) is dict and set(request) == set(AVAILABLE[operation]), 'exact source route request keys')
    with normal_operator_modules() as binding:
        if operation == 'inspect_source_matrix': value = binding.matrix()
        elif operation == 'verify_original_source': value = binding.verify_source()
        elif operation == 'plan_native_recipe': value = binding.recipe(**request)
        elif operation == 'prepare_native_inputs': value = binding.prepare_inputs(**request)
        elif operation == 'grade_source_behavior': value = binding.behavior_metrics(**request)
        else: value = binding.generation_metrics(**request)
    return {'task_id': TASK, 'operation': operation, 'result': value,
            'source_complete': False, 'runnable': False, 'scientifically_qualified': False,
            'generic_execution_admitted': False, 'holds': list(HOLDS)}

def inspect_definition():
    matrix = dispatch('inspect_source_matrix', {})['result']
    require(matrix['unique_case_slots'] == 46 and matrix['condition_cells'] == 85 and
            len(matrix['wider_families']) == 7, 'complete canonical source scope')
    require(all(cell['ready'] is False for row in matrix['rows'] for cell in row['cells']), 'all source cells remain unqualified')
    return {'schema': 'neuroformer_inactive_task_inspection_v1', 'id': TASK,
        'matrix': matrix, 'source_roles_preserved': 74, 'published_bodies_preserved': 87,
        'available_source_apis': {name: list(keys) for name, keys in AVAILABLE.items()},
        'unavailable_routes': dict(MISSING), 'holds': list(HOLDS),
        'source_complete': False, 'full_contract_complete': False, 'runnable': False,
        'research_qualified': False, 'submission_ready': False,
        'run': None, 'score': None, 'program_execution': None,
        'registration_performed_by_inspection': False, 'qualified_benchmarks': 0,
        'assignment_scope': 1, 'source_conditions_are_not_new_assignments': True}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('inspect',))
    parser.parse_args(argv)
    result = inspect_definition()
    print(json.dumps(result, sort_keys=True))
    return result

if __name__ == '__main__':
    main()
