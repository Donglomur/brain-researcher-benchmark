"""Trusted source/byte custody. No candidate code is imported into this process.

Capabilities establish this source's caller sequence, not external execution
authority. They must remain in a dedicated serialized trusted process. Ordinary
filesystem pins alone cannot establish kernel containment or data provenance.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import time
from types import MappingProxyType


def need(ok, why):
    if not ok:
        raise ValueError(why)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def parsed(raw):
    def pairs(rows):
        out = {}
        for key, value in rows:
            need(key not in out, 'Duplicate JSON key')
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'Nonfinite JSON'))


def pin(raw):
    need(type(raw) is bytes, 'Captured immutable bytes')
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def check_pin(value):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'}
         and type(value['bytes']) is int and value['bytes'] >= 0
         and type(value['sha256']) is str and len(value['sha256']) == 64
         and all(c in '0123456789abcdef' for c in value['sha256']), 'Exact body pin')


class Budget:
    def __init__(self, read_bytes, write_bytes, seconds):
        need(type(read_bytes) is int and read_bytes > 0 and type(write_bytes) is int and write_bytes > 0,
             'Explicit positive logical byte limits')
        need(type(seconds) in (int, float) and math.isfinite(seconds) and seconds > 0, 'Explicit finite deadline')
        self.read_limit, self.write_limit = read_bytes, write_bytes
        self.read_bytes = self.write_bytes = 0
        self.end = time.monotonic() + seconds

    def tick(self):
        need(time.monotonic() < self.end, 'Original operation deadline')

    def charge(self, kind, count):
        self.tick()
        need(kind in ('read', 'write') and type(count) is int and count >= 0, 'Typed byte charge')
        field = kind + '_bytes'
        setattr(self, field, getattr(self, field) + count)
        need(getattr(self, field) <= getattr(self, kind + '_limit'), 'Logical ' + kind + ' allowance exhausted')


def path(root, name):
    need(type(name) is str and name and not name.startswith('/') and '\\' not in name
         and all(x not in ('', '.', '..') for x in name.split('/')), 'Safe relative path')
    result = Path(root) / name
    need(not any(p.is_symlink() for p in (result, *result.parents)), 'No linked source/data path')
    return result


def read(root, name, expected, budget):
    check_pin(expected)
    target = path(root, name)
    budget.charge('read', expected['bytes'] + 1)
    fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        first = os.fstat(fd)
        need(stat.S_ISREG(first.st_mode) and first.st_nlink == 1 and first.st_size == expected['bytes'],
             'Ordinary exact pinned file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(expected['bytes'] + 1)
        after, named = os.fstat(fd), target.lstat()
        need(all(getattr(first, k) == getattr(after, k) == getattr(named, k) for k in
                 ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')),
             'Stable file and name identity')
    finally:
        os.close(fd)
    need(pin(body) == expected, 'Exact file bytes')
    return body


def write(root, name, body, budget):
    need(type(body) is bytes, 'Immutable output')
    target = path(root, name)
    need(target.parent.is_dir(), 'Explicitly prepared output parent')
    budget.charge('write', len(body))
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            need(stream.write(body) == len(body), 'Complete output write')
            stream.flush()
            os.fsync(stream.fileno())
        os.fchmod(fd, 0o444)
    finally:
        os.close(fd)
    return pin(body)


_CLOSED_KEY = object()


class ClosedStage:
    __slots__ = ('context', 'phase', 'mode', 'receipt_bytes', 'files', '_key',
                 'context_bytes', 'input_inventory_bytes', 'capsule_inventory_bytes')
    def __setattr__(self, name, value):
        raise TypeError('ClosedStage is immutable')
    def __init__(self, key, context, phase, mode, receipt, files, *, context_bytes,
                 input_inventory_bytes, capsule_inventory_bytes):
        need(key is _CLOSED_KEY, 'Only closed process capture creates a stage')
        need(all(type(v) is bytes for v in (context_bytes,input_inventory_bytes,capsule_inventory_bytes))
             and all(type(v) is bytes for v in files.values()), 'Immutable captured stage bodies')
        values=dict(context=context,phase=phase,mode=mode,receipt_bytes=encoded(receipt),
                    files=MappingProxyType(dict(files)),_key=key,context_bytes=context_bytes,
                    input_inventory_bytes=input_inventory_bytes,capsule_inventory_bytes=capsule_inventory_bytes)
        for name,value in values.items():
            object.__setattr__(self,name,value)


def _capture_closed(spec, receipt, output_root, expected_files, budget, *, context_bytes,
                    input_inventory_bytes, capsule_inventory_bytes):
    """Only the concrete source-owned runner calls this after run_stage returns."""
    need(receipt['context_id'] == spec['context_id'] and receipt['mode'] == spec['mode']
         and receipt['phase'] == spec['phase'], 'Actual stage binding')
    need(receipt['success'] is True and receipt['terminal_observed'] is True
         and receipt['cleanup_complete'] is True and receipt.get('broker_thread_terminal') is True
         and type(receipt['container_exit_code']) is int and receipt['container_exit_code'] == 0
         and type(receipt['attach_exit_code']) is int and receipt['attach_exit_code'] == 0,
         'Natural closed producer before capture')
    context=parsed(context_bytes)
    need(context['context_id']==spec['context_id'] and context['mode']==spec['mode']
         and context['phase']==spec['phase'] and receipt['prelaunch_context']==pin(context_bytes)
         and receipt['prelaunch_input_inventory']==pin(input_inventory_bytes)
         and receipt['prelaunch_capsule_inventory']==pin(capsule_inventory_bytes),
         'Actual prelaunch captured request and input/source inventories')
    inputs=parsed(input_inventory_bytes)
    need(inputs['MANIFEST.json']==context['payload']['packet'], 'Packet manifest was an actual mounted input')
    capsules=parsed(capsule_inventory_bytes)
    need(context['capsule_files']=={n:r['sha256'] for n,r in capsules.items()}
         and context['entrypoint'] in capsules, 'Actual prelaunch capsule inventory joins worker entrypoint')
    root = Path(output_root)
    observed = []
    for folder, dirs, files in os.walk(root, followlinks=False):
        need(not any(Path(folder, d).is_symlink() for d in dirs), 'No linked output directory')
        observed.extend(str(Path(folder, f).relative_to(root)) for f in files)
    need(set(observed) == set(expected_files) and len(observed) == len(expected_files), 'Exact complete output inventory')
    captured = {}
    for name, limit in expected_files.items():
        need(type(limit) is int and limit > 0, 'Positive artifact bound')
        target = path(root, name)
        st = target.lstat()
        need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and 0 <= st.st_size <= limit,
             'Bounded ordinary artifact after producer closure')
        # The producer is closed before deriving this untrusted proposal's pin.
        budget.charge('read', st.st_size + 1)
        with target.open('rb') as stream:
            raw = stream.read(st.st_size + 1)
        after = target.lstat()
        need(len(raw) == st.st_size and all(getattr(st, k) == getattr(after, k) for k in
             ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')), 'Stable closed artifact')
        captured[name] = raw
    return ClosedStage(_CLOSED_KEY, spec['context_id'], spec['phase'], spec['mode'], receipt, captured,
                       context_bytes=context_bytes,input_inventory_bytes=input_inventory_bytes,
                       capsule_inventory_bytes=capsule_inventory_bytes)


_WHOLE_KEY = object()


class WholeFit:
    __slots__ = ('model_bytes', 'commitment_bytes', 'fit_manifest_bytes', 'fit_request_bytes', 'closed_producer_bytes')
    def __setattr__(self,name,value):
        raise TypeError('WholeFit is immutable')
    def __init__(self, key, model, commitment, manifest, request, closed):
        need(key is _WHOLE_KEY, 'Whole reference capture capability required')
        for name,value in zip(self.__slots__,(model,commitment,manifest,request,closed),strict=True):
            need(type(value) is bytes,'Immutable whole-fit bytes')
            object.__setattr__(self,name,value)


def whole_fit_from_closed(stage, manifest_bytes, request_bytes):
    """Bind an actual trusted-reference closure to original request/member bytes.

    This function runs in the trusted caller after its fixed reference capsule
    produced all four states; it never accepts candidate artifacts as references.
    Capsule source identity is enforced by the source-owned ClosedProcess route.
    """
    need(type(stage) is ClosedStage and stage._key is _CLOSED_KEY and stage.phase == 'train'
         and stage.context.startswith('reference-whole-'), 'Actual whole-reference producer')
    need(set(stage.files) == {'model.bin', 'fit_report.json', 'fit_manifest.json'}, 'Whole reference output set')
    fitted = parsed(stage.files['fit_manifest.json'])
    need(fitted['context_id'] == stage.context and type(fitted['files']) is list
         and {r['path']: {k: r[k] for k in ('bytes', 'sha256')} for r in fitted['files']} ==
         {n: pin(stage.files[n]) for n in ('model.bin', 'fit_report.json')}
         and len(fitted['files']) == 2, 'Actual bootstrap fitted inventory joins closed artifacts')
    manifest, request = parsed(manifest_bytes), parsed(request_bytes)
    prelaunch=parsed(stage.context_bytes);inputs=parsed(stage.input_inventory_bytes)
    need(prelaunch['payload']['reference_kind']=='whole' and prelaunch['entrypoint']=='reference_entry.py'
         and set(parsed(stage.capsule_inventory_bytes))=={'reference_entry.py'}
         and prelaunch['payload']['reference_fit_request']==request
         and prelaunch['payload']['packet']==pin(manifest_bytes)==inputs['MANIFEST.json']
         and set(inputs)=={'MANIFEST.json',*manifest['files']}
         and all(inputs[name]=={k:descriptor[k] for k in ('bytes','sha256')}
                 for name,descriptor in manifest['files'].items()),
         'Whole reuse binds actual prelaunch request, manifest and all mounted members')
    need(request['phase_name'] == request['kind'] == 'reference_fit'
         and request['session_token'] == manifest['session_token']
         and request['payload'] == {'fitval_manifest': pin(manifest_bytes)}, 'Exact original whole fit request')
    report = parsed(stage.files['fit_report.json'])
    need(report['schema'] == 'neural094_trusted_reference_fit_report_v1'
         and report['status'] == 'all_four_final_states_fitted_before_query'
         and report['query_accessed'] is False and report['query_targets_used'] is False,
         'Whole trusted numerical fit report')
    artifact = {'path': 'model.bin', **pin(stage.files['model.bin'])}
    commitment = {'schema': 'neural094_trusted_reference_model_commit_v1',
                  'reference_sha256': report['reference_sha256'], 'session_token': manifest['session_token'],
                  'artifact': artifact, 'all_four_states_committed_before_query': True,
                  'fit_process_closed': True, 'sealed_readonly': True, 'artifact_sha256_verified_by_loader': True}
    closed = {'phase_name': 'reference_fit', 'status': 'complete_closed_phase', 'request': pin(request_bytes),
              'producer_observation': pin(stage.receipt_bytes),
              'prelaunch_context':pin(stage.context_bytes),
              'prelaunch_input_inventory':pin(stage.input_inventory_bytes), 'evidence': {
                  'trusted_worker_terminal': {'status': 'complete_trusted_reference_fit',
                      'query_features_read': False, 'query_targets_read': 0, 'models_committed': False,
                      'empirical_estimator_fit_attempts': report['empirical_fit_counters'].get('estimator_fit_attempts', 0)},
                  'artifacts': {'model_artifact': artifact}}}
    return WholeFit(_WHOLE_KEY, stage.files['model.bin'], encoded(commitment), manifest_bytes,
                    request_bytes, encoded(closed))


def restore_whole_for_reference_worker(bodies):
    """Fixed trusted worker only; bodies are readonly captured parent capability.

    Its mount inventory is source-owned and inaccessible to candidate workers.
    This restores the transport representation, not a new authority from flags.
    """
    names = ('model_bytes', 'commitment_bytes', 'fit_manifest_bytes', 'fit_request_bytes', 'closed_producer_bytes')
    need(type(bodies) is dict and set(bodies) == set(names)
         and all(type(bodies[n]) is bytes for n in names), 'Complete captured whole-fit transfer')
    return WholeFit(_WHOLE_KEY, *(bodies[n] for n in names))
