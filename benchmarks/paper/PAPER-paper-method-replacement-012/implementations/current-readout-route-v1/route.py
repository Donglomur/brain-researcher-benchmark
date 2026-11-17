"""Additive current-source NuCLR transductive route and supplemental receipts.

Selection reads metadata only. Numerical execution delegates to the unchanged
authenticated evaluator and requires a separately authorized operation. These
objects/receipts are provenance records, not a process-isolation capability or
proof that native arrays, representations or scientific comparators qualify.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
from types import ModuleType, MappingProxyType
import uuid

HERE = Path(__file__).resolve().parent
ROUTE_ID = 'multi_split_resample_transductive_v1'
ADOPTION_SHA256 = '206bc6284ea431d66cc61687c1c13e70f74f891195f213e11d7bbd7320ca24a0'
READER_SHA256 = 'f63f10ef724d54a001e572082ae28d498918ac793cf1bd51e3ba18abb46c2835'
RECEIPT_SCHEMA = 'nuclr-current-readout-route-receipt-v1'
MAX_RECEIPT_BYTES = 1024**2


class RouteError(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise RouteError(message)


def canonical(document):
    return json.dumps(document, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(document):
    return hashlib.sha256(canonical(document)).hexdigest()


def _read_pinned(path, maximum, expected):
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as handle:
        before = os.fstat(fd)
        identity = lambda x: (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns, x.st_ctime_ns)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             0 < before.st_size <= maximum, 'bounded ordinary unaliased source required')
        body = handle.read(maximum + 1)
        need(len(body) == before.st_size <= maximum and identity(before) == identity(os.fstat(fd)),
             'route source changed or exceeded bound')
    need(hashlib.sha256(body).hexdigest() == expected, 'route source pin differs')
    return body


def route_definition():
    return json.loads(_read_pinned(HERE / 'route-adoption.json', 65536, ADOPTION_SHA256))


@lru_cache(maxsize=4)
def _load_reader(implementation_root):
    """Private authenticated loading; no sys.path edits or original globals changed."""
    root = Path(implementation_root)
    path = root / 'native-metadata-reader-v2' / 'reader.py'
    body = _read_pinned(path, 1024**2, READER_SHA256)
    name = '_nuclr_current_route_' + uuid.uuid4().hex + '.reader'
    module = ModuleType(name)
    module.__file__, module.__package__ = str(path), name.rsplit('.', 1)[0]
    sys.modules[name] = module
    try:
        exec(compile(body, str(path), 'exec'), module.__dict__)
    except BaseException:
        del sys.modules[name]
        raise
    return module


@dataclass(frozen=True)
class PreparationBinding:
    exact_file_sha256: object
    canonical_manifest_sha256: str
    canonical_joined_panels_sha256: str
    prior_asset_verification_receipt_sha256: str | None
    binding_role: str
    accepted_input_receipt_sha256: str | None
    independent_acceptance_sha256: str | None
    _protected_run_root: Path = field(repr=False)
    _protected_run_identity: tuple = field(repr=False)
    _inputs: object = field(repr=False)
    _reader: object = field(repr=False)
    _native: object = field(repr=False)
    _source: object = field(repr=False)


@dataclass(frozen=True)
class RouteSelection:
    receipt: dict
    receipt_sha256: str
    _binding: PreparationBinding = field(repr=False)
    _selected_projection: dict = field(repr=False)
    _joined_record: dict = field(repr=False)


def _open_directory_without_symlinks(path, *, forbidden_identity=None):
    """Open each absolute directory component without following symbolic links."""
    path = Path(path)
    need(path.anchor == os.sep and '..' not in path.parts, 'single-root absolute directory without parent traversal required')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(path.anchor, flags)
    try:
        opened = os.fstat(fd)
        need((opened.st_dev, opened.st_ino) != forbidden_identity, 'protected original run tree refused')
        for component in path.parts[1:]:
            next_fd = os.open(component, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
            opened = os.fstat(fd)
            need((opened.st_dev, opened.st_ino) != forbidden_identity,
                 'protected original run tree refused, including path aliases')
        return fd
    except BaseException:
        os.close(fd)
        raise


def _protected_directory(path):
    path = Path(path)
    fd = _open_directory_without_symlinks(path)
    try:
        identity = os.fstat(fd)
        return path, (identity.st_dev, identity.st_ino)
    finally:
        os.close(fd)


def _dependencies(implementation_root):
    definition = route_definition()
    root = Path(implementation_root) if implementation_root is not None else HERE.parent
    module = _load_reader(str(root.resolve(strict=True)))
    need(module.READER_POLICY == definition['reader_policy'] and
         module.PRODUCER_COMMIT == definition['native_producer_commit'], 'reader policy/producer differs')
    native = module.frozen_native()
    source = native.load_dependencies()
    need(source.pins['source-splits-v2/source_splits.py'] == definition['source_selector_sha256'] and
         source.pins['initial-evaluator-v1/evaluator.py'] == definition['evaluator_sha256'],
         'adopted source selector/evaluator pins differ')
    return root, definition, module, native, source


def bind_preparation_metadata(owner_root, *, file_sha256, protected_run_root,
                              implementation_root=None):
    """Bind accepted original input metadata; do not repeat upstream array verification."""
    root, definition, module, native, source = _dependencies(implementation_root)
    accepted = json.loads(_read_pinned(root / 'native-metadata-reader-v2' / 'ACCEPTED_INPUTS.json',
                                      65536, definition['accepted_input_receipt_sha256']))
    need(type(file_sha256) is dict and file_sha256 == accepted['identities']['metadata_file_sha256'],
         'authentic binding requires the exact accepted three metadata file hashes')
    protected, identity = _protected_directory(protected_run_root)
    owner, _ = _protected_directory(owner_root)
    need(owner != protected and owner.is_relative_to(protected),
         'protected original run tree must strictly enclose the preparation directory')
    inputs = module.NativeInputs(owner, file_sha256=file_sha256)
    need(native.digest(inputs.manifest) == accepted['identities']['native_manifest_canonical_sha256'] and
         inputs.manifest['raw_archive_sha256'] == accepted['raw_archive']['sha256'],
         'accepted input manifest or raw archive identity differs')
    return PreparationBinding(MappingProxyType(dict(inputs.file_sha256)), native.digest(inputs.manifest),
                              native.digest(inputs.joined), accepted['identities']['verification_receipt_sha256'],
                              'accepted_owner_input_metadata', definition['accepted_input_receipt_sha256'],
                              accepted['identities']['independent_acceptance_sha256'], protected, identity,
                              inputs, module, native, source)


def bind_generated_control_metadata(*, manifest, joined, completion, protected_run_root,
                                    implementation_root=None):
    """Explicit generated-only in-memory fixture boundary; no file/array custody claim."""
    _, _, module, native, source = _dependencies(implementation_root)
    protected, identity = _protected_directory(protected_run_root)
    inputs = module.validate_documents(deepcopy(manifest), deepcopy(joined), deepcopy(completion))
    inputs.file_sha256 = {}
    return PreparationBinding(MappingProxyType({}), native.digest(inputs.manifest), native.digest(inputs.joined),
                              None, 'generated_control_metadata_only', None, None, protected, identity,
                              inputs, module, native, source)


def _check_binding(binding):
    need(type(binding) is PreparationBinding, 'metadata preparation binding required')
    need(digest(binding._inputs.manifest) == binding.canonical_manifest_sha256 and
         digest(binding._inputs.joined) == binding.canonical_joined_panels_sha256,
         'bound preparation documents changed in memory')
    need(dict(binding.exact_file_sha256) == binding._inputs.file_sha256,
         'trusted exact metadata file bindings changed')
    need(binding.binding_role in ('accepted_owner_input_metadata', 'generated_control_metadata_only'),
         'explicit metadata binding role required')
    need(binding._inputs.sessions == {row['session_id']: row for row in binding._inputs.manifest['sessions']} and
         binding._inputs.neurons == {row['id']: row for row in binding._inputs.manifest['neurons']},
         'derived source session or native-address index changed')


def _check_selection(selection):
    need(type(selection) is RouteSelection, 'current-route selection required')
    _check_binding(selection._binding)
    need(digest(selection.receipt) == selection.receipt_sha256 and
         digest(selection._selected_projection) == selection.receipt['selected_projection_sha256'] and
         digest(selection._joined_record) == selection.receipt['original_joined_record_sha256'],
         'current-route selection changed in memory')
    need(selection.receipt['route_definition_sha256'] == ADOPTION_SHA256 and
         selection.receipt['route_id'] == ROUTE_ID, 'selected route definition differs')


def select_current_route(binding, *, label_level, panel, route_id=ROUTE_ID):
    """The original selector runs first; the invalid E/I artifact stays refused."""
    _check_binding(binding)
    definition = route_definition()
    original = binding._inputs.joined
    projections = [binding._reader.restore_source_order(row['projection']) for row in original]
    # This call must precede route/panel compatibility checks. No repair, filter,
    # rewritten membership or bypass is inserted in the original topology path.
    selected = binding._source.splits.select_readout_panel(projections, label_level, panel)
    need(route_id == ROUTE_ID and panel == definition['panel'] and
         label_level in definition['label_levels'], 'unsupported current-source route or panel')
    need(len(selected['splits']) == 1 and 'val' in selected['splits'][0] and
         'train' in selected['splits'][0] and 'test' in selected['splits'][0] and
         'train_cv' not in selected['splits'][0], 'original single train/validation/test split required')
    matching = [row for row in original if row['projection']['label_level'] == label_level and
                row['projection']['panel'] == panel]
    need(len(matching) == 1, 'unique original native join required')
    joined = deepcopy(matching[0])
    need(joined['required_readout_class_balance'] == 'resample' and
         joined['transductive_source_route_unresolved'] is True,
         'frozen native source-policy snapshot differs')
    receipt = {
        'schema': RECEIPT_SCHEMA, 'phase': 'selected_no_fit', 'route_id': ROUTE_ID,
        'adapter_policy': 'current-readout-route-v1',
        'adapter_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'task_id': definition['task_id'], 'label_level': label_level, 'panel': panel,
        'route_definition_sha256': ADOPTION_SHA256,
        'root_decision_sha256': definition['root_decision_sha256'],
        'source_review_sha256': definition['source_review_sha256'],
        'source_commit': definition['source_commit'], 'source_script': definition['source_script'],
        'source_script_sha256': definition['source_script_sha256'],
        'source_loader_sha256': definition['source_loader_sha256'],
        'reader_policy': definition['reader_policy'], 'reader_sha256': READER_SHA256,
        'producer_commit': definition['native_producer_commit'],
        'producer_sha256': definition['native_producer_sha256'],
        'source_selector_sha256': definition['source_selector_sha256'],
        'evaluator_sha256': definition['evaluator_sha256'],
        'exact_preparation_file_sha256': dict(binding.exact_file_sha256),
        'metadata_binding_role': binding.binding_role,
        'accepted_input_receipt_sha256': binding.accepted_input_receipt_sha256,
        'independent_input_acceptance_sha256': binding.independent_acceptance_sha256,
        'canonical_manifest_sha256': binding.canonical_manifest_sha256,
        'canonical_joined_panels_sha256': binding.canonical_joined_panels_sha256,
        'native_order_policy': binding._inputs.manifest['order_policy'],
        'raw_archive_sha256': binding._inputs.manifest['raw_archive_sha256'],
        'metadata_archive_sha256': binding._inputs.manifest['metadata_archive_sha256'],
        'split_archive_sha256': selected['source_archive_sha256'],
        'split_member': selected['source_member'], 'split_member_sha256': selected['source_member_sha256'],
        'selected_projection_sha256': digest(selected),
        'original_joined_record_sha256': digest(joined),
        'label_map_sha256': digest(selected['label_map']), 'split_memberships_sha256': digest(selected['splits']),
        'original_panel_inventory': [{'label_level': row['projection']['label_level'],
                                      'panel': row['projection']['panel'],
                                      'source_member_sha256': row['projection']['source_member_sha256'],
                                      'joined_record_sha256': digest(row),
                                      'matches_registered_topology': row['topology_audit']['matches_registered_topology']}
                                     for row in original],
        'legacy_transductive_source_route_unresolved': joined['transductive_source_route_unresolved'],
        'legacy_flag_interpretation': 'unchanged frozen producer snapshot; this supplemental current route is selected',
        'historical_bugeon_route_verified': False, 'historical_experiment_order_verified': False,
        'paper_era_runtime_verified': False, 'authentic_reference_qualified': False,
        'scientific_qualification': False, 'metadata_binding_authenticates_native_arrays': False,
        'prior_asset_verification': {
            'receipt_sha256': binding.prior_asset_verification_receipt_sha256,
            'status': 'pinned_accepted_upstream_verification_not_reexecuted' if
                binding.prior_asset_verification_receipt_sha256 is not None else 'asset_custody_unasserted',
            'verified_by_this_adapter': False,
        },
        'unchanged_invalid_ei_inductive_disposition': 'original_selector_refuses',
        'benchmark_fit_schedule': 'K_validation_fits_plus_one_selected_final_refit',
        'author_fit_schedule': 'K_validation_fits_plus_K_eager_final_fits',
        'nonconvergence_policy': 'unchanged_ConvergenceWarning_refusal',
        'remaining_holds': deepcopy(binding._inputs.manifest['remaining_holds']),
    }
    return RouteSelection(receipt, digest(receipt), binding, selected, joined)


def _packet_fields(selection, *, input_role, context_variant, representation_training_sessions):
    _check_selection(selection)
    need(input_role in ('generated_engineering_control', 'authentic_candidate'), 'explicit input role required')
    need(type(representation_training_sessions) in (list, tuple) and
         all(type(value) is str for value in representation_training_sessions),
         'explicit representation-training session sequence required')
    binding, projection = selection._binding, selection._selected_projection
    need(input_role != 'authentic_candidate' or binding.binding_role == 'accepted_owner_input_metadata',
         'generated metadata binding cannot create an authentic candidate packet')
    source, native = binding._source, binding._native
    metadata = deepcopy(selection._joined_record['metadata'])
    vocabulary = sorted(source.splits.LABELS[projection['label_level']])
    return {
        'schema_version': 1, 'task_id': source.evaluator.TASK_ID, 'source_commit': source.splits.SOURCE_COMMIT,
        'input_role': input_role, 'label_level': projection['label_level'], 'panel': projection['panel'],
        'context_variant': context_variant, 'class_balance': 'resample',
        'source_session_manifest': sorted(binding._inputs.sessions),
        'representation_training_sessions': list(representation_training_sessions),
        'label_vocabulary': vocabulary, 'source_label_mapping': {label: label for label in vocabulary},
        'label_map': deepcopy(projection['label_map']), 'metadata': metadata,
        'splits': deepcopy(projection['splits']),
        'provenance': {
            'split_sha256': projection['source_member_sha256'], 'metadata_sha256': native.digest(metadata),
            'data_receipt_sha256': binding.canonical_manifest_sha256,
            'split_member': PurePosixPath(projection['source_member']).name,
            'split_release': 'december_2025_current',
            'split_release_detail': 'Current author archive, Last-Modified 2025-12-14; conference equivalence unresolved',
            'native_preparation_order_policy': binding._inputs.manifest['order_policy'],
            'historical_experiment_order_verified': False,
            'transductive_source_route_unresolved': selection._joined_record['transductive_source_route_unresolved'],
        },
    }


def _validate_packet_binding(selection, packet):
    need(type(packet) is dict, 'existing evaluator packet required')
    expected = _packet_fields(selection, input_role=packet.get('input_role'),
                              context_variant=packet.get('context_variant'),
                              representation_training_sessions=packet.get('representation_training_sessions', []))
    need(set(packet) == set(expected) | {'checkpoints'} and
         all(packet[key] == value for key, value in expected.items()),
         'packet differs from selected original source identities, policies or metadata')
    return selection._binding._source.evaluator.validate_packet(packet)


def _packet_receipt(selection, packet, specification):
    ordered_ids = specification['ordered_ids']
    binding = selection._binding
    addresses = binding._native.NativeInputs.native_addresses(binding._inputs, ordered_ids)
    result = deepcopy(selection.receipt)
    result.update({
        'phase': 'packet_bound_no_fit', 'selection_receipt_sha256': selection.receipt_sha256,
        'packet_sha256': digest(packet), 'input_role': packet['input_role'],
        'context_variant': packet['context_variant'],
        'checkpoint_order': [{'id': row['id'], 'epoch': row['epoch']} for row in packet['checkpoints']],
        'ordered_checkpoint_ids_sha256': digest(ordered_ids),
        'ordered_native_addresses': [{'unit_id': uid, 'session_id': address[0], 'column': address[1]}
                                     for uid, address in zip(ordered_ids, addresses)],
        'class_balance': 'resample', 'resampling_seed': 42,
        'scaler_fit_population': 'oversampled_training_rows_in_checkpoint_order',
        'required_readout_fits': len(packet['checkpoints']) + 1,
        'source_exposure': {
            'condition': 'ordinary_transductive_current_source',
            'source_session_manifest': deepcopy(packet['source_session_manifest']),
            'declared_representation_training_sessions': deepcopy(packet['representation_training_sessions']),
            'representation_training_exposure_verified': False,
            'native_normalization': 'per_session_full_concatenated_activity_flattened_99th_percentile',
            'supervised_validation_fit_population': 'original_train_members_only',
            'supervised_selected_final_fit_population': 'original_train_union_validation_members_only',
            'readout_test_labels_used_for_checkpoint_selection': False,
        },
        'authentic_execution_authorized_by_receipt': False,
    })
    need(len(canonical(result)) + 1 <= MAX_RECEIPT_BYTES, 'supplemental packet receipt exceeds bound')
    return result


def build_current_route_packet(selection, checkpoints, *, input_role, context_variant,
                               representation_training_sessions):
    """No fit or dtype conversion here; preserve explicit supplied checkpoint order."""
    packet = _packet_fields(selection, input_role=input_role, context_variant=context_variant,
                            representation_training_sessions=representation_training_sessions)
    packet['checkpoints'] = deepcopy(checkpoints)
    specification = _validate_packet_binding(selection, packet)
    return {'packet': packet, 'route_receipt': _packet_receipt(selection, packet, specification)}


def evaluate_current_route(selection, packet, route_receipt):
    """Explicit numerical entry point; external execution admission is required."""
    specification = _validate_packet_binding(selection, packet)
    expected = _packet_receipt(selection, packet, specification)
    need(type(route_receipt) is dict and route_receipt == expected, 'packet-bound supplemental receipt differs')
    source = selection._binding._source
    result = source.evaluator.evaluate(packet)
    expected_ids = [uid for uid in specification['ordered_ids'] if uid in specification['splits'][0]['test']]
    need(result['packet_sha256'] == digest(packet) and len(result['selected']) == 1 and
         [row['unit_id'] for row in result['records']] == expected_ids and
         result['resources']['readout_fits'] == len(packet['checkpoints']) + 1 and
         result['research_qualified'] is False and result['full_contract_complete'] is False,
         'unchanged evaluator result coverage, fit schedule or qualification differs')
    receipt = deepcopy(route_receipt)
    imblearn = sys.modules.get('imblearn')
    receipt.update({'phase': 'evaluated_current_route_engineering_only',
                    'packet_bound_receipt_sha256': digest(route_receipt),
                    'readout_result_sha256': digest(result),
                    'actual_readout_resources': deepcopy(result['resources']),
                    'imbalanced_learn_version': getattr(imblearn, '__version__', None),
                    'selected_checkpoint': deepcopy(result['selected'][0]),
                    'test_record_count': len(result['records']),
                    'scientific_qualification': False})
    need(len(canonical(receipt)) + 1 <= MAX_RECEIPT_BYTES, 'execution receipt exceeds fixed bound')
    return {'readout_result': result, 'route_receipt': receipt}


def write_receipt_new(selection, path, receipt):
    """Exclusive sidecar outside the binding's protected original run tree."""
    _check_selection(selection)
    need(type(receipt) is dict and receipt.get('schema') == RECEIPT_SCHEMA and
         receipt.get('route_id') == ROUTE_ID and receipt.get('route_definition_sha256') == ADOPTION_SHA256 and
         receipt.get('phase') in ('selected_no_fit', 'packet_bound_no_fit', 'evaluated_current_route_engineering_only'),
         'versioned current-route receipt required')
    need(all(receipt.get(key) == value for key, value in selection.receipt.items() if key != 'phase'),
         'receipt differs from selected source and custody identities')
    if receipt['phase'] != 'selected_no_fit':
        need(receipt.get('selection_receipt_sha256') == selection.receipt_sha256,
             'supplemental receipt selection identity differs')
    else:
        need(receipt == selection.receipt, 'no-fit selection receipt differs')
    body = canonical(receipt) + b'\n'
    need(len(body) <= MAX_RECEIPT_BYTES, 'supplemental route receipt exceeds fixed bound')
    path = Path(path)
    need(path.anchor == os.sep and '..' not in path.parts and path.name,
         'absolute sidecar path without parent traversal required')
    protected, identity = _protected_directory(selection._binding._protected_run_root)
    need(identity == selection._binding._protected_run_identity, 'protected run directory identity changed')
    need(not path.is_relative_to(protected), 'receipt must remain outside the entire original run tree')
    parent_fd = _open_directory_without_symlinks(path.parent, forbidden_identity=identity)
    try:
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=parent_fd)
        with os.fdopen(fd, 'wb') as output:
            output.write(body)
            output.flush()
            os.fsync(output.fileno())
    finally:
        os.close(parent_fd)
    return {'bytes': len(body), 'file_sha256': hashlib.sha256(body).hexdigest(),
            'canonical_receipt_sha256': digest(receipt)}
