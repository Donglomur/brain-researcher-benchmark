"""NEURAL-095: admit closed viewer and frozen-programme products before grading.

Operator-side only. The programme operand must be the NEW ungraded owner mode;
historical four-cell scored operations are not accepted or relabelled here.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import sys
import types

import numpy as np

HERE = Path(__file__).resolve().parent
VIEWS = ('cue_only', 'neural')
ACCESS = ('restricted_count_viewer', 'frozen_program')
PROGRAMME_MODE = 'frozen_pair_ungraded/v1'
POLICY_SCHEMA = 'neural095-cross-access-policy/v1'
DEPENDENCIES = {
    'participant-transport-v1/transport.py':
        (29465, '35f527f6b225080d32aae261c082d7529b5fc5d472a09eb1052e6f6672a9a6e5'),
    'participant-transport-v1/SOURCE_BINDINGS.json':
        (348, 'eee8c29e0d06bc5193de665c0806c48522a252d02ac50ea4077b6e9e4465d456'),
}


def need(ok, why):
    if not ok:
        raise ValueError(why)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def source_capture(path, expected):
    path = Path(path).absolute()
    need(type(expected) is dict and set(expected) == {'bytes', 'sha256'}
         and type(expected['bytes']) is int and 0 < expected['bytes'] <= 262144,
         'Bounded externally selected source descriptor')
    need('..' not in path.parts and all(not p.is_symlink() for p in (path, *path.parents)), 'Ordinary source dependency')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == expected['bytes'],
             'Exact single-link source size')
        with os.fdopen(fd, 'rb', closefd=False) as handle:
            body = handle.read(expected['bytes'] + 1)
        after = os.fstat(fd)
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink')
        need(all(getattr(before, key) == getattr(after, key) for key in fields) and pin(body) == expected,
             'Stable exact source dependency')
        return body
    finally:
        os.close(fd)


def captured_module(path, name, body, injected=None):
    result = types.ModuleType(name); result.__file__ = str(path)
    result.__dict__.update(injected or {}); sys.modules[name] = result
    exec(compile(body, str(path), 'exec'), result.__dict__)
    return result


def dependencies(implementations, local_sources):
    """Execute captured selected bytes; no hash-then-reopen code import.

The two local pins come from the operator's independently reviewed source map.
They are not inferred from a collection's own assertions. The original transport
bootstrap statement is replaced by its exact captured viewer module; its
functions and public/participant checks remain the original source.
"""
    root = Path(implementations).absolute()
    bodies = {name: source_capture(root / name, {'bytes': size, 'sha256': digest})
              for name, (size, digest) in DEPENDENCIES.items()}
    binding = json.loads(bodies['participant-transport-v1/SOURCE_BINDINGS.json'])
    need(binding['schema'] == 'neural095-participant-transport-dependencies/v1'
         and set(binding['members']) == {'viewer.py', 'SOURCE.json'}, 'Exact viewer dependency roles')
    viewer_root = root / 'count-viewer-v1'
    viewer_sources = {name: source_capture(viewer_root / name, expected)
                      for name, expected in binding['members'].items()}
    viewer = captured_module(viewer_root / 'viewer.py', '_n095_cross_viewer', viewer_sources['viewer.py'])
    original_capture = viewer.capture
    def viewer_capture(path, cap=1024**2):
        if Path(path).absolute() == viewer_root / 'SOURCE.json':
            need(len(viewer_sources['SOURCE.json']) <= cap, 'Manifest capture bound')
            return viewer_sources['SOURCE.json']
        return original_capture(path, cap)
    viewer.capture = viewer_capture
    source = bodies['participant-transport-v1/transport.py']
    bootstrap = b'\nv=load_viewer()\n'
    need(source.count(bootstrap) == 1, 'Exact original transport bootstrap seam')
    prefix, suffix = source.split(bootstrap)
    transport = captured_module(root / 'participant-transport-v1/transport.py', '_n095_cross_transport',
        prefix + b'\n# Captured pinned viewer injected by the source-only adapter.\n' + suffix,
        {'v': viewer})
    original_read = transport.read
    cached = {root / name: body for name, body in bodies.items()}
    def transport_read(path, cap):
        if Path(path).absolute() in cached:
            body = cached[Path(path).absolute()]; need(len(body) <= cap, 'Source capture bound'); return body
        return original_read(path, cap)
    transport.read = transport_read
    need(type(local_sources) is dict and set(local_sources) == {'frozen_owner.py', 'frozen_collection.py'},
         'Both independently selected new collection source members')
    local = {name: source_capture(HERE / name, expected) for name, expected in local_sources.items()}
    collection = captured_module(HERE / 'frozen_collection.py', '_n095_cross_collection', local['frozen_collection.py'])
    owner = captured_module(HERE / 'frozen_owner.py', '_n095_cross_owner', local['frozen_owner.py'],
                            {'COLLECTION_SOURCE': local['frozen_collection.py'], 'COLLECTION': collection})
    return transport, owner


def viewer_collection(transport, packets, sessions, collection):
    """Use the existing closed-process audit and original exact replay once."""
    receipts, histories = transport.audit_pair(packets, sessions)
    vectors, receipt = transport.v.validate_collection(packets, histories, collection)
    expected = {
        'schema': 'neural095-participant-collection/v1',
        'status': 'both_closed_views_collected', 'mode': transport.v.MODE,
        'queries_per_view': 258, 'sessions': receipts,
        'original_collection': transport.pin(transport.v.encoded(receipt)),
        'source': transport.source_identity(), 'provider_context_qualified': False,
        'scientific_qualification': False,
    }
    actual = transport.decode(transport.read(Path(collection) / 'TRANSPORT_COMPLETE.json', transport.v.MAX_HISTORY))
    need(actual == expected, 'Exact existing closed viewer collection')
    return vectors, receipt, receipts, expected


def public_inputs(rows):
    """Preserve original mounted input roles, including labels and clocks."""
    names = ('train.npz', 'query.npz', 'schema.json', 'units.json', 'contract.json')
    need(type(rows) is list and len(rows) == 5, 'All five original public input commitments')
    result = {}
    for row, name in zip(rows, names):
        need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256', 'mount_destination', 'read_only'}
             and row['mount_destination'] == '/input/' + name and row['read_only'] is True,
             'Exact ordered original public input roles')
        need(type(row['bytes']) is int and row['bytes'] > 0 and type(row['sha256']) is str
             and len(row['sha256']) == 64 and all(c in '0123456789abcdef' for c in row['sha256']),
             'Finite public input identity')
        result[name] = {key: row[key] for key in ('bytes', 'sha256')}
    return result


def actual_policy(transport, viewer_receipts, programme):
    """Distinct inference methods; same measurements do not make methods equal."""
    boundaries = [viewer_receipts[view]['boundary'] for view in VIEWS]
    shared = ('client', 'limits', 'sandbox', 'source', 'fresh_process_per_view', 'stateful_within_view')
    need(all({k: b[k] for k in shared} == {k: boundaries[0][k] for k in shared} for b in boundaries),
         'One declared viewer method across views')
    boundary = boundaries[0]
    return {
        'schema': POLICY_SCHEMA, 'candidate_id': 'NEURAL-095',
        'support': {'training': 748, 'query': 258, 'units': 40, 'pre_set_bins': 4,
                    'bin_edges_ms': [-200, -150, -100, -50, 0]},
        'restricted_count_viewer': {
            'condition': transport.v.MODE, 'representation': 'cue_metadata_and_lossless_count_table_png',
            'method': 'stateful_typed_view_navigation_and_answers',
            **{k: boundary[k] for k in shared},
        },
        'frozen_program': {
            'condition': PROGRAMME_MODE, 'representation': 'original_numeric_train_and_query_arrays',
            'method': 'train_only_prepare_then_one_frozen_full_query_batch',
            **{k: programme[k] for k in ('program', 'method_document', 'actor', 'policy', 'resource_policy')},
        },
        'matched_method_claimed': False, 'tools_only_causal_effect_claimed': False,
    }


def admit(*, transport, owner, packets, sessions, collection, programme_root,
          programme_selection, policy_body, policy_pin):
    """Capture all four complete prediction vectors without protected operands.

The transport/owner arguments are trusted source modules loaded by dependencies,
not participant plugins. Generated tests replace custody boundaries explicitly.
"""
    need(type(policy_body) is bytes and pin(policy_body) == policy_pin, 'Explicit selected policy bytes')
    policy = transport.decode(policy_body)
    viewer_vectors, viewer_receipt, viewer_receipts, closed_viewer = viewer_collection(
        transport, packets, sessions, collection)
    programme = owner.validate_closed(programme_root, programme_selection)
    ids = packets['cue_only'].ids
    need(type(ids) is list and len(ids) == 258 and len(set(ids)) == 258
         and programme['case_ids'] == ids, 'Same complete original ordered query roster')
    transport.v.pair_packets(packets)
    need(programme['mode'] == PROGRAMME_MODE and programme['status'] == 'closed_ungraded',
         'Only prospective closed ungraded programme collections')
    for view in VIEWS:
        need(public_inputs(programme['public_inputs'][view]) == packets[view].pins,
             'Identical complete training labels/cues/query/counts/schema/units/contract commitments')
    need(policy == actual_policy(transport, viewer_receipts, programme), 'Selected typed method policy differs from delivery')
    validator = packets['cue_only'].sources.modules['validator']
    vectors = {'restricted_count_viewer': {}, 'frozen_program': {}}
    submissions = {'restricted_count_viewer': viewer_receipt['submissions'], 'frozen_program': {}}
    for view in VIEWS:
        path = programme['submission_paths'][view]
        before = transport.read(path, validator.MAX_FILE_BYTES)
        need(before == programme['submissions'][view]['body']
             and pin(before) == programme['submissions'][view]['pin'], 'Programme captured bytes changed before validation')
        ordered = validator.validate(path, ids)
        need(transport.read(path, validator.MAX_FILE_BYTES) == before, 'Programme changed during public validation')
        submissions['frozen_program'][view] = pin(before)
        vectors['frozen_program'][view] = np.asarray(ordered, dtype=np.float64).copy()
        vectors['restricted_count_viewer'][view] = np.asarray(viewer_vectors[view], dtype=np.float64).copy()
    for access in ACCESS:
        for view in VIEWS:
            value = vectors[access][view]
            need(value.shape == (258,) and np.isfinite(value).all(), 'Every product has all 258 finite predictions')
            value.flags.writeable = False
    receipt = {
        'schema': 'neural095-cross-access-admission/v1', 'status': 'four_complete_products_admitted_ungraded',
        'candidate_id': 'NEURAL-095', 'case_ids': ids.copy(), 'submissions': submissions,
        'viewer_collection': pin(transport.encode(closed_viewer)), 'programme_closure': programme['closure'],
        'public_inputs': {view: packets[view].pins for view in VIEWS},
        'common_members': packets['cue_only'].common, 'units': list(packets['cue_only'].units),
        'policy': policy_pin, 'private_target_reads': 0, 'private_reference_reads': 0,
        'historical_scored_programme_accepted': False, 'research_qualified': False,
    }
    return vectors, receipt


def evaluate(*, transport, owner, packets, sessions, collection, programme_root,
             programme_selection, policy_body, policy_pin, reference_loader, private_loader):
    """One protected load only after both closures and all four public products."""
    vectors, admission = admit(transport=transport, owner=owner, packets=packets, sessions=sessions,
        collection=collection, programme_root=programme_root, programme_selection=programme_selection,
        policy_body=policy_body, policy_pin=policy_pin)
    references = reference_loader()
    private = private_loader()
    need(type(private) is dict and set(private) == {'case_id', 'tp_ms', 'condition', 'context'}
         and np.asarray(private['case_id']).tolist() == admission['case_ids'], 'Exact private/public query identity order')
    for key in ('condition', 'context'):
        need(np.array_equal(private[key], packets['cue_only'].arrays['query'][key]), 'Original private/public cue join')
    sources = packets['cue_only'].sources.modules
    arms, paired = {}, {}
    for access in ACCESS:
        arms[access] = {view: sources['metrics'].score_candidate(vectors[access][view], lambda: private, references)
                        for view in VIEWS}
        difference = sources['paired'].pair_difference(vectors[access]['cue_only'], vectors[access]['neural'],
            private['tp_ms'], private['condition'], private['context'])
        checks = sources['paired'].verify_paired_arithmetic(difference,
            arms[access]['cue_only']['candidate'], arms[access]['neural']['candidate'])
        paired[access] = {'cue_minus_neural': difference, 'arithmetic_checks': len(checks)}
    access_differences = {}
    for view in VIEWS:
        original = sources['paired'].pair_difference(vectors['restricted_count_viewer'][view],
            vectors['frozen_program'][view], private['tp_ms'], private['condition'], private['context'])
        checks = sources['paired'].verify_paired_arithmetic(original,
            arms['restricted_count_viewer'][view]['candidate'], arms['frozen_program'][view]['candidate'])
        # Reuse the exact arithmetic, but never mislabel access modes as cue and
        # neural. This is a finite-panel capability contrast, not a tool effect.
        def relabel(value):
            if type(value) is dict:
                return {key.replace('cue_minus_neural', 'viewer_minus_frozen_program'): relabel(item)
                        for key, item in value.items()}
            return value
        renamed = relabel(original)
        renamed['sign'] = 'positive means frozen programme lower absolute error on this finite panel'
        access_differences[view] = {'viewer_minus_frozen_program': renamed, 'arithmetic_checks': len(checks)}
    return {
        'schema': 'neural095-cross-access-grade/v1', 'status': 'four_products_scored',
        'candidate_id': 'NEURAL-095', 'admission': pin(encoded(admission)), 'arms': arms,
        'within_access_neural_increment': paired, 'descriptive_between_access_difference': access_differences,
        'reference_loader_calls': 1, 'private_loader_calls': 1, 'new_reference_fits': 0,
        'cases_per_product': 258, 'training_cases_available': 748,
        'query_target_access_before_all_four_admission': False,
        'same_input_commitments': True, 'same_representation': False, 'same_inference_method': False,
        'same_resource_budget': False,
        'cross_access_policy_preregistration_proven': False, 'provider_context_qualified': False,
        'external_no_tools_enforcement_proven': False, 'native_understanding_proven': False,
        'tools_only_causal_effect_claimed': False, 'research_qualified': False,
        'scope': 'One exposed animal/session; all results require actual separately admitted participant runs',
    }


def evaluate_paths(*, implementations, local_sources, public_inputs_by_view, sessions, collection,
                   programme_root, programme_selection, policy_path, policy_pin, evaluator_paths):
    """Concrete operator entry point for a later separately admitted study.

This function DOES read the selected public neural arrays and eventually the
protected evaluator inputs. Source construction/tests do not call it on real
inputs. Constructing the original loaders does not read protected operands.
    """
    transport, owner = dependencies(implementations, local_sources)
    need(set(public_inputs_by_view) == set(VIEWS), 'Both original complete public views')
    sources = transport.v.Sources()
    packets = {view: transport.v.Packet(view, public_inputs_by_view[view], sources) for view in VIEWS}
    policy_body = transport.read(policy_path, 65536)
    references, private = transport.v.loaders(sources, evaluator_paths, packets['cue_only'].ids)
    return evaluate(transport=transport, owner=owner, packets=packets, sessions=sessions,
        collection=collection, programme_root=programme_root, programme_selection=programme_selection,
        policy_body=policy_body, policy_pin=policy_pin, reference_loader=references, private_loader=private)
