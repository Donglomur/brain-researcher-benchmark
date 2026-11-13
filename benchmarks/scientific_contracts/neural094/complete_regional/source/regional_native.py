"""Concrete isolated-process adapter for the prospective complete study.

Reuses the captured bounded Docker/framed-broker lifecycle. There is no host
Python/model callback returning predictions. Future native authority must admit
the selected image/stack, physical quotas, outer process ownership and provider
state before constructing this runner. This file supplies no native grant.
"""
from pathlib import Path
import secrets
from regional_custody import need, read, write, encoded, parsed, pin, _capture_closed, ClosedStage
from regional_sources import load_group, TRANSPORT
from regional_runtime import validate_mounted
import copy


class NoModelEngine:
    kind = 'disabled_no_model'
    def cancel(self):
        return None


class NoModelBroker:
    def __init__(self, context, phase, frame_bytes):
        self.context_id, self.phase = context, phase
        self.limits = {'frame_bytes': frame_bytes}
        self.engine = NoModelEngine()
        self.attempted = False
    def handle(self, request):
        self.attempted = True
        raise ValueError('Model tool unavailable in F/reference stages')
    def cancel(self):
        return None
    def receipt(self):
        return {'context_id': self.context_id, 'phase': self.phase, 'calls': 0,
                'model_access': 'disabled', 'attempted_forbidden_request': self.attempted,
                'model_child_terminal': True, 'input_tokens_reserved': 0, 'output_tokens_reserved': 0,
                'input_tokens_reported': 0, 'output_tokens_reported': 0, 'traces': []}


def authenticate_tree(root, inventory, budget):
    need(type(inventory) is dict and bool(inventory), 'Complete captured ordinary tree inventory')
    root = Path(root)
    actual = []
    import os
    for folder, dirs, files in os.walk(root, followlinks=False):
        need(not any(Path(folder, d).is_symlink() for d in dirs), 'Unlinked tree')
        actual.extend(str(Path(folder, f).relative_to(root)) for f in files)
    need(len(actual) == len(inventory) and set(actual) == set(inventory), 'No missing/extra mounted files')
    for name, descriptor in inventory.items():
        read(root, name, descriptor, budget)
        need(Path(root, name).stat().st_mode & 0o222 == 0, 'Captured mount is sealed readonly')


class ClosedProcess:
    """One serialized trusted owner; every launch has fresh context and broker.

    The required authority object admits concrete outside facts. It cannot
    return predictions, fitted states or scalar scientific results. Tests must
    use the separate explicit engineering constructor; no callback bypass is
    exposed by the production method.
    """
    def __init__(self, transport_root, transport_pin, runtime_root, runtime_inventory,
                 capsules, *, budget, native_authority, model_spec, token_admission,
                 storage_admission, docker_binary):
        need(native_authority is not None, 'Native source route is not authorized by construction')
        runtime_inventory=copy.deepcopy(runtime_inventory)
        capsules=copy.deepcopy(capsules)
        model_spec=copy.deepcopy(model_spec)
        validate_mounted(runtime_inventory,transport_pin)
        need(Path(runtime_root).is_absolute() and
             Path(transport_root)==Path(runtime_root)/'host_transport',
             'Host transport must use the sealed admitted runtime projection')
        authenticate_tree(runtime_root,runtime_inventory,budget)
        self.modules = load_group(transport_root, transport_pin, budget, TRANSPORT)
        self.runtime_root, self.runtime_inventory = str(runtime_root), runtime_inventory
        self.capsules, self.budget = capsules, budget
        self.model_spec, self.token_admission = model_spec, token_admission
        self.storage_admission = storage_admission
        self.transport = self.modules['morse_docker'].DockerCommandTransport(docker_binary)
        self.native_authority = native_authority
        self._configuration_bytes=encoded({'runtime_root':self.runtime_root,
            'runtime_inventory':runtime_inventory,'capsules':capsules,'model_spec':model_spec})
        need(set(capsules) == {'F', 'I', 'reference'}, 'Three fixed captured source capsules')
        fixed = {'F':('frozen_program_entry.py', {'frozen_program_entry.py','program.py','TRAINING_RECIPE.json'}),
                 'I':('investigator_policy.py', {'investigator_policy.py','INSTRUCTIONS.json'}),
                 'reference':('reference_entry.py', {'reference_entry.py'})}
        authenticate_tree(runtime_root, runtime_inventory, budget)
        for role, capsule in capsules.items():
            need(set(capsule) == {'root', 'files', 'entrypoint'}, 'Closed capsule definition')
            authenticate_tree(capsule['root'], capsule['files'], budget)
            entry,names = fixed[role]
            need(capsule['entrypoint'] == entry and set(capsule['files']) == names
                 and capsule['files'][entry] == runtime_inventory[entry], 'Exact task-owned trusted adapter/policy source')
        # Must bind the actual selected transport, source manifests, image and
        # external enforcement observations. No bool/hash self-admits execution.
        native_authority.require_neural094_route(transport_pin, runtime_inventory, capsules)
        self.failed = False
        self.active = False

    def stage(self, spec, public_context, expected_files, *, role, input_inventory,
              fit_inventory, model_limits):
        need(not self.failed and not self.active and role in self.capsules, 'Sequential fresh stage ownership')
        need(encoded({'runtime_root':self.runtime_root,'runtime_inventory':self.runtime_inventory,
             'capsules':self.capsules,'model_spec':self.model_spec})==self._configuration_bytes,
             'Previously admitted configuration cannot change after source freeze')
        spec=copy.deepcopy(spec);public_context=copy.deepcopy(public_context)
        expected_files=copy.deepcopy(expected_files);input_inventory=copy.deepcopy(input_inventory)
        fit_inventory=copy.deepcopy(fit_inventory);model_limits=copy.deepcopy(model_limits)
        capsule = self.capsules[role]
        need(spec['runtime_root'] == self.runtime_root and spec['capsule_root'] == capsule['root'],
             'Only frozen runtime/capsule roots')
        need(spec['mode'] == ('case_adaptive' if role == 'I' else 'frozen_program'), 'Fixed mode semantics')
        need(public_context['context_id'] == spec['context_id'] and public_context['mode'] == spec['mode']
             and public_context['phase'] == spec['phase'] and public_context['entrypoint'] == capsule['entrypoint']
             and public_context['capsule_files'] == {n: p['sha256'] for n, p in capsule['files'].items()},
             'Actual worker source/context identity')
        phase = spec['phase']
        if role == 'reference':
            need(public_context['payload']['reference_kind'] in ('whole', 'regional'), 'Fixed trusted method route')
        if phase == 'train':
            need(fit_inventory is None and spec['query_root'] is spec['fit_root'] is None,
                 'Fit sees no query or prior fitted state')
            authenticate_tree(spec['train_root'], input_inventory, self.budget)
        else:
            need(not any(Path(spec['train_root']).iterdir()), 'No reopened training-label mount during query')
            authenticate_tree(spec['query_root'], input_inventory, self.budget)
            authenticate_tree(spec['fit_root'], fit_inventory, self.budget)
        need(not any(Path(spec['output_root']).iterdir()) and not any(Path(spec['workspace_root']).iterdir()),
             'Fresh output/workspace, no cross-bundle state')
        authenticate_tree(self.runtime_root, self.runtime_inventory, self.budget)
        authenticate_tree(capsule['root'], capsule['files'], self.budget)
        context_bytes=encoded(public_context)
        input_inventory_bytes=encoded(input_inventory)
        capsule_inventory_bytes=encoded(capsule['files'])
        context_pin=write(spec['context_root'], 'context.json', context_bytes, self.budget)
        self.native_authority.require_neural094_stage(spec, role, input_inventory, fit_inventory)
        lim=spec['limits']
        # Preventive logical transport reservations, including one bounded
        # overshoot read and all failure/cleanup commands. These are debits,
        # never reported as realized I/O or refunded on provider failure.
        command_reads=8*2*(lim['frame_bytes']+65536)
        self.budget.charge('read',command_reads+lim['stdout_bytes']+lim['stderr_bytes']+131072)
        self.budget.charge('write',command_reads+4*((lim['stderr_bytes']+2)//3))
        m = self.modules['morse_broker']
        if role == 'I':
            need(model_limits is not None, 'Prospectively allocated I stage model budget')
            calls=model_limits['max_calls']
            self.budget.charge('read',calls*(self.model_spec['response_max_bytes']+
                self.model_spec['stderr_max_bytes']+131072+2*lim['frame_bytes']))
            self.budget.charge('write',calls*(self.model_spec['request_max_bytes']+
                12*lim['frame_bytes']+8192))
            engine = m.HttpsJsonEngine(self.model_spec, token_admission=self.token_admission)
            broker = m.ModelBroker(engine, spec['context_id'], phase, model_limits, self.model_spec)
        else:
            need(model_limits is None, 'F and reference have no runtime model allocation')
            broker = NoModelBroker(spec['context_id'], phase, spec['limits']['frame_bytes'])
        self.active = True
        try:
            receipt = self.modules['morse_docker'].run_stage(
                spec, broker, transport=self.transport, storage_admission=self.storage_admission)
            # Preserve private transcript even on a failed worker. A production
            # run reserves this complete serialization/retention before launch.
            if role == 'I':
                receipt['private_transcript'] = broker.private_transcript()
            receipt['scientific_qualification'] = False
            need(read(spec['context_root'],'context.json',context_pin,self.budget)==context_bytes,
                 'Same captured prelaunch context after native producer closure')
            receipt.update(prelaunch_context=context_pin,
                prelaunch_input_inventory=pin(input_inventory_bytes),
                prelaunch_capsule_inventory=pin(capsule_inventory_bytes))
            write(spec['context_root'],'HOST_RESULT.json',encoded(receipt),self.budget)
            captured = _capture_closed(spec, receipt, spec['output_root'], expected_files, self.budget,
                context_bytes=context_bytes,input_inventory_bytes=input_inventory_bytes,
                capsule_inventory_bytes=capsule_inventory_bytes)
            # Inputs and sealed state must still be identical after producer
            # removal. Readonly mounts are not a substitute for this join.
            if phase == 'query':
                authenticate_tree(spec['fit_root'], fit_inventory, self.budget)
                authenticate_tree(spec['query_root'], input_inventory, self.budget)
            else:
                authenticate_tree(spec['train_root'], input_inventory, self.budget)
            return captured
        except BaseException:
            self.failed = True
            raise
        finally:
            self.active = False


def seal_fit(stage, destination, budget):
    need(type(stage) is ClosedStage and stage.phase == 'train', 'Actual closed train stage')
    manifest = parsed(stage.files['fit_manifest.json'])
    need(type(manifest) is dict and set(manifest) == {'context_id', 'files'}
         and manifest['context_id'] == stage.context and type(manifest['files']) is list,
         'Closed fitted inventory context')
    expected = {name: pin(raw) for name, raw in stage.files.items() if name != 'fit_manifest.json'}
    names = [row['path'] for row in manifest['files']]
    need(len(names) == len(set(names)) and set(names) == set(expected)
         and all({k: row[k] for k in ('bytes', 'sha256')} == expected[row['path']]
                 for row in manifest['files']), 'All exact fitted bytes after producer closure')
    need(not any(Path(destination).iterdir()), 'Fresh fit seal root')
    for name, raw in stage.files.items():
        Path(destination, name).parent.mkdir(parents=True, exist_ok=True)
        write(destination, name, raw, budget)
    return {name: pin(raw) for name, raw in stage.files.items()}


def new_context_id():
    """No anatomical labels, source aliases or session ordinal in candidate ID."""
    return 'candidate-' + secrets.token_hex(24)
