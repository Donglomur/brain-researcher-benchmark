"""Actual source-owned isolated worker composition over the reviewed Engine mechanism."""
from pathlib import Path
import hashlib
from core import need, encoded, pin, publish, fresh, capture, parse, integer
from engine import Engine
from contracts import identity
from operative import source as effective_source

COMMON = ('core.py', 'contracts.py', 'array_io.py', 'worker_common.py')
ENTRIES = {'candidate': 'candidate_worker', 'analysis': 'analysis_worker', 'selection': 'selection_worker',
           'reference': 'reference_worker'}


def seed(parts):
    return int.from_bytes(hashlib.sha256(encoded(['neural049-method-seed-v1', list(parts)])).digest()[:4], 'big')


def numeric_limits(profile):
    return {k: profile['numeric_'+k] for k in ('read_bytes','write_bytes','serialized_bytes','allocation_bytes','live_bytes','elements','work','files')}


class Transport:
    def __init__(self, a, captured, budget, artifacts, record, bank):
        self.a, self.captured, self.budget, self.artifacts, self.record, self.bank = a, captured, budget, artifacts, record, bank
        self.engines = {role: Engine(a['native_'+role], budget, record, gallery=bank) for role in ('public','private')}
        from records import Records
        root = fresh(Path(a['roots']['output'])/'operations',budget)
        self.results = Records(root,budget,a['resources']['record_bytes'],a['resources']['index_bytes'])

    def sources(self, role, implementation=None):
        names = list(COMMON) + [ENTRIES[role]+'.py']
        if role == 'reference':
            need(implementation in ('r1','r2'), 'only exact selected independent bank')
            names = ['core.py', 'reference_worker.py']
        files = {}; originals = {}; mounts = []
        for name in names:
            original,desc = effective_source(self.captured['manifest'],'program/'+name)
            files[name] = desc; originals[name] = original
        if role == 'reference':
            prefix = 'references/'+implementation+'/'
            for original, desc in self.captured['manifest']['files'].items():
                if original.startswith(prefix) and original.endswith('.py'):
                    effective,desc = effective_source(self.captured['manifest'],original)
                    files[original] = desc; originals[original] = effective
            need(any(x.startswith(prefix) for x in files), 'full exact selected bank source')
        for alias, original in originals.items():
            desc = files[alias]; source = Path(self.a['roots']['source'])/original
            self.artifacts.capture(source, desc, self.a['resources']['source_bytes'], retain=False)
            mounts.append({'source': str(source), 'destination': '/inputs/source/'+alias, 'pin': desc, 'bytes_cap': desc['bytes']})
        return files, originals, mounts

    def invoke(self, operation, role, profile_name, request, mounts, *, implementation=None,
               expected=None, optional=None, paired_seed=None, cutoff=None):
        need(operation not in self.results and role in ENTRIES, 'unique concrete worker operation')
        profile = self.a['profiles'][profile_name]; now = self.budget.tick()
        engine = self.engines['private' if role in ('reference','selection') else 'public']
        parent_end = self.a['clock']['production_end'] if engine.scope is None else engine.scope['cutoff']
        cutoff = min(self.a['clock']['production_end'], now+profile['seconds'], now+profile['cpu_ns']/profile['cpu_rate_ns'],
                     (cutoff if cutoff is not None else parent_end)-profile['retirement_seconds'],
                     parent_end-profile['retirement_seconds'])
        need(cutoff > now, 'sufficient positive phase remainder before effects')
        root = Path(self.a['roots']['reference' if role in ('reference','selection') else 'output'])
        job = fresh(root/operation, self.budget); output = fresh(job/'native', self.budget)
        target = '/artifacts/'+hashlib.sha256(operation.encode()).hexdigest() if role == 'reference' else '/output'
        request = dict(request)
        if role == 'reference':
            request.update(origin=self.budget.origin, deadline=cutoff, qualified_execution=True)
        else:
            request.update(schema='neural049_worker_request_v1', source_manifest=self.captured['pin'],
                operation=operation, origin=self.budget.origin, deadline=cutoff,
                seed=seed(paired_seed if paired_seed is not None else [operation]),
                limits={k: profile['numeric_'+k] for k in ('allocation_bytes','elements','serialized_bytes','files','work')})
        raw = encoded(request); need(len(raw) <= self.a['resources']['view_bytes'], 'complete request cap before publication')
        reqpin = publish(job/'REQUEST.json', raw, self.budget, readonly=True)
        files, aliases, source_mounts = self.sources(role, implementation)
        wc = {'qualified_execution': True, 'request_path': '/inputs/REQUEST.json', 'request_pin': reqpin,
              'request_cap': self.a['resources']['view_bytes'], 'source_manifest': self.captured['pin'],
              'origin': self.budget.origin, 'deadline': cutoff, 'operation': operation, 'output': target,
              'read_cap': profile['numeric_read_bytes'], 'write_cap': profile['numeric_write_bytes']}
        if role == 'reference':
            wc.update(implementation=implementation, reference_source_identity=request['source_identity'], reference_limits=numeric_limits(profile))
        config = {'schema': 'neural049_sandbox_v1', 'original_origin': self.budget.origin, 'deadline': cutoff,
                  'clock_domain': 'qualified_shared_host_monotonic', 'source_read_bytes': self.a['resources']['source_bytes'],
                  'source_manifest': self.captured['pin'], 'files': files, 'request': reqpin,
                  'entry': ENTRIES[role], 'role': role, 'worker_config': wc}
        cp = publish(job/'LAUNCH.json', encoded(config), self.budget, readonly=True)
        launch = self.captured['manifest']['files']['program/sandbox_launcher.py']
        all_mounts = source_mounts + list(mounts) + [
            {'source': str(job/'REQUEST.json'), 'destination': '/inputs/REQUEST.json', 'pin': reqpin, 'bytes_cap': reqpin['bytes']},
            {'source': str(job/'LAUNCH.json'), 'destination': '/inputs/LAUNCH.json', 'pin': cp, 'bytes_cap': cp['bytes']},
            {'source': str(Path(self.a['roots']['source'])/'program/sandbox_launcher.py'), 'destination': '/inputs/LAUNCHER.py',
             'pin': launch, 'bytes_cap': launch['bytes']}]
        argv = [self.a['native_python'], '-I', '-B', '/inputs/LAUNCHER.py', '/inputs/LAUNCH.json',
                str(cp['bytes']), cp['sha256'], repr(self.budget.origin), repr(cutoff)]
        result = engine.execute(operation, argv, all_mounts, str(output), profile, cutoff,
                                self.captured['pin'], expected, optional_artifacts=optional, output_target=target)
        self.budget.tick()
        row = {'operation': operation, 'role': role, 'profile': profile_name,
               'request': {'path': str(job/'REQUEST.json'), 'pin': reqpin},
               'launch': {'path': str(job/'LAUNCH.json'), 'pin': cp}, 'request_value': request,
               'source_aliases': aliases, 'mounts': all_mounts, 'argv': argv, 'output': str(output),
               'container_output': target, 'native': result}
        self.results[operation] = row
        self.record({'kind': 'operation_completed', 'operation': operation, 'record': row})
        return row

    def reference_plan(self, operation):
        name = 'RESULT.json' if operation == 'predict' else 'STATE.json'
        required = {'result/'+n: self.a['resources']['state_bytes'] for n in (name, 'WORK.json', 'RECEIPT.json')}
        optional = {}
        for width in (6,8):
            for i in range(128): optional['result/arrays/'+str(i).zfill(width)+'.npy'] = self.a['resources']['array_bytes']
        return required, optional

    def remount(self, produced):
        return [{'source': str(Path(produced['output'])/name), 'destination': produced['container_output']+'/'+name,
                 'pin': desc, 'bytes_cap': desc['bytes']} for name, desc in produced['native']['artifacts'].items()]
