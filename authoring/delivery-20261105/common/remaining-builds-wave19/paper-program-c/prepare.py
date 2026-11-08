"""Executable future full-fold preparation; never called on data in BUILD.

Whole-run AE and pooled training PCA are retrospective scientific preprocessing.
This module grants no authority to perform them. Its inputs are operator-owned
primitive regional observations, not original archives or fitted native models.
"""
from pathlib import Path
from core import HMM, TASK, CONTROLS, need, validate_runs, identity, encoded
from safe_io import array, write_array, new_json
import representation


def build(packet, input_root, expected_packet_identity, branch, fold, output, budget):
    need(identity(packet) == expected_packet_identity, 'Externally frozen complete original input metadata')
    need(packet['task_id'] == TASK and packet['branch'] == branch and branch in HMM,
         'Exact branch input packet')
    need(packet['sampling_frequency'] == HMM[branch][2]
         and packet['channels'] == (1 if branch == 'ctf_bursts' else 38)
         and type(packet['original_preparation_binding']) is str
         and len(packet['original_preparation_binding']) == 64,
         'Original supplied sample grid/channels and authenticated preparation lineage')
    validate_runs(packet['runs'], branch)
    need(set(budget) == {'array_bytes', 'output_bytes'} and
         all(type(v) is int and v > 0 for v in budget.values()), 'Prospective explicit preparation allocation')
    output = Path(output)
    need(not output.exists() and not output.is_symlink(), 'Fresh operator preparation output')
    output.mkdir()
    from core import runs
    train_ids = set(runs(branch, fold, 'train'))
    training, queries = [], []
    for r in packet['runs']:
        x = array(input_root, r['observations'], budget['array_bytes'])
        need(x.ndim == 2 and x.shape[1] == packet['channels'], 'Full original supplied run axes')
        row = {'person': r['person'], 'run': r['run'], 'observations': x}
        (training if (r['person'], r['run']) in train_ids else queries).append(row)
    state = representation.fit(training, branch, fold)
    written = 0
    def save(path, x):
        nonlocal written
        d = write_array(path, x, min(budget['array_bytes'], budget['output_bytes']-written))
        written += d['bytes']
        d['path'] = str(path.relative_to(output))
        return d
    state_files = {k: save(output/(k+'.npy'), state[k])
                   for k in ('anchor', 'offset', 'scale', 'projection')}
    state_descriptor = {k: state[k] for k in ('profile', 'branch', 'fold', 'training_runs')}
    state_descriptor['arrays'] = state_files
    representation_id = identity(state_descriptor)
    controls = {}
    for control in CONTROLS:
        directory = output/control
        directory.mkdir()
        rows = representation.training_control(training, state, control)
        controls[control] = [{'person': r['person'], 'run': r['run'],
                              'observations': save(directory/(str(i)+'.npy'), r['observations'])}
                             for i, r in enumerate(rows)]
    private = output/'operator_private_query'
    private.mkdir()
    rows = representation.query(queries, state)
    query_rows = [{'person': r['person'], 'run': r['run'],
                   'observations': save(private/(str(i)+'.npy'), r['observations'])}
                  for i, r in enumerate(rows)]
    manifest = {'schema': 'osl_full_fold_preparation_v1', 'task_id': TASK,
                'branch': branch, 'fold': fold, 'input_identity': expected_packet_identity,
                'representation': state_descriptor, 'representation_id': representation_id,
                'training_controls': controls, 'operator_private_query': query_rows,
                'numeric_bytes_written': written,
                'candidate_mount': 'One control training list only; never this operator union',
                'query_adaptation': False, 'native_representation_equivalence': False,
                'scientific_qualification': False}
    # The completion record is written only after every required run/control.
    need(written + len(encoded(manifest)) <= budget['output_bytes'],
         'Completion metadata included in original output allocation')
    new_json(output/'PREPARATION.json', manifest)
    return manifest


def training_view(preparation, control, role):
    need(control in CONTROLS and role in ('A', 'B', 'reference'), 'Exact fresh view')
    rows = preparation['training_controls'][control]
    validate_runs(rows, preparation['branch'], preparation['fold'], 'train')
    return {'schema': 'osl_training_view_v1', 'task_id': TASK, 'role': role,
            'branch': preparation['branch'], 'fold': preparation['fold'], 'control': control,
            'representation_id': preparation['representation_id'], 'runs': rows,
            'query_observations_included': False,
            'original_input_identity': preparation['input_identity']}
