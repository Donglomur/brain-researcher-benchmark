"""Complete target-last producer programme; no scoring or target read here.

Every fit/query uses the concrete ClosedProcess implementation. Source-selected
candidate policies are loaded only in isolated workers. There is no prediction
provider callback or supplied scalar-score route.
"""
from pathlib import Path
import copy
import math
from regional_custody import need, encoded, parsed, pin, write, WholeFit, whole_fit_from_closed
from regional_native import ClosedProcess, seal_fit, new_context_id
from regional_preparation import Cohort, stage_packet
from regional_scope import bundles, geometry, capacity
from regional_policy import validate, authoring_receipt

REF = '4b361baf14ae689344e389b4bb45fb822c0283a401d6271fefc56115efc2a28d'
REFERENCES = ('training_prior','selected_context','matched_context_logistic','matched_joint_logistic')


def prediction_rows(raw, tokens):
    """Complete target-free probability admission; retain submitted order data."""
    values = parsed(raw)
    need(type(values) is list and len(values) == len(tokens), 'Complete prediction extent')
    by_token = {}
    for row in values:
        need(type(row) is dict and set(row) == {'token','probabilities'}
             and type(row['token']) is str and row['token'] not in by_token, 'Unique exact prediction row')
        p = row['probabilities']
        need(type(p) is list and len(p) == 3 and all(type(v) in (int,float) and math.isfinite(v)
             and 0 <= v <= 1 for v in p), 'Three finite nonboolean probabilities')
        need(abs(sum(p)-1)<=1e-8, 'Exact inherited syntax probability-sum tolerance')
        by_token[row['token']] = p
    need(set(by_token) == set(tokens) and len(set(tokens)) == len(tokens), 'Every exact original query token')
    # Normalization belongs to each numerical scorer, where original and
    # independent binary64 boundary/sign discrepancies must remain visible.
    return [by_token[t] for t in tokens]


def reference_rows(raw, tokens):
    rows = parsed(raw)
    need(type(rows) is list and len(rows) == 4, 'All four original reference views')
    result = {}
    for row in rows:
        need(type(row) is dict and set(row) == {'reference','rows'}
             and row['reference'] in REFERENCES and row['reference'] not in result, 'Exact reference identity')
        result[row['reference']] = prediction_rows(encoded(row['rows']), tokens)
    return result


_BATCH_KEY = object()


class ClosedBatch:
    __slots__ = ('scope','cohort','bank','root','sources','closure','_key')
    def __init__(self, key, scope, cohort, bank, root, sources, closure):
        need(key is _BATCH_KEY, 'Only complete source-owned producer programme creates batch')
        self.scope, self.cohort, self.bank, self.root = scope, cohort, bank, root
        self.sources, self.closure, self._key = sources, closure, key


class Programme:
    def __init__(self, cohort, policy, authoring, runner, root, selected, *, budget, subset, modules, np):
        need(type(cohort) is Cohort and type(runner) is ClosedProcess, 'Concrete admitted cohort and isolated runner')
        policy=copy.deepcopy(policy);authoring=copy.deepcopy(authoring);selected=copy.deepcopy(selected)
        self.cohort, self.scope, self.runner, self.budget = cohort, cohort.scope, runner, budget
        self.policy = validate(policy, self.scope)
        need(set(authoring) == {'F','I'}, 'Both complete authoring logs')
        self.authoring = {mode: authoring_receipt(authoring[mode], policy[mode+'_authoring'],
            policy['source'][mode], policy['model_spec'],policy['authoring_resources'][mode]) for mode in ('F','I')}
        need(all(policy['source'][mode] == pin(encoded(runner.capsules[mode]['files'])) for mode in ('F','I')),
             'Complete captured capsule inventory binds global authoring source')
        runner.native_authority.require_neural094_authoring(authoring, policy)
        need(pin(encoded(runner.model_spec)) == policy['model_spec'], 'Same trusted fixed model configuration')
        self.selected, self.subset, self.modules, self.np = selected, subset, modules, np
        self.root = Path(root)
        need(self.root.is_dir() and not any(self.root.iterdir()), 'Fresh complete programme root')
        self.bank, self.whole, self.receipts, self.input_identity = {}, {}, [], {}
        self.allocations = {row['key']: row for row in policy['I_contexts']}
        need(set(selected) == {'native_template','stage_limits','model_limits','payload_limits',
                              'numerical_sources','capacity','source_manifest'}, 'Explicit complete programme selection')
        need(set(selected['stage_limits']) == {'train','query','reference_train','reference_query'}, 'Every native phase operand')
        cohort.admit_all_manifests()
        derived_capacity=capacity(self.scope,iter(cohort.extent_rows()),selected['capacity']['phase_limits'])
        need(derived_capacity==selected['capacity'], 'Exact full S/job/byte preallocation from admitted metadata')
        for phase in ('train','query'):
            native=selected['stage_limits'][phase]; declared=policy['condition_resources']['F'][phase]
            need(native['cpu_seconds']==declared['cpu_seconds']
                 and native['wall_seconds']+native['cleanup_seconds']==declared['wall_seconds']
                 and native['memory_bytes']==declared['memory_bytes']
                 and native['workspace_bytes']+native['output_bytes']+native['tmp_bytes']==declared['storage_bytes'],
                 'Declared paired ceilings equal the concrete native operands')
        for phase,label in (('train','fit'),('query','query'),('reference_train','reference_fit'),('reference_query','reference_query')):
            native=selected['stage_limits'][phase];reserved=selected['capacity']['phase_limits'][label]
            need(native['cpu_seconds']==reserved['cpu_seconds']
                 and native['wall_seconds']+native['cleanup_seconds']==reserved['wall_seconds']
                 and native['memory_bytes']==reserved['memory_bytes']
                 and native['workspace_bytes']+native['output_bytes']+native['tmp_bytes']==reserved['storage_bytes']
                 and native['file_bytes']==reserved['model_bytes']==reserved['prediction_bytes'],
                 'Full graph resource reservations join actual per-stage native ceilings')
        instruction = parsed(__import__('regional_custody').read(runner.capsules['I']['root'],'INSTRUCTIONS.json',
            runner.capsules['I']['files']['INSTRUCTIONS.json'],budget))
        need(type(instruction['max_actions']) is int and all(instruction['max_actions']<=
             policy['condition_resources']['I'][phase]['tool_calls'] for phase in ('train','query')),
             'Externally observable isolated action count fits each declared tool allowance')
        runner.native_authority.require_neural094_complete_capacity(selected['capacity'], self.scope.lineage, policy)
        # The whole source/method/support and aggregate allocations are frozen
        # before any candidate input directory is created.
        self.freeze = copy.deepcopy({'policy': self.policy, 'scope': self.scope.lineage, 'selected': selected})
        self._freeze_bytes=encoded(self.freeze)
        self._freeze_pin=write(self.root, 'FREEZE.json', self._freeze_bytes, budget)

    def _directory(self, name):
        root = self.root/name
        root.mkdir(mode=0o700)
        return root

    def _stage(self, logical, mode, phase, prepared, *, fitted=None, whole=None):
        from regional_custody import read
        need(encoded({'policy':self.policy,'scope':self.scope.lineage,'selected':self.selected})==self._freeze_bytes
             and read(self.root,'FREEZE.json',self._freeze_pin,self.budget)==self._freeze_bytes,
             'Exact whole-study freeze still binds every stage')
        role = 'reference' if mode == 'reference' else mode
        limit_key = ('reference_' if role == 'reference' else '')+phase
        limits = self.selected['stage_limits'][limit_key]
        identity = 'reference-'+logical['reference_kind']+'-'+new_context_id() if role == 'reference' else new_context_id()
        parent = self._directory(identity+'-'+phase)
        paths = {name: parent/name for name in ('input','output','work','context','empty')}
        for path in paths.values():
            path.mkdir(mode=0o755)
        inputs = stage_packet(prepared, paths['input'], self.budget)
        input_key=(logical['key'],phase)
        if input_key in self.input_identity:
            need(inputs == self.input_identity[input_key], 'Byte-identical F/I/reference observable input for same condition')
        else:
            self.input_identity[input_key]=dict(inputs)
        payload = dict(self.selected['payload_limits'], packet=pin(prepared['manifest_bytes']))
        if role == 'reference':
            payload.update(reference_kind=logical['reference_kind'], reference_sha256=REF,
                           numerical_sources=self.selected['numerical_sources'],
                           selection_private=prepared['selection_private'])
            if phase=='train' and logical['reference_kind']=='whole':
                payload['reference_fit_request']={'phase_name':'reference_fit','kind':'reference_fit',
                    'session_token':prepared['manifest']['session_token'],
                    'payload':{'fitval_manifest':pin(prepared['manifest_bytes'])}}
            if whole is not None:
                need(type(whole) is WholeFit and phase == 'train', 'Source-owned sealed whole reuse only')
                (paths['input']/'whole_fit').mkdir(mode=0o755)
                transfers = {}
                for name in ('model_bytes','commitment_bytes','fit_manifest_bytes','fit_request_bytes','closed_producer_bytes'):
                    body = getattr(whole,name)
                    descriptor = write(paths['input']/'whole_fit', name, body, self.budget)
                    transfers[name] = descriptor
                    inputs['whole_fit/'+name] = descriptor
                payload['whole_fit_transfer'] = transfers
        else:
            payload['program_sha256'] = self.runner.capsules['F']['files']['program.py']['sha256']
        fit_root, fit_inventory = (None,None) if fitted is None else fitted
        if role == 'reference' and phase == 'query':
            payload['commitment'] = fit_inventory['MODEL_COMMIT.json']
        spec = {**copy.deepcopy(self.selected['native_template']), 'context_id': identity,
                'mode': 'case_adaptive' if mode == 'I' else 'frozen_program', 'phase': phase,
                'name': 'morse-'+new_context_id().removeprefix('candidate-'),
                'runtime_root': self.runner.runtime_root, 'capsule_root': self.runner.capsules[role]['root'],
                'train_root': str(paths['input'] if phase == 'train' else paths['empty']),
                'query_root': str(paths['input']) if phase == 'query' else None,
                'fit_root': str(fit_root) if phase == 'query' else None,
                'context_root': str(paths['context']), 'output_root': str(paths['output']),
                'workspace_root': str(paths['work']), 'limits': limits}
        # Physical storage profiles must be obtained for THESE exact roots by
        # the independently selected trusted mechanism before any launch.
        spec['storage_profile'] = self.runner.storage_admission.prepare_neural094_storage(
            str(paths['output']), str(paths['work']), limits['output_bytes'], limits['workspace_bytes'])
        capsule = self.runner.capsules[role]
        public = {'context_id': identity, 'mode': spec['mode'], 'phase': phase,
                  'entrypoint': capsule['entrypoint'], 'capsule_files': {n:p['sha256'] for n,p in capsule['files'].items()},
                  'payload': payload}
        output = {'fit_manifest.json': limits['file_bytes'], 'model.bin': limits['file_bytes']} if phase == 'train' else {'predictions.json': limits['file_bytes']}
        if role == 'reference':
            output['fit_report.json' if phase == 'train' else 'inference_report.json'] = limits['file_bytes']
        elif mode == 'F' and phase == 'query':
            output['legacy_predictions.json'] = limits['file_bytes']
        allocation = None
        if mode == 'I':
            allocation = dict(self.selected['model_limits'], **self.allocations[logical['key']][phase])
        stage = self.runner.stage(spec, public, output, role=role, input_inventory=inputs,
                                  fit_inventory=fit_inventory, model_limits=allocation)
        observed=parsed(stage.receipt_bytes)
        usage=observed['broker']
        charged={'max_calls':usage['calls'],'input_tokens':usage['input_tokens_reserved'],
                 'output_tokens':usage['output_tokens_reserved']}
        self.receipts.append({'logical': logical['key'], 'role': role, 'phase': phase,
            'native': pin(stage.receipt_bytes),'model_reserved':charged,
            'model_unused_capacity':None if allocation is None else {k:allocation[k]-charged[k]
                                      for k in ('max_calls','input_tokens','output_tokens')},
            'model_actual_reported':{k:usage.get(k) for k in ('input_tokens_reported','output_tokens_reported')},
            'actual_wall_seconds_including_cleanup':observed.get('observed_wall_seconds_including_cleanup'),
            'actual_aggregate_cpu_seconds':None,'actual_peak_memory_bytes':None,
            'actual_peak_storage_bytes':None,'native_resource_limits':limits})
        write(parent, 'HOST_CLOSED.json', stage.receipt_bytes, self.budget)
        if phase == 'train':
            destination = self._directory(identity+'-sealed')
            destination.chmod(0o755)
            inventory = seal_fit(stage, destination, self.budget)
            if role == 'reference':
                commit = {'schema':'neural094_trusted_reference_model_commit_v1',
                          'reference_sha256':REF,'session_token':prepared['manifest']['session_token'],
                          'artifact':{'path':'model.bin',**pin(stage.files['model.bin'])},
                          'all_four_states_committed_before_query':True,'fit_process_closed':True,
                          'sealed_readonly':True,'artifact_sha256_verified_by_loader':True}
                inventory['MODEL_COMMIT.json'] = write(destination,'MODEL_COMMIT.json',encoded(commit),self.budget)
            return stage, (destination,inventory)
        tokens = prepared['manifest']['case_tokens']
        raw = stage.files['predictions.json']
        admitted = (reference_rows if role == 'reference' else prediction_rows)(raw,tokens)
        for matrix in (admitted.values() if role == 'reference' else [admitted]):
            self.modules['metric_core'].probabilities(self.np.asarray(matrix,dtype=self.np.float64),self.np)
        key = mode+':'+logical['key']
        need(key not in self.bank, 'No repeated/replaced completed condition')
        self.bank[key] = {'path':str((parent/'PREDICTIONS.json').relative_to(self.root)),
                          **write(parent,'PREDICTIONS.json',raw,self.budget),
                          'closed':pin(stage.receipt_bytes),'tokens':list(tokens)}
        return stage

    def _candidate_pair(self, group, mode):
        trained = []
        for b in group:
            prepared = self.cohort.prepare(b,'fitval',subset=self.subset,modules=self.modules,np=self.np)
            trained.append(self._stage(b,mode,'train',prepared)[1])
        # Both source-defined arm states are closed and sealed before either
        # receives any query packet. Each query remains a fresh context.
        for b, fitted in zip(group, trained, strict=True):
            prepared = self.cohort.prepare(b,'query',subset=self.subset,modules=self.modules,np=self.np)
            self._stage(b,mode,'query',prepared,fitted=fitted)

    def run(self):
        for ordinal in range(1,40):
            b = {'key':f'w-{ordinal:02d}-joint','kind':'whole','ordinal':ordinal,'side':'joint',
                 'pair':None,'seed':None,'reference_kind':'whole'}
            fit = self.cohort.prepare(b,'fitval',subset=self.subset,modules=self.modules,np=self.np)
            stage, sealed = self._stage(b,'reference','train',fit)
            request = encoded({'phase_name':'reference_fit','kind':'reference_fit',
                               'session_token':fit['manifest']['session_token'],
                               'payload':{'fitval_manifest':pin(fit['manifest_bytes'])}})
            self.whole[ordinal] = whole_fit_from_closed(stage,fit['manifest_bytes'],request)
            query = self.cohort.prepare(b,'query',subset=self.subset,modules=self.modules,np=self.np)
            self._stage(b,'reference','query',query,fitted=sealed)
        iterator = iter(bundles(self.scope))
        for left in iterator:
            right = next(iterator)
            need(left['ordinal'] == right['ordinal'] and left['kind'] == right['kind']
                 and left['pair'] == right['pair'] and left['seed'] == right['seed'], 'Exact source-owned paired order')
            group = [left,right]
            for mode in ('F','I'):
                self._candidate_pair(group,mode)
            if left['kind'] == 'regional':
                trained = []
                for b in group:
                    b = dict(b,reference_kind='regional')
                    fit = self.cohort.prepare(b,'fitval',subset=self.subset,modules=self.modules,np=self.np)
                    trained.append((b,self._stage(b,'reference','train',fit,whole=self.whole[b['ordinal']])[1]))
                for b,sealed in trained:
                    query = self.cohort.prepare(b,'query',subset=self.subset,modules=self.modules,np=self.np)
                    self._stage(b,'reference','query',query,fitted=sealed)
        g = geometry(self.scope)
        need(len(self.bank) == g['candidate_bundles_both_modes']+39+g['regional_reference_bundles'],
             'Every candidate/reference prediction captured before private grading')
        closure = {'schema':'neural094_complete_producer_closure_v1','geometry':g,
                   'prediction_artifacts':len(self.bank),'all_producers_closed':True,
                   'all_predictions_admitted':True,'query_target_reads':0,
                   'authoring':self.authoring,'source_freeze':pin(encoded(self.freeze)),
                   'native_qualification':False,'scientific_qualification':False}
        write(self.root,'COMPLETE_PRODUCERS.json',encoded({'closure':closure,'bank':self.bank,
              'receipts':self.receipts}),self.budget)
        return ClosedBatch(_BATCH_KEY,self.scope,self.cohort,self.bank,str(self.root),self.policy['source'],closure)
