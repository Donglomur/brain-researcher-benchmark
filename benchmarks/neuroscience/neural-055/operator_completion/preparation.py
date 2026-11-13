"""Concrete operator assembly around the unchanged S8 scientific executables.

Importing this module does not load NumPy, data, a model or a native provider.
An explicitly invoked operation may run the retained scientific preparers.
"""
import hashlib
import os
from pathlib import Path
import stat
import time

from source_closure import (RuntimeSupport, absolute, identity, need, parse,
                            preparation_bodies, read_exact, relative)

PEOPLE = tuple('sub-%02d' % i for i in range(1, 11))
LAUNCHER = b'''"""Use only the restored preparation/public import closure."""
import os, runpy, sys
from pathlib import Path
root=Path(__file__).absolute().parent
allowed={'stage_source.py','build_case.py','build_panel.py'}
if len(sys.argv)<2 or sys.argv[1] not in allowed:raise ValueError('closed preparation entry')
script=root/'private'/'preparation'/sys.argv[1]
sys.path[:0]=[str(root/'private'/'preparation'),str(root/'public')]
sys.argv=[str(script),*sys.argv[2:]]
runpy.run_path(str(script),run_name='__main__')
'''


def exact_keys(value, keys):
    need(type(value) is dict and set(value) == set(keys), 'exact operator specification fields')


def positive(value, label):
    need(type(value) is int and value > 0, 'positive ' + label)
    return value


class Session:
    """One fresh operator output and the existing S8 process/error recorder."""
    def __init__(self, context, source_root, operator_root, output, python, limits,
                 origin, cpu_origin, bootstrap_reads=0, stream_cap=1048576):
        self.context = context; self.source_root = absolute(source_root)
        self.operator_root = absolute(operator_root); self.output = absolute(output)
        self.python = str(absolute(python)); self.stream_cap = positive(stream_cap, 'stream cap')
        need(self.stream_cap <= limits['stream_bytes'], 'stream cap within selected operator lifetime')
        self.support = RuntimeSupport(context)
        try:
            m = self.support.modules
            self.budget = m['budget'].Budget(origin, limits, cpu_origin=cpu_origin)
            self.budget.read(bootstrap_reads)
            self.carrier = m['common'].FailureCarrier()
            self.journal = m['journal'].Journal(self.output, self.budget, self.carrier)
            self.runner = m['process'].ProcessRunner(self.budget, self.journal, self.carrier)
        except BaseException:
            self.support.close()
            raise
        self.layout = None; self.restored = {}; self.operations = []; self.first = None

    def mkdir(self, name):
        p = self.output / relative(name)
        need(not p.exists() and p.parent.is_dir(), 'fresh owned directory with existing parent')
        self.budget.check('before owned directory creation')
        p.mkdir(mode=0o700)
        return p

    def write(self, name, raw):
        return self.journal.write(str(relative(name)), raw)

    def json(self, name, value):
        self.journal.json(str(relative(name)), value)
        return self.identify(self.output / relative(name), 16777216, relative_to=self.output)

    def identify(self, path, cap, *, relative_to=None):
        """Hash ordinary current files, streaming bytes without decoding arrays."""
        p = absolute(path); before = p.lstat()
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             'bounded ordinary current artifact')
        self.budget.read(before.st_size + 1)
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        h = hashlib.sha256(); n = 0
        try:
            need(identity(os.fstat(fd)) == identity(before), 'same artifact handle')
            while n <= before.st_size:
                self.budget.check('artifact hashing')
                chunk = os.read(fd, min(65536, before.st_size + 1 - n))
                if not chunk:
                    break
                n += len(chunk); h.update(chunk)
            need(n == before.st_size and identity(os.fstat(fd)) == identity(before) == identity(p.lstat()),
                 'stable complete artifact hash')
        finally:
            os.close(fd)
        name = str(p if relative_to is None else p.relative_to(relative_to))
        return {'path': name, 'bytes': n, 'sha256': h.hexdigest()}

    def selected(self, descriptor, cap=16777216):
        need(type(descriptor) is dict and {'path', 'bytes', 'sha256'} <= set(descriptor), 'explicit current input descriptor')
        p = absolute(descriptor['path'])
        return read_exact(p, descriptor, cap, self.budget.read)

    def restore(self):
        if self.layout is not None:
            return self.layout
        self.layout = self.mkdir('preparation_source')
        for name in ('private', 'private/preparation', 'public'):
            self.mkdir('preparation_source/' + name)
        selected = preparation_bodies(self.context)
        selected['run_preparation.py'] = LAUNCHER
        for role, raw in selected.items():
            name = 'preparation_source/' + role
            self.write(name, raw); p = self.output / name
            os.chmod(p, 0o444)
            self.restored[role] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'mode': '0o444'}
        for p in (self.layout / 'private/preparation', self.layout / 'private', self.layout / 'public', self.layout):
            os.chmod(p, 0o555)
        self.json('RESTORED_SOURCE.json', {'schema': 'neural055-restored-preparation-source-v1',
                  'runtime_source': self.context['identity'], 'files': self.restored,
                  'original_scientific_bodies_modified': False})
        return self.layout

    def dispatch(self, label, argv, kind='operator_preparation'):
        """The real existing runner; controls replace this scientific boundary only."""
        self.budget.check('before retained executable dispatch')
        env = {k: v for k, v in os.environ.items() if not k.startswith('PYTHON')}
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        result = self.runner.run(label, argv, self.budget.deadline, self.stream_cap,
                                 kind=kind, cwd=str(self.output), env=env)
        self.operations.append(result.document())
        return result

    def legacy(self, label, script, argv):
        need(script in ('stage_source.py', 'build_case.py', 'build_panel.py'), 'closed retained scientific entry')
        layout = self.restore()
        for name, d in self.restored.items():
            read_exact(layout / name, d, 1048576, self.budget.read)
        return self.dispatch(label, [self.python, '-I', '-B', str(layout / 'run_preparation.py'), script, *map(str, argv)])

    def stage(self, spec):
        exact_keys(spec, ('metadata', 'participants'))
        need(type(spec['participants']) is list and [r.get('person') for r in spec['participants']] == list(PEOPLE),
             'all ten original participants in source order')
        self.selected(spec['metadata'], 2097152)
        archive_hashes = set()
        for row in spec['participants']:
            exact_keys(row, ('person', 'archive', 'archive_pin'))
            pin = row['archive_pin']; person = row['person']
            need(type(pin) is dict and pin.get('participant') == person and pin.get('filename') == person + '.zip'
                 and type(pin.get('osf_id')) is str and pin['osf_id'] and type(pin.get('version')) is int and pin['version'] >= 1,
                 'explicit original participant-to-archive binding')
            positive(pin.get('bytes'), 'source archive extent')
            need(type(pin.get('sha256')) is str and len(pin['sha256']) == 64
                 and all(c in '0123456789abcdef' for c in pin['sha256']), 'exact source archive identity')
            absolute(row['archive']); archive_hashes.add(pin['sha256'])
        need(len(archive_hashes) == 10, 'ten distinct source archives')
        self.mkdir('people'); self.mkdir('source_pins')
        self.json('source_pins/METADATA.json', {k: spec['metadata'][k] for k in ('bytes', 'sha256')})
        staged = {}; staged_bodies = {}
        for row in spec['participants']:
            person = row['person']; target = self.output / 'people' / person
            self.json('source_pins/' + person + '.json', row['archive_pin'])
            self.legacy('stage-' + person, 'stage_source.py', [
                '--archive', row['archive'], '--archive-pin', self.output / 'source_pins' / (person + '.json'),
                '--metadata', spec['metadata']['path'], '--metadata-pin', self.output / 'source_pins/METADATA.json',
                '--participant', person, '--output', target])
            d = self.identify(target / 'STAGED.json', 1048576, relative_to=self.output)
            value = parse(read_exact(target / 'STAGED.json', d, 1048576, self.budget.read))
            need(value['schema'] == 'neural055-safe-staged-person-v1' and value['participant'] == person
                 and value['source_archive'] == row['archive_pin'], 'actual staged participant and archive join')
            need(value['source_metadata'] == {k: spec['metadata'][k] for k in ('bytes', 'sha256')},
                 'same exact staged metadata source')
            staged[person] = d; staged_bodies[person] = value
        snapshot = self.support.source_snapshot(self.context, self.source_root, self.budget)
        snapshot.legacy_module('private/preparation/metadata_core.py').validate_staged_participant_bindings(staged_bodies)
        index = self.json('STAGING_INDEX.json', {'schema': 'neural055-staging-index-v1', 'people': staged})
        return {'schema': 'neural055-staging-assembly-result-v1', 'artifact_root': str(self.output), 'staging_index': index,
                'people': list(PEOPLE), 'join_attestation_still_external': True,
                'full_neural_input_qualification_claimed': False}

    def seal_public(self, root):
        """Change only a newly-created case owned by this invocation."""
        root = absolute(root)
        need(root.is_relative_to(self.output / 'cases') and root.name == 'public', 'owned fresh public case only')
        expected = {'CASE.json', 'ASSETS.json', 'TRAINING.json', 'coordinates.json', 'query.npy',
                    'candidate_features.npy', 'training_image_features.npy'}
        assets = parse(read_exact(root / 'ASSETS.json', self.identify(root / 'ASSETS.json', 1048576), 1048576, self.budget.read))
        td = assets['training']; need(td['path'] == 'TRAINING.json', 'exact original training metadata name')
        training = parse(read_exact(root / 'TRAINING.json', td, 16777216, self.budget.read))
        need(type(training.get('people')) is list and len(training['people']) == 9, 'nine original training participants')
        for row in training['people']:
            name = row['eeg']['path']; relative(name)
            need(name == 'train/' + row['person_id'] + '.npy' and row['person_id'] in PEOPLE,
                 'original participant training filename')
            expected.add(name)
        need(len(expected) == 16, 'nine unique training files and seven fixed public files')
        actual = set(); directories = []
        for p in (root, root / 'train'):
            s = p.lstat(); need(stat.S_ISDIR(s.st_mode) and not p.is_symlink(), 'ordinary owned public directory')
            directories.append(p)
            with os.scandir(p) as iterator:
                for entry in iterator:
                    path = Path(entry.path); s = entry.stat(follow_symlinks=False)
                    if stat.S_ISDIR(s.st_mode):
                        need(path == root / 'train', 'only original train directory')
                    else:
                        need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'ordinary single-link public artifact')
                        actual.add(str(path.relative_to(root)))
        need(actual == expected, 'complete exact public-only namespace before finalization')
        for name in sorted(actual):
            p = root / name; before = p.lstat()
            fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
            try:
                need(identity(os.fstat(fd)) == identity(before), 'same owned permission handle')
                os.fchmod(fd, 0o444)
                need(identity(os.fstat(fd)) == identity(p.lstat()), 'same finalized public file')
            finally:
                os.close(fd)
        for p in reversed(directories):
            os.chmod(p, 0o555)
        return {'public_root': str(root), 'files': len(actual), 'file_mode': '0o444', 'directory_mode': '0o555'}

    def assemble(self, spec):
        exact_keys(spec, ('staging_index', 'feature_manifest', 'join_attestation', 'id_key_file', 'maximum_case_output_bytes'))
        positive(spec['maximum_case_output_bytes'], 'complete per-case output ceiling')
        for key in ('staging_index', 'feature_manifest', 'join_attestation', 'id_key_file'):
            self.selected(spec[key], 16777216 if key != 'id_key_file' else 1048576)
        stage = parse(self.selected(spec['staging_index']))
        need(set(stage) == {'schema', 'people'} and stage['schema'] == 'neural055-staging-index-v1'
             and set(stage['people']) == set(PEOPLE), 'complete original ten-person staging index')
        attest = parse(self.selected(spec['join_attestation']))
        need(attest.get('staging_index_sha256') == spec['staging_index']['sha256'], 'genuine attestation of this produced staging index')
        self.mkdir('cases'); roots = []; cases = []; seals = []
        for person in PEOPLE:
            root = self.output / 'cases' / person
            argv = []
            for key, option in (('staging_index', '--staging-index'), ('feature_manifest', '--feature-manifest'),
                                ('join_attestation', '--join-attestation'), ('id_key_file', '--id-key-file')):
                argv.extend((option, spec[key]['path']))
            argv.extend(('--heldout', person, '--output', root, '--max-output-bytes', spec['maximum_case_output_bytes']))
            self.legacy('case-' + person, 'build_case.py', argv)
            d = self.identify(root / 'PREPARED.json', 1048576)
            prepared = parse(read_exact(root / 'PREPARED.json', d, 1048576, self.budget.read))
            need(prepared['schema'] == 'neural055-prepared-case-v1' and prepared['outer_participant'] == person,
                 'actual complete original case output')
            need(prepared['public_case']['path'] == 'public/CASE.json'
                 and prepared['public_assets']['path'] == 'public/ASSETS.json'
                 and prepared['private_target']['path'] == 'private/TARGET.json', 'separate original public and private roles')
            pub = root / 'public'
            seals.append(self.seal_public(pub))
            case = {'person': person, 'public_root': str(pub)}
            for name, key in (('CASE.json', 'public_case'), ('ASSETS.json', 'public_assets')):
                actual = self.identify(pub / name, 1048576)
                need(all(actual[k] == prepared[key][k] for k in ('bytes', 'sha256')), 'unchanged original prepared public identity')
                case[name] = {k: actual[k] for k in ('bytes', 'sha256')}
            cases.append(case); roots.append(root)
        panel = self.output / 'panel'; argv = []
        for root in roots:
            argv.extend(('--case-root', root))
        argv.extend(('--output', panel))
        self.legacy('panel', 'build_panel.py', argv)
        public = self.identify(panel / 'public/PANEL.json', 1048576)
        private = self.identify(panel / 'private/PANEL.json', 1048576, relative_to=self.output)
        index = self.json('INPUT_INDEX.json', {'schema': 'neural055-full10-input-index-v1', 'cases': cases, 'public_panel': public})
        snapshot = self.support.source_snapshot(self.context, self.source_root, self.budget)
        consumer = self.support.modules['inputs'].OriginalInputs(snapshot, self.budget)
        descriptor = dict(index, mode='0o600', role='full10_public_input_index')
        actual = consumer.inspect(self.output, descriptor)
        need(actual.original_plan['cases'] == 10 and actual.original_plan['query_count'] == 2000,
             'actual unchanged full10 consumer accepts constructed index')
        self.json('PUBLIC_TREE_FINALIZATION.json', {'schema': 'neural055-owned-public-tree-finalization-v1', 'cases': seals})
        return {'schema': 'neural055-complete-input-assembly-v1', 'artifact_root': str(self.output), 'input_index': descriptor,
                'protected_panel': dict(private, mode=oct(stat.S_IMODE((panel / 'private/PANEL.json').stat().st_mode)), role='protected_panel'),
                'original_public_plan': actual.original_plan, 'original_input_qualification_still_required': True}

    def compile_plan(self, mode, spec, execute=False):
        from plans_v2 import build_campaign_plan, build_feature_plan, encode_plan, central_entry_argv
        need(mode in ('prepare-features', 'run'), 'existing scientific entry mode')
        plan = build_feature_plan(spec, self.context) if mode == 'prepare-features' else build_campaign_plan(spec, self.context)
        name = 'FEATURE_PLAN.json' if mode == 'prepare-features' else 'CAMPAIGN_PLAN.json'
        raw = encode_plan(plan); self.write(name, raw)
        output = self.output / ('features' if mode == 'prepare-features' else 'campaign')
        call = central_entry_argv(mode, plan, python=self.python, source_root=str(self.source_root),
                                 operator_root=str(self.operator_root), output=str(output), plan_path=str(self.output / name))
        need(call['plan_pin'] == {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}, 'actual written plan body joins original argv')
        self.json('COMMAND.json', call)
        result = {'schema': 'neural055-compiled-operator-plan-v1', 'mode': mode, 'plan': call['plan_pin'],
                  'plan_path': str(self.output / name), 'argv': call['argv'], 'executed': False}
        if execute:
            self.dispatch('original-' + mode, call['argv'], kind='feature_preparation' if mode == 'prepare-features' else 'campaign')
            terminal_pin = self.identify(output / 'TERMINAL.json', 16777216)
            terminal = parse(read_exact(output / 'TERMINAL.json', terminal_pin, 16777216, self.budget.read))
            need(terminal.get('schema') == 'neural055-original-complete-terminal-v1'
                 and terminal['status'] == 'complete' and terminal['mode'] == mode, 'actual original scientific terminal completion')
            result.update(executed=True, original_terminal=terminal_pin)
            if mode == 'prepare-features':
                result['feature_manifest'] = self.identify(output / 'FEATURE_MANIFEST.json', 1048576)
        return result

    def finish(self, result=None, error=None):
        """Preserve partial owned state; never claim a failed operation completed."""
        try:
            if error is not None:
                self.carrier.fail(error, 'operator')
            terminal = {'schema': 'neural055-operator-terminal-v1', 'status': 'complete' if error is None else 'unavailable',
                        'result': result, 'errors': self.carrier.document(), 'operations': self.operations,
                        'costs': self.budget.snapshot(), 'scientific_qualification_claimed': False,
                        'measurement_scope': 'existing process CPU/wall/streams plus explicit controller transfers; child native logical I/O and RSS are not measured here'}
            durable = self.journal.terminal(terminal)
            need(durable, 'original operator terminal durable')
            return terminal
        finally:
            self.support.close()
