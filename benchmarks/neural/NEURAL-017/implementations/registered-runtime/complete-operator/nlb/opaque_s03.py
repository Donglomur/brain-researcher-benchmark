"""Exact operator-only opaque support handoff to the original five S03 views.

Metadata preparation never opens public arrays, the export key, shuffle seed,
targets or comparator. The future S03 worker alone transports the original
protected donor map; no new donor draw, source split or campaign is substituted.
"""
import copy
import hashlib
import json
import re
from .contracts import canonical, closed, descriptor, digest, integer, need, parse, relative
from .programme import CONDITIONS, SHUFFLE_RULE, planned_support

META = ('original_support', 'original_split', 'original_shuffle', 'private_binding', 'export_receipt')
INPUTS = set(META) | {'opaque_public', 'protected_shuffle_seed'}
CAP = 2 * 2**20
AXES = {'train_trial_ids': 1721, 'eval_trial_ids': 574, 'heldin_unit_ids': 137, 'heldout_unit_ids': 45}
SOURCE_PUBLIC = {'bytes': 113599728, 'sha256': '6c4ae66d25a3727fa00927cfee847f60bc84a55de41d5898ad6d4f3c9e48f884'}
SOURCE_FP = 'ba1b50199d8a326e1292b7e36bc6bb694ea8d3d6fa31df7bc910b45268924825'
SOURCE_MANIFEST = 'f913cbbee0bc38173acf0fef5b23dfef8c812af9354e965bfdbadffd20662f3a'
D0 = '56281244725d7062955bd2be6ab7f2393765acda5d6a19702d1c41f369c0eb5c'
SUPPORT = {'training_trials': 1721, 'query_trials': 574, 'bins': 140, 'bin_ms': 5,
           'observed_units': 137, 'withheld_units': 45}


def byte_pin(d):
    return {k: d[k] for k in ('bytes', 'sha256')}


def opaque_digest(value):
    """Original opaque-delivery encoding deliberately has no trailing LF."""
    body = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf8')
    return hashlib.sha256(body).hexdigest()


def sha(value):
    need(type(value) is str and re.fullmatch('[a-f0-9]{64}', value), 'Exact SHA256')
    return value


def selection(value):
    closed(value, {'schema', 'source_manifest', 'inputs', 'opaque_fingerprint',
                   'binding_content_sha256', 'export_implementation', 'export_source_dependencies'})
    need(value['schema'] == 'NLB017_opaque_S03_selection_v1', 'Closed operator S03 selection')
    descriptor(value['source_manifest']); closed(value['inputs'], INPUTS)
    for p in value['inputs'].values(): descriptor(p)
    need(len({p['path'] for p in value['inputs'].values()}) == len(INPUTS), 'Separate fixed input roles')
    need(sum(value['inputs'][k]['bytes'] for k in META) <= CAP, 'Aggregate metadata capture cap')
    need(value['inputs']['protected_shuffle_seed']['bytes'] == 32, 'Original protected shuffle seed extent')
    need(value['inputs']['opaque_public']['bytes'] <= 256 * 2**20, 'Original public archive cap')
    sha(value['opaque_fingerprint']); sha(value['binding_content_sha256'])
    for name in ('export_implementation', 'export_source_dependencies'):
        closed(value[name], {'bytes', 'sha256'}); integer(value[name]['bytes'], 1, 65536); sha(value[name]['sha256'])
    return value


def prepare(selected, captured):
    """Pure metadata transformation over five independently pinned snapshots.

    Captured byte pins retain original D0 provenance, not just its source tag.
    The returned private handoff is a recipe, not authority or native evidence.
    """
    selection(selected); closed(captured, set(META)); docs = {}
    for name in META:
        body = captured[name]; expected = selected['inputs'][name]
        need(type(body) is bytes and len(body) == expected['bytes'] and digest(body) == expected['sha256'],
             'Exact captured metadata identity: ' + name)
        docs[name] = parse(body)
    original = planned_support(docs['original_support'])
    binding = docs['private_binding']; receipt = docs['export_receipt']; split = docs['original_split']
    closed(binding, {'core', 'public_manifest_sha256', 'public_panel_fingerprint'})
    need(opaque_digest(binding) == selected['binding_content_sha256'], 'Independent inverse-map content commitment')
    core = binding['core']
    closed(core, {'schema', 'source_panel_fingerprint', 'source_manifest_sha256', 'axes',
                  'condition_policy', 'key_sha256', 'permutation', 'counts_units'})
    need(core['schema'] == 'NLB017_opaque_delivery_v1' and core['source_panel_fingerprint'] == SOURCE_FP
         and core['source_manifest_sha256'] == SOURCE_MANIFEST and opaque_digest(core) == binding['public_manifest_sha256']
         and binding['public_panel_fingerprint'] == selected['opaque_fingerprint'], 'Original-to-opaque provenance')
    need(core['condition_policy'] == 'original permitted labels retained verbatim and permuted with their trials'
         and core['permutation'] == 'lexicographic opaque ID order separately within each split/axis'
         and core['counts_units'] == 'spikes_per_5ms_bin', 'Unchanged opaque export semantics')
    sha(core['key_sha256']); closed(core['axes'], set(AXES))
    need(receipt['schema'] == 'neural017_opaque_file_export_v1' and receipt['status'] == 'complete'
         and receipt['source'] == SOURCE_PUBLIC and receipt['source_panel_fingerprint'] == SOURCE_FP
         and receipt['public'] == byte_pin(selected['inputs']['opaque_public'])
         and receipt['public_panel_fingerprint'] == selected['opaque_fingerprint']
         and receipt['binding'] == byte_pin(selected['inputs']['private_binding'])
         and receipt['binding_content_sha256'] == selected['binding_content_sha256']
         and receipt['implementation'] == selected['export_implementation']
         and receipt['source_dependencies'] == selected['export_source_dependencies']
         and receipt['support'] == SUPPORT and receipt['condition_policy'] == 'original permitted labels retained'
         and receipt['old_campaign_commitments_valid_for_this_export'] is False
         and receipt['participant_execution_or_native_understanding_established'] is False,
         'Exact complete accepted export operands and scope')
    opaque = copy.deepcopy(original); orders = {}; inverses = {}; aliases = {}
    for name, size in AXES.items():
        axis = core['axes'][name]; closed(axis, {'source', 'opaque_in_source_order'})
        need(axis['source'] == original[name], 'Original support ORDER equals private source axis: ' + name)
        values = axis['opaque_in_source_order']; prefix = 'tr-' if 'trial' in name else 'un-'
        need(type(values) is list and len(values) == size and len(set(values)) == size
             and all(type(x) is str and re.fullmatch(prefix + '[a-f0-9]{32}', x) for x in values),
             'Complete unique typed opaque identities')
        order = sorted(range(size), key=values.__getitem__); inverse = [0] * size
        for new, old in enumerate(order): inverse[old] = new
        orders[name], inverses[name] = order, inverse
        aliases[name] = dict(zip(axis['source'], values))
        opaque[name] = [values[i] for i in order]
    for axis, labels in (('train_trial_ids', 'train_condition_ids'), ('eval_trial_ids', 'eval_condition_ids')):
        need(all(type(x) is str and x for x in original[labels]), 'Original bounded Unicode condition labels')
        opaque[labels] = [original[labels][i] for i in orders[axis]]
    chronology = original['chronological_eval_trial_ids']
    opaque['chronological_eval_trial_ids'] = (None if chronology is None else
        [aliases['eval_trial_ids'][identity] for identity in chronology])
    planned_support(opaque)
    closed(split, {'fit_indices', 'validation_indices', 'descriptor'})
    need(type(split['descriptor']) is dict and split['descriptor'].get('source_split_sha256') == D0,
         'Original independently captured D0 descriptor')
    f, v = split['fit_indices'], split['validation_indices']
    need(type(f) is list and type(v) is list and len(f) == 1381 and len(v) == 340
         and all(type(i) is int for i in f + v) and f == sorted(set(f)) and v == sorted(set(v))
         and sorted(f + v) == list(range(1721)), 'Original full 1381/340 D0 whole-trial partition')
    rebound = {'fit_indices': sorted(inverses['train_trial_ids'][i] for i in f),
               'validation_indices': sorted(inverses['train_trial_ids'][i] for i in v),
               'descriptor': copy.deepcopy(split['descriptor'])}
    old_shuffle = docs['original_shuffle']
    need(old_shuffle['schema'] == 'NLB017_target_free_shuffle_commitment_v2'
         and old_shuffle['planned_support_sha256'] == digest(canonical(original))
         and old_shuffle['rule'] == SHUFFLE_RULE
         and old_shuffle['seed_sha256'] == selected['inputs']['protected_shuffle_seed']['sha256']
         and type(old_shuffle['numpy_version']) is str and old_shuffle['numpy_version'],
         'Original protected shuffle source commitment')
    need(old_shuffle['seed_sha256'] != core['key_sha256'], 'Shuffle seed is not the opaque export key')
    transport = {'schema': 'NLB017_opaque_shuffle_transport_v1',
        'physical_support_sha256': digest(canonical(original)), 'opaque_support_sha256': digest(canonical(opaque)),
        'original_shuffle_sha256': digest(canonical(old_shuffle)),
        'binding_content_sha256': selected['binding_content_sha256'],
        'physical_panel_fingerprint': SOURCE_FP, 'opaque_panel_fingerprint': selected['opaque_fingerprint'],
        'seed_sha256': old_shuffle['seed_sha256'], 'numpy_version': old_shuffle['numpy_version'],
        'rule': 'inverse_q[original_donor[q]]; original draw and original recipient/donor identity pairs preserved'}
    handoff = {'schema': 'NLB017_private_opaque_S03_handoff_v1', 'selection': copy.deepcopy(selected),
        'captured_content_sha256': {name: digest(canonical(doc)) for name, doc in docs.items()},
        'opaque_support_sha256': digest(canonical(opaque)), 'opaque_split_sha256': digest(canonical(rebound)),
        'transport_commitment_sha256': digest(canonical(transport)),
        'full_campaign_admitted': False, 'scientific_or_native_qualified': False}
    return {'support': opaque, 'split': rebound, 'shuffle': transport, 'handoff': handoff}


def mapping_for_s03(body, inputs, public, planned, seed, commitment):
    """Worker-only original-map transport; source data membership is unchanged."""
    closed(body, {'public', 'planned_support', 'shuffle_commitment', 'protected_shuffle_seed', 'opaque_handoff'})
    handoff = parse(inputs.read(body['opaque_handoff'], 65536))
    selected = selection(handoff['selection'])
    need(body['public'] == selected['inputs']['opaque_public']
         and body['protected_shuffle_seed'] == selected['inputs']['protected_shuffle_seed'], 'Exact worker data/seed descriptors')
    captured = {name: inputs.read(selected['inputs'][name], CAP) for name in META}
    prepared = prepare(selected, captured)
    need(canonical(handoff) == canonical(prepared['handoff'])
         and canonical(planned) == canonical(prepared['support'])
         and canonical(commitment) == canonical(prepared['shuffle']), 'Recomputed exact handoff and projected support')
    binding = parse(captured['private_binding']); original = parse(captured['original_support'])
    need(public['panel_fingerprint'] == selected['opaque_fingerprint']
         and str(public['source_manifest_sha256'].item()) == binding['public_manifest_sha256'], 'Current admitted opaque panel identity')
    from .views import shuffle_map
    import numpy as np
    donor = shuffle_map(seed, original, parse(captured['original_shuffle']))
    aliases = binding['core']['axes']['eval_trial_ids']['opaque_in_source_order']
    q = np.asarray(sorted(range(574), key=aliases.__getitem__), dtype=np.int64)
    inverse = np.empty(574, dtype=np.int64); inverse[q] = np.arange(574)
    transported = inverse[donor[q]]
    need(np.array_equal(q[transported], donor[q]) and np.array_equal(np.sort(transported), np.arange(574)),
         'Original recipient/donor relation under exact opaque permutation')
    need(np.array_equal(public['eval_condition_ids'][transported], public['eval_condition_ids']),
         'Original within-condition donors after transport')
    return transported


def original_selection(value):
    closed(value, {'schema', 'source_manifest', 'inputs', 'numpy_version', 'shuffle_status'})
    need(value['schema'] == 'NLB017_original_S03_metadata_selection_v1', 'Original metadata selection')
    descriptor(value['source_manifest'])
    closed(value['inputs'], {'raw_selection', 'raw_D0', 'protected_shuffle_seed'})
    for item in value['inputs'].values(): descriptor(item)
    need(len({p['path'] for p in value['inputs'].values()}) == 3, 'Separate original metadata/seed roles')
    need(byte_pin(value['inputs']['raw_selection']) == {'bytes': 601926, 'sha256': SOURCE_MANIFEST}
         and byte_pin(value['inputs']['raw_D0']) == {'bytes': 10425, 'sha256': D0}, 'Retained original source identities')
    need(value['inputs']['protected_shuffle_seed']['bytes'] == 32, 'Separately selected protected seed descriptor')
    need(type(value['numpy_version']) is str and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', value['numpy_version']), 'Exact selected producer NumPy version')
    need(value['shuffle_status'] == 'prospectively_selected_no_historical_commitment_claim', 'Explicit prospective shuffle selection')
    return value


def original_metadata(selected, captured):
    """Project retained converter metadata; never repeat trial selection or RNG.

    IDs and conditions use full_converter/real-data make_packets encodings. D0
    copies the retained validation identities, not its historical random recipe.
    The donor map is later made by the unchanged original shuffle_map producer.
    """
    original_selection(selected); closed(captured, {'raw_selection', 'raw_D0'}); docs = {}
    for role, body in captured.items():
        item = selected['inputs'][role]
        need(type(body) is bytes and len(body) == item['bytes'] and digest(body) == item['sha256'], 'Exact original capture: '+role)
        docs[role] = parse(body)
    raw, d0 = docs['raw_selection'], docs['raw_D0']
    need(raw['schema_version'] == 1 and raw['dandiset_version'] == '000128/0.220113.0400'
         and raw['asset_id'] == '26e85f09-39b7-480f-b337-278a8f034007'
         and raw['source_sha256'] == 'a27f84f9c31f077011062fd99a6ced199fdf19e656151f056c3c6244a408a3c4'
         and raw['selection_before_spike_values'] is True and raw['all_source_trial_ids_present'] is True
         and raw['observation_masks_identical_within_partition'] is True
         and raw['fixed_bin_ms'] == 5 and raw['fixed_relative_left_edges_ms'] == list(range(-250,450,5)), 'Unchanged original full source')
    rows = raw['selected_trials']
    need(type(rows) is list and len(rows) == 2295 and [x['split'] for x in rows] == ['train']*1721+['val']*574,
         'Original converter train-then-val ordering')
    need(all(type(x['row']) is int and type(x['trial_id']) is int for x in rows)
         and sorted(x['row'] for x in rows) == list(range(2295))
         and len({x['trial_id'] for x in rows}) == 2295, 'Complete original rows and unique physical identities')
    train, query = rows[:1721], rows[1721:]
    for part in (train, query):
        need([x['row'] for x in part] == sorted(x['row'] for x in part), 'Original within-split chronology')
    need(all(type(x['condition']) is list and len(x['condition']) == 2
             and all(type(i) is int for i in x['condition']) for x in rows), 'Original condition pairs')
    trial = lambda x: 'train-nwb:trial-'+str(x['trial_id'])
    support = {'schema':'NLB017_target_free_planned_support_v2',
        'source_release':{'dandiset':'000128','version':'0.220113.0400','asset_id':raw['asset_id'],
                          'raw_bytes':690612247,'raw_sha256':raw['source_sha256']},
        'split_identity':copy.deepcopy(selected['inputs']['raw_selection']),
        'shape':{'training':[1721,140,137,45],'query':[574,140,137,45]},
        'train_trial_ids':[trial(x) for x in train], 'eval_trial_ids':[trial(x) for x in query],
        'train_condition_ids':[json.dumps(x['condition'],separators=(',',':')) for x in train],
        'eval_condition_ids':[json.dumps(x['condition'],separators=(',',':')) for x in query],
        'bin_left_edges_ms':raw['fixed_relative_left_edges_ms'].copy(),
        'chronological_eval_trial_ids':[trial(x) for x in query]}
    for role in ('heldin_unit_ids','heldout_unit_ids'):
        need(type(raw[role]) is list and all(type(i) is int for i in raw[role]), 'Original unit IDs')
        support[role] = ['Jenkins-20090925:unit-'+str(i) for i in raw[role]]
    planned_support(support)
    need(d0['schema_version'] == 1 and d0['candidate_id'] == 'NEURAL-017'
         and d0['train_trial_count'] == 1721 and d0['inner_validation_count'] == 340
         and d0['inner_fit_count'] == 1381 and d0['regenerate_with_new_numpy_version'] is False,
         'Original fixed D0 declaration')
    validation = d0['inner_validation_trial_ids']; train_ids = support['train_trial_ids']
    need(type(validation) is list and len(validation) == len(set(validation)) == 340
         and set(validation) <= set(train_ids), 'Exact original D0 membership, no assessment trials')
    validation_set = set(validation); vi = [i for i,x in enumerate(train_ids) if x in validation_set]
    need([train_ids[i] for i in vi] == validation, 'D0 retained original training row order')
    split = {'fit_indices':[i for i,x in enumerate(train_ids) if x not in validation_set], 'validation_indices':vi,
        'descriptor':{'source_split_sha256':D0, 'source_split':copy.deepcopy(selected['inputs']['raw_D0']),
            'source_selection':copy.deepcopy(selected['inputs']['raw_selection']),
            'original_source':copy.deepcopy(d0['source']), 'original_source_rule':copy.deepcopy(d0['source_rule']),
            'membership':'exact retained 340 validation identities; remaining 1381 original training identities'}}
    shuffle = {'schema':'NLB017_target_free_shuffle_commitment_v2','planned_support_sha256':digest(canonical(support)),
        'seed_sha256':selected['inputs']['protected_shuffle_seed']['sha256'],
        'numpy_version':selected['numpy_version'],'rule':copy.deepcopy(SHUFFLE_RULE)}
    return {'original_support':support, 'original_split':split, 'original_shuffle':shuffle}


def original_main(argv=None):
    """Metadata-only original producer; seed/public/binding bodies are unopened."""
    import argparse
    import sys
    import time
    from pathlib import Path
    from .contracts import Budget, Custody, Store
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root','selection','selection-sha256','output-prefix'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--selection-bytes',type=int,required=True)
    args = parser.parse_args(argv); custody = Custody('original_s03_metadata_prepare')
    budget = Budget(dict(cpu_seconds=60,read_bytes=2*2**20,write_bytes=2**20,stream_bytes=4096,
        model_tokens=0,created_files=4,tool_calls=0),time.monotonic()+60,custody=custody)
    store = Store(Path(args.root),budget,custody)
    selected = parse(store.read({'path':args.selection,'bytes':args.selection_bytes,'sha256':args.selection_sha256},16384))
    original_selection(selected)
    need(getattr(sys,'_nlb017_bootstrap',{}).get('manifest_sha256') == selected['source_manifest']['sha256'],
         'Exact original producer source selection')
    captured = {role:store.read(selected['inputs'][role],CAP) for role in ('raw_selection','raw_D0')}
    made = original_metadata(selected,captured)
    relative(args.output_prefix); output = store.path(args.output_prefix)
    need(output.parent.is_dir() and not output.exists(),'Fresh original metadata output')
    budget.charge('created_files',1); output.mkdir(mode=0o700)
    produced = {role:store.write(args.output_prefix+'/'+role+'.json',canonical(doc),CAP) for role,doc in made.items()}
    response = canonical({'schema':'NLB017_original_S03_metadata_prepared_v1','products':produced,
        'array_or_shuffle_operation_performed':False,'historical_shuffle_commitment_claimed':False,'benchmark_ready':False})
    budget.charge('stream_bytes',len(response)); budget.guard()
    need(sys.stdout.buffer.write(response) == len(response),'Complete bounded original metadata response')
    sys.stdout.buffer.flush(); budget.guard()
    return 0


def main(argv=None):
    """Captured-source metadata preparation only; not an S03 array executor."""
    import argparse
    import sys
    import time
    from pathlib import Path
    from .contracts import Budget, Custody, Store
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'selection', 'selection-sha256', 'output-prefix'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--selection-bytes', type=int, required=True)
    args = parser.parse_args(argv)
    custody = Custody('opaque_s03_metadata_prepare')
    budget = Budget(dict(cpu_seconds=60, read_bytes=4*2**20, write_bytes=2**20,
        stream_bytes=4096, model_tokens=0, created_files=8, tool_calls=0), time.monotonic()+60, custody=custody)
    store = Store(Path(args.root), budget, custody)
    selected = parse(store.read({'path': args.selection, 'bytes': args.selection_bytes,
                                 'sha256': args.selection_sha256}, 16384))
    selection(selected)
    bootstrap = getattr(sys, '_nlb017_bootstrap', {})
    need(bootstrap.get('manifest_sha256') == selected['source_manifest']['sha256'], 'Exact captured source-manifest selection')
    captured = {name: store.read(selected['inputs'][name], CAP) for name in META}
    prepared = prepare(selected, captured)
    relative(args.output_prefix); output = store.path(args.output_prefix)
    need(output.parent.is_dir() and not output.exists(), 'Fresh private metadata output')
    budget.charge('created_files', 1); output.mkdir(mode=0o700)
    produced = {name: store.write(args.output_prefix+'/'+name+'.json', canonical(doc), CAP)
                for name, doc in prepared.items()}
    from .operator_compiler import compile_opaque_s03
    compiled = compile_opaque_s03(selected, produced)
    result = store.write(args.output_prefix+'/S03_COMPILATION.json', canonical(compiled), 65536)
    budget.guard()
    response = canonical({'schema': 'NLB017_opaque_S03_prepared_v1', 'compiled': result,
        'products': produced, 'array_operation_performed': False, 'benchmark_ready': False})
    budget.charge('stream_bytes', len(response))
    need(sys.stdout.buffer.write(response) == len(response), 'Complete bounded metadata response')
    sys.stdout.buffer.flush()
    budget.guard()
    return 0
