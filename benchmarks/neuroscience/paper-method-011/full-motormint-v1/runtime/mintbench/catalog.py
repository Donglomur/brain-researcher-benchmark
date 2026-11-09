"""Complete scientific scope plus source-defined, non-empirical output schedules."""
from pathlib import Path
from .validation import decode, digest, need

ROOT = Path(__file__).resolve().parent.parent
MODULES = ('concept_and_algorithm', 'cycle_geometry', 'network_ground_truth',
           'primary_behavior', 'library_distance', 'hyperparameter_sensitivity',
           'factorial_ablations', 'threshold_crossings', 'averaged_training_control',
           'cycle_direction_generalization', 'pacman_generalization', 'nlb_neural_state',
           'small_training_sets', 'neuron_loss', 'maze_simulations', 'cost_and_scaling',
           'rtt_pseudocondition_accuracy_cost')
PRIMARY = ('Area2_Bump', 'MC_Cycle', 'MC_Maze', 'MC_RTT')
NEURON_COUNTS = (1, 2, 3, 4, 5, *range(10, 161, 5), 162)
KINDS = {
    'concept_and_algorithm': ('documentary',),
    'cycle_geometry': ('cycle_geometry', 'documentary'),
    'network_ground_truth': ('behavior', 'geometry'),
    'primary_behavior': ('behavior',),
    'library_distance': ('nearest_library', 'documentary'),
    'hyperparameter_sensitivity': ('behavior', 'contrasts'),
    'factorial_ablations': ('behavior', 'contrasts'),
    'threshold_crossings': ('behavior', 'contrasts'),
    'averaged_training_control': ('behavior', 'contrasts'),
    'cycle_direction_generalization': ('behavior',),
    'pacman_generalization': ('behavior', 'distribution', 'documentary'),
    'nlb_neural_state': ('neural_state', 'psth', 'behavior'),
    'small_training_sets': ('behavior',),
    'neuron_loss': ('behavior', 'neuron_loss_curve'),
    'maze_simulations': ('behavior', 'documentary'),
    'cost_and_scaling': ('cost',),
    'rtt_pseudocondition_accuracy_cost': ('behavior', 'contrasts', 'cost', 'documentary'),
}


def scope():
    value = decode((ROOT / 'SCOPE.json').read_bytes())
    need(tuple(m['id'] for m in value['modules']) == MODULES, 'all17original modules in order')
    need(len(value['datasets']) == 9 and value['full_paper_target'] is True, 'full nine-dataset scope')
    return value


def gaps():
    value = decode((ROOT / 'GAP_REGISTER.json').read_bytes())
    need(len(value['gaps']) == 17 and len({g['id'] for g in value['gaps']}) == 17, 'all17original gates')
    return value


def signature():
    return digest({'scope': scope(), 'gaps': gaps(), 'kinds': KINDS})


def primary_slots():
    for dataset in PRIMARY:
        for method, repeats in [('MINT', 1), ('Wiener_filter', 1), ('Kalman_filter', 1),
                                ('feedforward', 10), ('GRU', 10)]:
            for repeat in range(repeats):
                yield {'id': f'{dataset}:{method}:{repeat}', 'dataset': dataset,
                       'method': method, 'repeat': repeat}
    yield {'id': 'MC_Maze:Naive_Bayes_regression:0', 'dataset': 'MC_Maze',
           'method': 'Naive_Bayes_regression', 'repeat': 0}


def ablation_cells():
    data = {d['id']: d for d in scope()['datasets']}
    for dataset in PRIMARY:
        dimensions = sum(int(g.split(':')[-1]) for g in data[dataset]['behavior']['groups'])
        for readout in ('direct', 'linear'):
            for interpolation in ('on', 'off'):
                for direction in ('causal', 'acausal'):
                    for dimension in range(dimensions):
                        if dataset == 'MC_Cycle' and dimension == 0 and readout == 'linear':
                            continue  # Source-defined phase exclusion, not candidate masking.
                        yield f'{dataset}:{readout}:{interpolation}:{direction}:{dimension}'


def loss_cells():
    for count in NEURON_COUNTS:
        for repetition in range(50):
            for regime in ('known', 'undetected'):
                for method in ('MINT', 'Wiener_filter'):
                    for group in ('position', 'velocity'):
                        yield f'{count}:{repetition}:{regime}:{method}:{group}'


def nlb_cells():
    for dataset in scope()['datasets']:
        if dataset['nlb']:
            for metric in dataset['nlb']['metrics']:
                yield f'{dataset["id"]}:{metric}'


def required_support(module):
    """Known finite keys; None means source-defined historical roster still required.

    None never means optional or empty. Admission requires an independent exact
    support manifest plus applicable gate evidence for every module.
    """
    need(module in MODULES, 'canonical module')
    if module=='cycle_geometry':
        return [f'cycle:{kind}:{axis}' for kind in ('joint','ordering') for axis in ('muscle','kinematic','partition')]+['cycle:projection']
    if module == 'primary_behavior':
        return [s['id'] for s in primary_slots()]
    if module == 'factorial_ablations':
        return list(ablation_cells())
    if module == 'neuron_loss':
        return list(loss_cells())
    if module == 'nlb_neural_state':
        return list(nlb_cells())  # Required MINT endpoints; comparator roster bound separately.
    return None


def coverage():
    return {'task': 'PAPER-paper-method-011', 'modules': list(MODULES), 'datasets': 9,
            'primary_run_bundles': sum(1 for _ in primary_slots()),
            'ablation_R2_cells': sum(1 for _ in ablation_cells()),
            'neuron_counts': len(NEURON_COUNTS), 'neuron_loss_group_R2_cells': sum(1 for _ in loss_cells()),
            'nlb_MINT_endpoints': sum(1 for _ in nlb_cells()),
            'original_gates': [g['id'] for g in gaps()['gaps']],
            'scope_sha256': signature(), 'scientifically_qualified': False,
            'note': 'Schedules are source-derived metadata, not observations or benchmark counts.'}
