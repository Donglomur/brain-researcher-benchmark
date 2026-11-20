"""Protected reference-only selector over the retained owner and original scorer.

The two phase names are model identities. Both phases have assisted information
access and wire role B; no participant A/B comparison is constructed here.
"""
import argparse
import hashlib
import os
from pathlib import Path
import stat
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reference_core import (ACCESS, ARMS, FILE_CAP, META_CAP, METRICS, OUTCOME, PHASES,
    PROFILE, ROUTE, body, decode, encode, load_module, method_plan, need, path, pin,
    read, recipe, source_identity, validate_job, write_new)

HERE = Path(__file__).resolve().parent
FACADE = HERE.parents[1] / 'full-panel-improvement-v1' / 'full_panel_episode.py'
FACADE_PIN = {'bytes': 41057,
              'sha256': '7becc1746b068699070bc28f16286246427233e1a0082274b01a6ad75bcf8c3a'}
_base = load_module('_smc_reference_fixed_facade', FACADE, FACADE_PIN)


def hash_file(filename, cap=FILE_CAP):
    p = path(filename)
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    h = hashlib.sha256()
    count = 0
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 <= before.st_size <= cap, 'Bounded ordinary scientific file')
        while True:
            chunk = stream.read(min(1024**2, cap + 1 - count))
            if not chunk:
                break
            count += len(chunk)
            need(count <= cap, 'Complete scientific byte ceiling')
            h.update(chunk)
        after, named = os.fstat(stream.fileno()), p.lstat()
    keys = ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
    need(count == before.st_size and all(getattr(before, k) == getattr(after, k) == getattr(named, k)
         for k in keys), 'Stable complete scientific file')
    return h.hexdigest()


def validate_reference_pair(closed):
    """Metadata gate is necessary; retained runner.grade adds parent/cgroup proofs."""
    need(closed['schema'] == 'smc_author_reference_closed_pair_v1' and closed['route'] == ROUTE
         and closed['outcome'] == OUTCOME and set(closed['conditions']) == set(PHASES)
         and closed['both_conditions_closed_before_private_grade'] is True
         and closed['all_programmes_frozen_before_execution'] is True
         and closed['private_target_accessed'] is False
         and closed['AI_attribution_verified'] is False and closed['scientific_success'] is None,
         'Both distinct closed reference jobs before any target read')
    return closed


def copy_snapshot(source, destination, expected, cap):
    """Copy at most the precharged exact extent; growth is never written."""
    source, destination = path(source), path(destination)
    need(type(expected) is dict and set(expected) == {'bytes', 'sha256'}
         and type(expected['bytes']) is int and 0 < expected['bytes'] <= cap,
         'Prospectively bounded exact snapshot descriptor')
    descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and before.st_size == expected['bytes'], 'Exact ordinary snapshot source before copying')
        output_fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
        count, digest = 0, hashlib.sha256()
        with os.fdopen(output_fd, 'wb') as sink:
            while count < expected['bytes']:
                chunk = stream.read(min(1024**2, expected['bytes'] - count))
                need(chunk, 'Snapshot source truncated during bounded copy')
                count += len(chunk)
                digest.update(chunk)
                sink.write(chunk)
            need(stream.read(1) == b'', 'Snapshot source grew beyond precharged extent')
            after, named = os.fstat(stream.fileno()), source.lstat()
            fields = ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
            need(all(getattr(before, key) == getattr(after, key) == getattr(named, key) for key in fields)
                 and digest.hexdigest() == expected['sha256'], 'Stable exact original snapshot bytes')
            sink.flush()
            os.fsync(sink.fileno())
    need(destination.lstat().st_size == expected['bytes'], 'Complete bounded snapshot output')
    return expected


class ReferenceEpisode(_base.FullPanelEpisode):
    ROUTE, CONDITIONS = ROUTE, PHASES
    PROFILES = {OUTCOME: PROFILE}
    KEYS = {OUTCOME: ['offline']}
    CLOSED_SCHEMA = 'smc_author_reference_closed_pair_v1'

    def __init__(self, repository_root, component_root):
        self.repository_root, self.HERE = path(repository_root), path(component_root)
        source_identity(self.HERE)
        retained_root = self.repository_root / _base.EPISODE_REL
        _base._read_source(retained_root / 'SOURCE.json', _base.EPISODE_SOURCE_PIN)
        self.retained = _base._module('_smc_reference_retained_episode',
                                      retained_root / 'episode.py', _base.EPISODE_PIN)
        self.retained.source_identity()
        for name in ('need', 'path', 'body', 'read', 'publish', 'relative', 'descriptor',
                     'checked', 'encoded', 'request_bytes', 'pin', 'decode', 'file_mount',
                     'mount_identity', 'validate_closed', 'observe_closed', 'provider_class'):
            setattr(self, name, getattr(self.retained, name))
        self.bindings = read(self.HERE / 'BINDINGS.json')
        self.TRANSPORT = retained_root / 'vendor_transport'
        self.TRANSPORT_SHA = self.retained.TRANSPORT_SHA
        self.TASK_SHA = pin(body(self.HERE / 'REFERENCE_TASK.json'))['sha256']
        self._protocol = self._protocol_path = None
        self._captured_actual = {}
        self._compatibility = ReferenceBenchmark(self)

    def source_identity(self):
        return source_identity(self.HERE)

    def implementation_identity(self):
        manifest = read(self.HERE / 'SOURCE.json')
        return pin(encode({'schema': 'smc_author_reference_implementation_v1',
            'route': ROUTE, 'files': {name: value for name, value in manifest['files'].items()
            if name != 'DEPLOYMENT_BINDING.json'},
            'transport': self.pin(self.body(self.TRANSPORT / 'SOURCE_MANIFEST.json'))}))

    @property
    def PAIR_SHA(self):
        return self.bindings['sources']['pair']['sha256']

    def benchmark(self):
        return self._compatibility

    def material_binding(self):
        return self.bindings['sources']['pair']

    def public_context(self, pair_path, task_path):
        pair_raw, task_raw = body(pair_path), body(task_path)
        need(pin(pair_raw) == {k: self.bindings['sources']['pair'][k] for k in ('bytes', 'sha256')}
             and pin(task_raw)['sha256'] == self.TASK_SHA, 'Exact original pair and new reference contract')
        task = decode(task_raw)
        need(task['route'] == ROUTE and task['outcome'] == OUTCOME
             and task['reference_phases'] == list(PHASES)
             and task['access_condition'] == ACCESS and task['wire_roles'] == ['B', 'B'],
             'Reference model identities remain separate from assisted access')
        delivery_path = path(pair_path).parent / ACCESS / 'delivery_manifest.json'
        expected = self.bindings['sources']['assisted_delivery']
        delivery = decode(body(delivery_path, {k: expected[k] for k in ('bytes', 'sha256')}))
        need(delivery['condition'] == ACCESS, 'Both references select authentic assisted materials')
        return decode(pair_raw), {ACCESS: delivery}

    def instantiate(self, pair_path, task_path, runtime_path, runtime_sha, output):
        self.public_context(pair_path, task_path)
        runtime_raw = body(runtime_path)
        need(pin(runtime_raw)['sha256'] == runtime_sha, 'Exact selected runtime configuration')
        runtime = self.runtime_config(decode(runtime_raw))
        root = path(output)
        need(not root.exists() and root.parent.is_dir()
             and not root.is_relative_to(path(pair_path).parent)
             and not root.is_relative_to(self.HERE), 'Fresh external reference protocol')
        program = body(self.HERE / 'reference_adapter.py')
        binding_pin = pin(body(self.HERE / 'BINDINGS.json'))
        plans = {phase: method_plan(phase, pin(program), binding_pin) for phase in PHASES}
        root.mkdir(mode=0o700)
        records = {}
        # Both exact model selections and programmes are frozen before either execution.
        for phase in PHASES:
            folder = root / phase
            folder.mkdir(mode=0o700)
            program_pin = write_new(folder / 'program.py', program, 0o444)
            declaration_pin = write_new(folder / 'declaration.json', encode(plans[phase]), 0o444)
            freeze = {'schema': 'smc_author_reference_method_freeze_v1', 'route': ROUTE,
                'phase_id': phase, 'access_condition': ACCESS, 'plan': plans[phase],
                'program': program_pin, 'declaration': declaration_pin,
                'original_pair_sha256': self.PAIR_SHA, 'test_inputs_released': False}
            frozen_pin = write_new(folder / 'METHOD.json', encode(freeze))
            records[phase] = {'program': program_pin, 'declaration': declaration_pin,
                'method': {'path': str(folder / 'METHOD.json'), **frozen_pin}}
        protocol = {'schema': 'smc_author_reference_protocol_v1', 'route': ROUTE,
            'task_id': self.TASK_ID, 'outcome': OUTCOME, 'access_condition': ACCESS,
            'pair_path': str(path(pair_path)), 'pair_sha256': self.PAIR_SHA,
            'task_path': str(path(task_path)), 'task_sha256': self.TASK_SHA,
            'source': self.source_identity(), 'resource_profile': PROFILE, 'programs': records,
            'runtime': write_new(root / 'runtime.json', runtime_raw),
            'deployment_binding_pin': runtime['deployment']['binding_pin'],
            'all_programmes_and_declarations_frozen_before_first_phase': True,
            'AI_attempt': False, 'scientific_improvement': False,
            'execution_authorized_by_construction': False}
        write_new(root / 'PROTOCOL.json', encode(protocol))
        return protocol

    def admit_protocol(self, protocol_path, expected):
        self._captured_actual.clear() if self._protocol_path != path(protocol_path) else None
        self._protocol = self._protocol_path = None
        raw = body(protocol_path)
        need(pin(raw)['sha256'] == expected, 'Selected reference protocol')
        protocol = decode(raw)
        need(protocol['schema'] == 'smc_author_reference_protocol_v1' and protocol['route'] == ROUTE
             and protocol['outcome'] == OUTCOME and protocol['access_condition'] == ACCESS
             and protocol['source'] == self.source_identity() and protocol['resource_profile'] == PROFILE
             and protocol['pair_sha256'] == self.PAIR_SHA and protocol['task_sha256'] == self.TASK_SHA
             and set(protocol['programs']) == set(PHASES)
             and protocol['all_programmes_and_declarations_frozen_before_first_phase'] is True
             and protocol['AI_attempt'] is False and protocol['scientific_improvement'] is False,
             'Exact two-arm reference-only protocol')
        self.public_context(protocol['pair_path'], protocol['task_path'])
        root = path(protocol_path).parent
        bindings_pin = pin(body(self.HERE / 'BINDINGS.json'))
        for phase in PHASES:
            row = protocol['programs'][phase]
            program = body(root / phase / 'program.py', row['program'])
            need(program == body(self.HERE / 'reference_adapter.py'), 'Exact selected adapter')
            declared = decode(body(root / phase / 'declaration.json', row['declaration']))
            need(declared == method_plan(phase, row['program'], bindings_pin), 'Original arm recipe frozen')
            method_path = root / phase / 'METHOD.json'
            need(row['method']['path'] == str(method_path), 'Protocol-owned method freeze')
            frozen = decode(body(method_path, {k: row['method'][k] for k in ('bytes', 'sha256')}))
            need(frozen == {'schema': 'smc_author_reference_method_freeze_v1', 'route': ROUTE,
                'phase_id': phase, 'access_condition': ACCESS, 'plan': declared,
                'program': row['program'], 'declaration': row['declaration'],
                'original_pair_sha256': self.PAIR_SHA, 'test_inputs_released': False},
                'Immutable reference model selection before release')
        runtime = self.runtime_config(decode(body(root / 'runtime.json', protocol['runtime'])))
        need(protocol['deployment_binding_pin'] == runtime['deployment']['binding_pin'],
             'Exact selected deployment retained')
        self._protocol, self._protocol_path = protocol, path(protocol_path)
        return protocol, runtime

    def mounts_for(self, protocol_path, protocol, phase, job_path, job_pin, manifests):
        need(protocol == self._protocol and phase in PHASES, 'Admitted reference job before exposure')
        _, manifests = self.public_context(protocol['pair_path'], protocol['task_path'])
        root = path(protocol['pair_path']).parent / ACCESS
        result = {}
        for row in manifests[ACCESS]['files']:
            name = row['path']
            self.relative(name)
            purpose = 'historical_author_source' if name.startswith('official_source/') or name in (
                'official_source_manifest.json', 'official_asset_manifest.json') else 'input'
            result['/materials/' + name] = self.file_mount(root / name,
                {k: row[k] for k in ('bytes', 'sha256')}, purpose)
        row = protocol['programs'][phase]
        folder = path(protocol_path).parent / phase
        result['/program/program.py'] = self.file_mount(folder / 'program.py', row['program'], 'program')
        result['/declaration.json'] = self.file_mount(folder / 'declaration.json', row['declaration'], 'contract')
        result['/execution.json'] = self.file_mount(job_path, job_pin, 'contract')
        for source, destination in [('reference_worker.py', '/runner/worker.py'),
                                    ('reference_core.py', '/runner/reference_core.py')]:
            result[destination] = self.file_mount(self.HERE / source, pin(body(self.HERE / source)), 'program')
        result['/runner/retained_worker.py'] = self.file_mount(self.repository_root / _base.EPISODE_REL / 'worker.py',
            {'bytes': 11424, 'sha256': '2fc10bb2b608e7f1e4a803588cff1123add5aa7c6fbb92eb6b22cea028a9b473'}, 'program')
        result['/selected_artifacts/BINDINGS.json'] = self.file_mount(self.HERE / 'BINDINGS.json',
            pin(body(self.HERE / 'BINDINGS.json')), 'contract')
        for name, expected in self.bindings['helpers'].items():
            result['/selected_artifacts/author_reference/' + name] = self.file_mount(
                self.HERE / 'helpers' / name, expected, 'historical_author_source')
        need(not any('/test/eval_target' in destination for destination in result),
             'Protected TEST target never enters either author job')
        return result

    def job_for(self, protocol, phase):
        need(phase in PHASES, 'Distinct original model phase')
        row = protocol['programs'][phase]
        return {'schema': 'smc_author_reference_execution_job_v1', 'route': ROUTE,
            'outcome': OUTCOME, 'condition': phase, 'phase_id': phase, 'access_condition': ACCESS,
            'source': protocol['source'], 'resource_profile': PROFILE, 'submission_keys': ['offline'],
            'program_sha256': row['program']['sha256'], 'declaration_sha256': row['declaration']['sha256'],
            'method_freeze_sha256': row['method']['sha256'], 'bindings': pin(body(self.HERE / 'BINDINGS.json')),
            'max_file_bytes': FILE_CAP}

    def captured_predictions(self, receipt, phase, outcome, programme):
        need(outcome == OUTCOME and phase in PHASES and self._protocol is not None,
             'Reference-only owned capture')
        files = receipt['output_inventory']['files']
        need(receipt['output_inventory']['complete'] is True
             and set(files) == {'offline.h5', 'actual_declaration.json', 'RESULT.json', 'OUTPUTS.json'},
             'Complete reference output inventory')
        root = path(receipt['quarantine_root'])
        result = decode(body(root / 'RESULT.json', files['RESULT.json']))
        need(result == {'schema': 'smc_author_reference_program_result_v1', 'route': ROUTE,
            'phase_id': phase, 'access_condition': ACCESS, 'outcome': OUTCOME,
            'program_sha256': programme['program']['sha256'],
            'declaration_sha256': programme['declaration']['sha256'],
            'method_freeze_sha256': programme['method']['sha256'], 'submission_keys': ['offline']},
            'Actual captured model output joins original frozen programme')
        actual = decode(body(root / 'actual_declaration.json', files['actual_declaration.json']))
        need(actual['schema'] == 'smc_author_reference_actual_v1' and actual['route'] == ROUTE
             and actual['phase_id'] == phase and actual['access_condition'] == ACCESS
             and actual['recipe'] == recipe(phase) and actual['role'] == 'author_calibration'
             and actual['method_freeze_sha256'] == programme['method']['sha256']
             and actual['program_sha256'] == programme['program']['sha256']
             and actual['AI_attempt'] is False and actual['scientific_improvement'] is False,
             'Reference actual-use evidence remains distinct from AI improvement')
        prediction = root / 'offline.h5'
        need(prediction.lstat().st_size == files['offline.h5']['bytes']
             and hash_file(prediction) == files['offline.h5']['sha256'], 'Captured original predictions unchanged')
        self._captured_actual[phase] = {'path': str(root / 'actual_declaration.json'),
                                      'pin': files['actual_declaration.json']}
        return {'offline': prediction}

    def _grade_from_owned_pair(self, closed_path, closed_sha, target, evaluator, output, scratch_bytes):
        closed_raw = body(closed_path)
        need(pin(closed_raw)['sha256'] == closed_sha, 'Exact parent-selected closed reference pair')
        closed = validate_reference_pair(decode(closed_raw))
        protocol, runtime = self.admit_protocol(closed['protocol_path'], closed['protocol_sha256'])
        need(closed['source'] == protocol['source'] and closed['runtime_qualification'] == runtime['qualification'],
             'Closed reference pair retains exact qualified source/runtime')
        need(type(scratch_bytes) is int and 0 < scratch_bytes <= 512 * 1024**2,
             'Finite whole-reference snapshot allowance')
        final = path(output)
        root = path(closed_path).parent
        forbidden = (path(protocol['pair_path']).parent,
                     path(closed['protocol_path']).parent, root, self.HERE)
        need(not final.exists() and final.parent.is_dir()
             and not any(final.is_relative_to(folder) for folder in forbidden),
             'New private reference results and snapshots outside public/protocol/owned/source trees')
        original = self.benchmark().original()
        panel_path = path(protocol['pair_path']).parent / ACCESS / 'inputs/mc_maze/test/panel.json'
        originals, freezes, snapshot_pins, total = {}, {}, {}, 0
        for phase in PHASES:
            row = closed['conditions'][phase]
            need(row['receipt_path'] == str(root / 'control' / phase / 'RECEIPT.json')
                 and row['freeze_path'] == str(root / 'freezes' / (phase + '.json')),
                 'Only original owned reference receipts and freezes')
            receipt = decode(body(row['receipt_path'], row['receipt']))
            job = self.job_for(protocol, phase)
            request = read(root / 'jobs' / phase / 'REQUEST.json')
            need(pin(self.request_bytes(request)) == row['request']
                 and request['phase_id'] == phase and request['role'] == 'B'
                 and request['source'] == protocol['source'], 'Exact assisted reference request')
            self.validate_closed(request, receipt)
            predicted = self.captured_predictions(receipt, phase, OUTCOME, protocol['programs'][phase])['offline']
            frozen = decode(body(row['freeze_path'], row['freeze']))
            selected = recipe(phase)
            need(frozen['role'] == 'author_calibration' and frozen['arm'] == selected['arm']
                 and frozen['seed'] == selected['seed'] and frozen['particles'] == 192 and frozen['repeats'] == 32,
                 'Each original frozen model recipe remains separate')
            original.validate_freeze(predicted, panel_path, self.HERE / 'original_protocol.json', row['freeze_path'])
            originals[phase], freezes[phase] = predicted, row['freeze_path']
            snapshot_pins[phase] = receipt['output_inventory']['files']['offline.h5']
            total += snapshot_pins[phase]['bytes']
        # Both complete snapshots and validation precede the first original scorer target read.
        need(total + max(row['bytes'] for row in snapshot_pins.values()) <= scratch_bytes,
             'Both complete snapshots plus one original-scorer snapshot fit charged scratch')
        write_new(root / 'GRADE_STARTED.json', encode({'schema': 'smc_author_reference_grade_once_v1',
                  'closed_pair_sha256': closed_sha, 'both_reference_outputs_authenticated': True}))
        with tempfile.TemporaryDirectory(prefix='.author-reference-grade-', dir=final.parent) as temporary:
            temp = Path(temporary)
            snapshots = {}
            for phase in PHASES:
                destination = temp / (phase + '.h5')
                copy_snapshot(originals[phase], destination, snapshot_pins[phase], scratch_bytes)
                original.validate_freeze(destination, panel_path, self.HERE / 'original_protocol.json', freezes[phase])
                snapshots[phase] = destination
            reports = {}
            for phase in PHASES:
                report_path = temp / (phase + '.json')
                reports[ARMS[phase]] = original.score_predictions(snapshots[phase], panel_path,
                    self.HERE / 'original_protocol.json', freezes[phase], target,
                    original.TARGET_SHA256, evaluator, report_path)
                need(set(reports[ARMS[phase]]['metrics']) == set(METRICS), 'All four original metrics retained')
            need(pin(body(closed_path))['sha256'] == closed_sha, 'Closed reference chain unchanged')
            final_report = {'schema': 'smc_protected_author_reference_results_v1', 'route': ROUTE,
                'closed_pair_sha256': closed_sha, 'access_condition': ACCESS,
                'models': reports, 'AI_attempt': False, 'scientific_improvement': False,
                'independent_replication_established': False,
                'inference_repeats_are_independent_models': False,
                'historical_checkpoint_printed_row_linkage': 'unresolved',
                'target_exposure': 'original_public_TEST_since_2026_01', 'SOTA_claim': False}
            write_new(final, encode(final_report))
        return final_report


class ReferenceBenchmark:
    def __init__(self, episode):
        self.episode = episode
        self._original = None

    def original(self):
        if self._original is None:
            self._original = load_module('_smc_reference_original_scorer',
                self.episode.HERE / 'helpers/scorer.py', self.episode.bindings['helpers']['scorer.py'])
        return self._original

    def inspect_pair(self, pair_path, pair_sha, task_path, task_sha, *, max_bytes):
        e = self.episode
        need(pair_sha == e.PAIR_SHA and task_sha == e.TASK_SHA, 'Exact reference materials')
        pair, manifests = e.public_context(pair_path, task_path)
        rows = manifests[ACCESS]['files']
        need(sum(row['bytes'] for row in rows) <= max_bytes, 'Original assisted-material byte cap')
        root = path(pair_path).parent / ACCESS
        for row in rows:
            e.relative(row['path'])
            filename = root / row['path']
            need(filename.lstat().st_size == row['bytes'] and hash_file(filename, max_bytes) == row['sha256'],
                 'Complete authentic assisted input/source identity before model release')
        return pair

    def freeze(self, pair_path, pair_sha, task_path, task_sha, phase, outcome, predictions,
               declaration_path, destination, *, max_bytes):
        e = self.episode
        need(outcome == OUTCOME and phase in PHASES and set(predictions) == {'offline'}
             and phase in e._captured_actual, 'Actual closed reference capture before original freeze')
        e.public_context(pair_path, task_path)
        selected = recipe(phase)
        declaration = read(declaration_path)
        need(declaration['recipe'] == selected and declaration['access_condition'] == ACCESS,
             'Original reference selection frozen before execution')
        return self.original().freeze_predictions(predictions['offline'],
            path(pair_path).parent / ACCESS / 'inputs/mc_maze/test/panel.json',
            e.HERE / 'original_protocol.json', destination,
            arm=selected['arm'], method_id='smc-released36d-' + selected['arm'],
            role='author_calibration', seed=selected['seed'], particles=192, repeats=32)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--pair', required=True)
    parser.add_argument('--runtime', required=True)
    parser.add_argument('--runtime-sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    source_identity(HERE, args.source_sha256)
    episode = ReferenceEpisode(args.repository, HERE)
    return episode.instantiate(args.pair, HERE / 'REFERENCE_TASK.json',
                               args.runtime, args.runtime_sha256, args.output)


if __name__ == '__main__':
    main()
