"""Actual fixed-mount process producer and source-bound output return path."""
import base64
import os
from pathlib import Path
from wire import Ledger as WireLedger
from store import FileStore
from linux_backend import LinuxBackend
from n079_common import require, fields, integer, checked_pin, pin, identity, close_all


class ChargedWireLedger(WireLedger):
    """Conservative backend reservation mapping, never unique physical I/O."""
    def __init__(self, context, limits):
        self.context = context; self.work_id = 'supervisor'
        super().__init__(limits, context.clock.origin, context.clock.scientific, context.clock.closeout, context.clock.outer)

    def reserve(self, charges, phase, *, cutoff='scientific'):
        # Generic donor reads mix source/data/metadata. Reserve their full bound
        # against each source/data dimension, preserving the original generic
        # counter rather than claiming an observed separation or unique sum.
        delta = {}
        if charges.get('read_bytes'):
            delta['source_read_bytes'] = charges['read_bytes']; delta['data_read_bytes'] = charges['read_bytes']
        if charges.get('write_bytes'):
            delta['write_bytes'] = charges['write_bytes']
        if charges.get('processes'):
            delta['process_starts'] = charges['processes']
        if delta:
            self.context.ledger.charge(self.work_id, delta, 'backend conservative bound: ' + phase, cutoff)
        super().reserve(charges, phase, cutoff=cutoff)


class JobSupervisor:
    def __init__(self, context, selected):
        context.require_effect('candidate_job', 'supervisor')
        fields(selected, ('backend', 'logical_limits', 'store_root', 'admission_pin', 'worker_sources', 'role_commands'))
        checked_pin(selected['admission_pin'])
        context.authority.exchange('concrete_namespace_backend', selected)
        self.context, self.selected = context, selected
        self.ledger = ChargedWireLedger(context, selected['logical_limits'])
        self.store = None; self.backend = None; self.results = {}; self.closed = False
        try:
            self.store = FileStore(selected['store_root'], self.ledger)
            self.backend = LinuxBackend(self.store, self.ledger, selected['backend'])
        except BaseException as error:
            self.close(error); raise

    def run(self, request):
        fields(request, ('schema', 'context', 'work_id', 'role', 'sources', 'view', 'binding', 'argv',
                         'request_pin', 'view_evidence', 'program_evidence'))
        require(request['schema'] == 'n079_actual_job_v1' and request['context'] not in self.results,
                'fresh once-only source-owned job context')
        require(request['role'] in self.selected['role_commands'], 'selected producer role')
        require(request['work_id'] in self.context.ledger.local, 'actual full work allocation')
        for key in ('request_pin', 'view_evidence', 'program_evidence'):
            checked_pin(request[key])
        require(request['argv'] == self.selected['role_commands'][request['role']], 'exact source-selected producer command')
        record = {'context': request['context'], 'work_id': request['work_id'], 'phase': 'admitting',
                  'request_pin': request['request_pin'], 'closure': None, 'output': None, 'failure': None}
        self.results[request['context']] = record
        self.ledger.work_id = request['work_id']
        try:
            self.context.authority.exchange('actual_complete_process_view', request)
            files = {}
            worker_sources = self.worker_sources(request)
            for name, item in request['sources'].items():
                fields(item, ('body_base64', 'pin'))
                checked_pin(item['pin'])
                require(len(item['body_base64']) <= 4 * ((item['pin']['bytes'] + 2) // 3), 'bounded source encoding before decode')
                raw = base64.b64decode(item['body_base64'], validate=True)
                require(pin(raw) == item['pin'], 'exact staged source body')
                if name in worker_sources:
                    require(item['pin'] == worker_sources[name], 'unchanged admitted trusted worker source')
                else:
                    require(name in ('/program/method.py', '/request/request.json'), 'only declared generated method/request')
                files[name] = raw
            require(set(worker_sources) <= set(files), 'all source-owned worker dependencies present')
            token = self.backend.stage_exact(request['context'], files, request['view'], request['binding'],
                                            self.ledger.origin, self.ledger.scientific)
            record['stage_token'] = token; record['phase'] = 'staged'
            result = self.backend.launch_exact(token, request['argv'], request['binding'], self.ledger.origin, self.ledger.scientific)
            record['phase'] = 'producer_returned'
            job = self.backend.jobs[request['context']]
            require(job['result']['natural_exit'] and job['result']['exit_code'] == 0 and job['result']['stream_eof'],
                    'actual natural complete producer return')
            # Independently authenticated observer checks selected source,
            # process/cgroup identity, both full streams and quiescence. A
            # producer-supplied result flag cannot close this path.
            inventory = self.backend.inventory(job)
            observed = {'job': request['context'], 'stage_token': token, 'binding': request['binding'],
                        'process': {'pid': job['process'].pid, 'command_pin': job['command_pin']},
                        'cgroup': job['cgroup'], 'cgroup_identity': job['cgroup_identity'],
                        'output': job['output'], 'output_identity': job['output_identity'],
                        'observation': job['observation'],
                        'observation_identity': [os.stat(job['observation'], follow_symlinks=False).st_dev,
                                                 os.stat(job['observation'], follow_symlinks=False).st_ino],
                        'inventory': inventory, 'streams': job['stream_inventory'],
                        'result': {k: job['result'][k] for k in ('exit_code', 'natural_exit', 'stream_eof', 'finished_ns', 'forced_stop')}}
            record['closure'] = self.context.authority.exchange('independent_producer_observation', observed)
            job['inventory'] = inventory; job['observer_closed'] = True
            # Read exact index only after observed closure, including EOF. Full
            # index schemas are checked by the selected scientific consumer.
            index = result['index']
            require(index['bytes'] <= self.context.profile['reader_limits']['file_bytes'], 'complete result-index cap')
            raw = self.backend.read_closed_output(request['context'], index['path'], 0, index['bytes'])
            require(not self.backend.read_closed_output(request['context'], index['path'], index['bytes'], 1), 'exact result-index EOF')
            require(pin(raw) == {k: index[k] for k in ('bytes', 'sha256')}, 'actual complete result-index identity')
            from ach_resource_common import bounded_decode
            record['output'] = bounded_decode(raw, self.context.encoding_limits)
            record['inventory'] = inventory; record['phase'] = 'closed'
            self.context.journal.append('complete_job', record)
            self.context.tick(); return record
        except BaseException as error:
            from n079_common import error_record
            record['phase'] = 'failed'; record['failure'] = error_record(error)
            record['backend_prefix'] = self.ledger.report()
            error.n079_prefix = record
            from ach_resource_common import collect_errors
            collect_errors([('failed job prefix retention', lambda: self.context.journal.append('failed_job', record, 'closeout'))], error)
            raise
        finally:
            self.ledger.work_id = 'supervisor'

    def worker_sources(self, request):
        if request['role'] == 'native':
            return self.selected['worker_sources']['native']
        from n079_plan import bundles
        matches = [b for b in bundles() if b['id'] == request['binding']['bundle']]
        require(len(matches) == 1, 'one actual canonical candidate bundle selects its tool support')
        return self.selected['worker_sources'][matches[0]['tool']][request['role']]

    def promote(self, context_id, name, material_name):
        require(context_id in self.results and self.results[context_id]['phase'] == 'closed', 'observed complete producer before promotion')
        job = self.backend.jobs[context_id]; matches = [x for x in job['inventory'] if x['path'] == name]
        require(len(matches) == 1, 'actual observed output member')
        item = matches[0]
        relative = (Path(job['output']) / name).relative_to(Path(self.selected['backend']['material_root'])).as_posix()
        evidence = self.context.authority.exchange('immutable_observed_output_promotion',
            {'job': context_id, 'output': item, 'material_name': material_name, 'relative_path': relative,
             'observation': self.results[context_id]['closure']})
        require(material_name not in self.backend.materials.catalog, 'fresh immutable material identity')
        selected = {'relative_path': relative, 'pin': {k: item[k] for k in ('bytes', 'sha256')}, 'immutable_admission': evidence}
        self.backend.materials.catalog[material_name] = selected
        return {'path': material_name, **selected['pin']}

    def close(self, primary=None):
        if self.closed:
            return
        self.closed = True; operations = []
        if self.backend is not None:
            fd = self.backend.materials.fd; self.backend.materials.fd = None
            operations.append(('backend material root', lambda: os.close(fd)))
        if self.store is not None:
            operations.append(('owned staging root', self.store.close))
        close_all(operations, primary)

    def register_report_material(self, bundle_id, object, material_name, relative_path):
        payload = {'bundle_id': bundle_id, 'object': object, 'material_name': material_name, 'relative_path': relative_path}
        evidence = self.context.authority.exchange('admit_report_material', payload)
        require(material_name not in self.backend.materials.catalog, 'fresh public report metadata material')
        descriptor = {'path': material_name, **{k: object[k] for k in ('bytes', 'sha256')}}
        registration = {'relative_path': relative_path, 'pin': {k: object[k] for k in ('bytes', 'sha256')}, 'immutable_admission': evidence}
        self.backend.materials.catalog[material_name] = registration
        self.context.journal.append('actual_report_material_registration', {'payload': payload, 'registration': registration})
        return {'descriptor': descriptor, 'registration': registration}

    def register_public_materials(self, catalog, export_evidence):
        evidence = self.context.authority.exchange('admit_outer_public_materials',
            {'catalog': catalog, 'export_evidence': export_evidence})
        require(type(catalog) is dict and catalog, 'complete actual public material roster')
        for name, row in catalog.items():
            require(name not in self.backend.materials.catalog or self.backend.materials.catalog[name] == row,
                    'actual public export never replaces different material')
        self.backend.materials.catalog.update(catalog)
        self.context.journal.append('actual_public_material_registration', {'catalog': catalog, 'evidence': evidence})
        return {'registered': sorted(catalog), 'evidence': evidence}

    def material_record(self, material_name):
        require(material_name in self.backend.materials.catalog, 'actual immutable promoted material')
        result = self.backend.materials.catalog[material_name]
        self.context.journal.append('promoted_material_registry_read', {'name': material_name, 'record': result})
        return result
