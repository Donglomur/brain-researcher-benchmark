"""Complete accepted Bugeon NPY inputs -> original owner-side temporaldata schema.

This is a numerical/schema adapter, not a training runner or an access sandbox.
The real external constructors remain a mandatory unexecuted runtime seam.
There is no writer, download, implicit fit, source diagnostic call, or installation.
An admitted serializer can consume iter_accepted_sessions in a later operation.
"""
from __future__ import annotations

from dataclasses import dataclass
import datetime
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import uuid

HERE = Path(__file__).resolve().parent
ROUTE_SHA256 = '0a805257cee463aadab9627f39af4c09b5cdf5509c6e0d2852c6975b93eaa5aa'
PREPARER_SHA256 = '10af34325fcc3dedb47a3cb461b562ac0292f1481e9d3a757c094f6866ae35c0'
SOURCE_COMMIT = '0fa409b304147ace00507063d44f03155691af62'
VCS_DEPENDENCIES = {
    'temporaldata': 'b0a92bf4f9e36e27c5eddbf02c8acbd5df90ee39',
    'brainsets': '61c8a7bc4fb39412a4d2f12c6209936606d4c12f',
}
VECTOR_FIELDS = {
    'depth': 'depth', 'plane': 'plane',
    'rf_center_xvis': 'rfCenter_Xvis', 'rf_center_yvis': 'rfCenter_Yvis',
}


class BridgeError(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise BridgeError(message)


def load_route():
    """Load the fixed accepted-input route; do not patch its historical source."""
    path = HERE.parent / 'current-readout-route-v1' / 'route.py'
    body = path.read_bytes()
    need(hashlib.sha256(body).hexdigest() == ROUTE_SHA256, 'current route source differs')
    name = '_nuclr_temporaldata_route_' + uuid.uuid4().hex
    module = ModuleType(name)
    module.__file__, module.__package__ = str(path), ''
    sys.modules[name] = module
    try:
        exec(compile(body, str(path), 'exec'), module.__dict__)
    except BaseException:
        del sys.modules[name]
        raise
    return module


def required_runtime_provenance(distribution=importlib.metadata.distribution):
    """Check declared VCS installations; this is NOT package-tree attestation.

    A later runtime qualification must authenticate loaded code and constructor,
    HDF5 roundtrip and torch_brain Dataset behavior. Editable installs are refused.
    Metadata provenance alone never promotes the bridge to runtime-qualified.
    """
    result = {}
    for name, commit in VCS_DEPENDENCIES.items():
        try:
            dist = distribution(name)
            direct = json.loads(dist.read_text('direct_url.json') or 'null')
        except (importlib.metadata.PackageNotFoundError, ValueError, TypeError) as exc:
            raise BridgeError('required source runtime is unavailable: ' + name) from exc
        need(type(direct) is dict and type(direct.get('vcs_info')) is dict and
             type(direct.get('dir_info', {})) is dict and direct['vcs_info'].get('vcs') == 'git' and
             direct['vcs_info'].get('commit_id') == commit and
             direct.get('dir_info', {}).get('editable') is not True,
             'required original VCS dependency differs: ' + name)
        result[name] = {'version': dist.version, 'declared_commit': commit,
                        'loaded_source_tree_authenticated': False}
    return result


def load_source_runtime():
    """Require real dependencies; never substitute fake intervals or serializers."""
    provenance = required_runtime_provenance()
    from temporaldata import Data, ArrayDict, IrregularTimeSeries
    from brainsets.taxonomy import Species
    from brainsets.descriptions import BrainsetDescription, SubjectDescription, SessionDescription
    from brainsets.core import serialize_fn_map
    return SimpleNamespace(Data=Data, ArrayDict=ArrayDict, IrregularTimeSeries=IrregularTimeSeries,
                           Species=Species, BrainsetDescription=BrainsetDescription,
                           SubjectDescription=SubjectDescription, SessionDescription=SessionDescription,
                           serialize_fn_map=serialize_fn_map, provenance=provenance,
                           runtime_qualified=False)


def _geometry(session, blocks, neurons):
    need(type(session) is dict and type(blocks) is list and blocks and type(neurons) is list,
         'complete session metadata and block sequence required')
    sid, count = session['session_id'], session['neurons']
    need(type(count) is int and count > 0 and len(neurons) == count,
         'complete session neuron count required')
    need([row['id'] for row in neurons] == [f'{sid}_u{i}' for i in range(count)] and
         all(row['session_id'] == sid and row['source_neuron_index'] == i
             for i, row in enumerate(neurons)), 'original native column identity/order differs')
    need(len(blocks) == len(session['experiments']), 'complete session experiment sequence required')
    return sid, count


def assemble_session(session, neurons, blocks, unit_arrays, runtime):
    """Assemble the exact source schema from complete arrays in current release order.

    Pure lower-level numerical boundary, also used with explicit generated arrays
    and constructor doubles. It establishes no authentic custody by itself.
    Each input block contains raw activity and ALREADY SHIFTED native timestamps.
    """
    import numpy as np
    sid, count = _geometry(session, blocks, neurons)
    subject, date = sid.split('_')
    expected_keys = {'depth', 'plane', 'rfCenter_Xvis', 'rfCenter_Yvis', 'stackPosCorrected'}
    need(set(unit_arrays) == expected_keys, 'original model metadata fields required')
    typed_units = {}
    for name, value in unit_arrays.items():
        need(isinstance(value, np.ndarray) and value.dtype.kind in 'fiu' and
             value.dtype.str == session['neuron_headers'][name]['dtype'],
             'native unit metadata dtype differs')
        expected_shape = tuple(session['neuron_headers'][name]['shape'])
        need(value.shape == expected_shape, 'native unit metadata shape differs')
        if name == 'stackPosCorrected':
            need(value.shape == (count, 2), 'native stack position columns differ')
            typed_units['stackPos_x'], typed_units['stackPos_y'] = value[:, 0], value[:, 1]
        else:
            need(value.shape in ((count,), (count, 1)), 'native unit vector geometry differs')
            output_name = next(output for output, source in VECTOR_FIELDS.items() if source == name)
            typed_units[output_name] = value.squeeze()

    traces = []
    previous_end = None
    for expected, block in zip(session['experiments'], blocks):
        activity, clock = block['activity'], block['timestamps']
        need(block['experiment_id'] == expected['experiment_id'] and block['normalized'] is False,
             'original complete raw block order required')
        need(isinstance(activity, np.ndarray) and isinstance(clock, np.ndarray) and
             activity.shape == (expected['frames'], count) and clock.shape == (expected['frames'],) and
             activity.dtype.str == expected['activity_header']['dtype'] and
             clock.dtype.str == expected['timestamp_header']['dtype'], 'native array shape/dtype differs')
        need(np.isfinite(activity).all() and np.isfinite(clock).all() and np.all(np.diff(clock) >= 0),
             'source nonfinite/unsorted arrays refused without exclusions')
        need(float(clock[0]) == expected['shifted_first_second'] and
             float(clock[-1]) == expected['shifted_last_second'] and
             (previous_end is None or float(clock[0]) >= previous_end),
             'source shifted clock or nonmonotonic concatenation differs')
        previous_end = float(clock[-1])
        # Delegate auto-domain semantics to the required real source library.
        traces.append(runtime.IrregularTimeSeries(timestamps=clock, df_over_f=activity, domain='auto'))

    timestamps = np.concatenate([row.timestamps for row in traces], axis=0)
    raw = np.concatenate([row.df_over_f for row in traces], axis=0)
    norm = session['normalization']
    need(raw.shape == (session['frames'], count) and raw.dtype.str == norm['native_concatenated_dtype'],
         'complete source frame accounting differs')
    need(norm['method'] == 'numpy_percentile_flattened_session_99_default_linear' and
         norm['percentile_scalar_dtype'] in ('<f4', '<f8'), 'source normalization policy differs')
    denominator = np.asarray(norm['percentile'], dtype=norm['percentile_scalar_dtype'])[()]
    need(np.isfinite(denominator) and denominator != 0, 'source normalization denominator invalid')
    normalized = raw / denominator
    need(normalized.dtype.str == norm['normalized_dtype'] and np.isfinite(normalized).all(),
         'current runtime normalization dtype/nonfinite mismatch; no cast or clipping')
    domain = traces[0].domain
    for trace in traces[1:]:
        domain = domain | trace.domain
    calcium = runtime.IrregularTimeSeries(timestamps=timestamps, df_over_f=raw,
                                         df_over_f_norm=normalized, domain=domain)
    need(calcium.is_sorted(), 'source temporaldata sortedness failed')
    labels = np.array([row['ttype'] for row in neurons])
    ei = np.array(['IN' if label not in ('IN', 'EC') else label for label in labels])
    subclass = np.array([label.split('-')[0] if label not in ('IN', 'EC') else 'unknown' for label in labels])
    need(ei.tolist() == [row['ei_class'] for row in neurons] and
         subclass.tolist() == [row['subclass'] for row in neurons], 'source transcriptomic labels differ')
    # Both raw and normalized matrices and literal unit metadata are preserved.
    # The source's calcium UnitDropout quirk is not repaired by this conversion.
    return runtime.Data(
        brainset=runtime.BrainsetDescription(id='bugeon_transcriptomic_2022', origin_version='0.0.0',
            derived_version='0.0.0', source='https://www.nature.com/articles/s41586-022-04915-7',
            description='A_transcriptomic_axis_predicts_state_modulation_of_cortical_interneurons'),
        subject=runtime.SubjectDescription(id=subject.upper(), species=runtime.Species.UNKNOWN),
        session=runtime.SessionDescription(id=sid, recording_date=datetime.datetime.strptime(date, '%Y%m%d')),
        units=runtime.ArrayDict(id=np.array([row['id'] for row in neurons]), ttype=labels,
                               ei_class=ei, subclass=subclass, **typed_units),
        calcium_traces=calcium, domain=calcium.domain)


@dataclass(frozen=True)
class OwnerSession:
    session_id: str
    data: object
    provenance: dict


def iter_accepted_sessions(selection, route, runtime=None):
    """Yield all 17 original session objects for later owner-side serialization.

    The accepted readout selection must be five-subclass ordinary transductive.
    There is no session/subset option. Consumer exhaustion and actual 17-file
    HDF5 roundtrip are mandatory in a separately reviewed serialization protocol.
    This function DOES read authentic arrays if called: source construction does
    not authorize that operation. It never creates training or candidate results.
    """
    route._check_selection(selection)
    binding = selection._binding
    need(selection.receipt['label_level'] == 'subclass' and selection.receipt['panel'] == 'transductive',
         'prospectively selected complete five-subclass ordinary-transductive panel required')
    need(binding.binding_role == 'accepted_owner_input_metadata', 'accepted owner input metadata required')
    need(len(selection._selected_projection['label_map']) == 1500, 'complete selected label population required')
    inputs, native = binding._inputs, binding._native
    need(len(inputs.sessions) == 17 and len(inputs.neurons) == 10153 and
         sum(len(row['experiments']) for row in inputs.sessions.values()) == 69,
         'all original representation sessions/neurons/blocks required')
    runtime = runtime if runtime is not None else load_source_runtime()
    for session in inputs.manifest['sessions']:
        sid = session['session_id']
        blocks = []
        for block in session['experiments']:
            record = inputs.read_block(sid, block['experiment_id'], 0, block['frames'], normalized=False)
            record['experiment_id'] = block['experiment_id']
            blocks.append(record)
        unit_arrays = {}
        directory = native.profile()['sessions'][sid]['source_directory']
        import numpy as np
        for name in ('depth', 'plane', 'rfCenter_Xvis', 'rfCenter_Yvis', 'stackPosCorrected'):
            member = directory + '/neuron.' + name + '.npy'
            asset = inputs.assets[member]
            need(asset['source_member'] == member and asset['relative_path'] == 'native/' + member,
                 'source native metadata asset path differs')
            with native.NativeArray(inputs.root / asset['relative_path'], sha256=asset['sha256']) as array:
                need(array.header == session['neuron_headers'][name], 'native metadata header differs')
                unit_arrays[name] = np.array(array.values, copy=True, order='K')
                array.check()
        neurons = [inputs.neurons[f'{sid}_u{i}'] for i in range(session['neurons'])]
        data = assemble_session(session, neurons, blocks, unit_arrays, runtime)
        yield OwnerSession(sid, data, {
            'schema': 'nuclr-owner-temporaldata-session-v1', 'session_id': sid,
            'input_manifest_sha256': binding.canonical_manifest_sha256,
            'prior_input_acceptance_sha256': binding.independent_acceptance_sha256,
            'selection_receipt_sha256': selection.receipt_sha256,
            'source_preparer_sha256': PREPARER_SHA256, 'source_commit': SOURCE_COMMIT,
            'frames': session['frames'], 'neuron_observations': session['neurons'],
            'blocks': len(session['experiments']), 'order_policy': session['order_policy'],
            'source_normalization': dict(session['normalization']),
            'source_library_declarations': runtime.provenance,
            'contains_owner_only_transcriptomic_labels': True,
            'loaded_runtime_qualified': False, 'hdf5_serialized': False,
            'historical_reference_reproduced': False, 'scientific_qualification': False})
        # The caller must serialize/dispose each item before requesting the next;
        # retaining all returned objects is outside this one-session memory plan.
        del data, blocks, unit_arrays
