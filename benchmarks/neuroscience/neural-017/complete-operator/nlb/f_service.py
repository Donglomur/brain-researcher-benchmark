"""Trusted source-owned reference gateway for both frozen and investigating actors."""
import base64
from .contracts import need, closed, canonical, digest, descriptor, integer, Store, Custody, Budget, diagnostic
from .programme import allowed_references, bank_id
from .reference_service import PREFIX, FRAME_CAP, PREDICTION_CAP


def reference_bank(campaign, context, condition, gid, budget):
    """Bind all allowed handles to actual same-condition S06 producers.

    These are source/receipt admissions, not newly supplied results or cached
    predictions. Every requested inference still invokes the real expert.
    """
    need(condition == gid.split('/')[0] and context['binding']['programme'] == campaign.identity and
         context['binding']['condition'] == condition and context['binding']['group'] == gid and
         context['binding']['code_view'] == gid.split('/')[1][-1], 'same programme/group/condition/code view')
    expected = allowed_references(condition)
    need(tuple(context['references']) == expected, 'complete condition-specific expert bank')
    need({'S05', 'S06'} <= set(campaign.evidence.done) and
         {'E07', 'E09', 'E10'} <= set(campaign.evidence.evidence), 'original qualified expert stages precede either actor')
    states = {name: state for name, state in context['states'].items() if state.get('reference') is not None}
    need(len(states) == len(expected) and {v['reference'] for v in states.values()} == set(expected),
         'one exact qualified handle per allowed reference')
    reader = Store(campaign.store.root, budget, Custody('reference_bank:' + gid))
    campaign.custody.resources.append(reader.custody)
    entries = {}
    for name, state in states.items():
        rid = state['reference']
        producer = bank_id(condition, rid)
        need(producer in campaign.originals and producer in campaign.executor.selected, 'actual original bank producer')
        original = campaign.originals[producer]
        need(original.job == producer and original.custody.complete and original.custody.first_error is None and
             original.reaped and original.absence is True and original.exit_code == 0 and
             all(original.stream_eof.values()) and original.costs['cpu_seconds'] is not None,
             'completed original expert and known construction cost')
        need({'process', 'worker_result', 'worker_terminal'} <= set(original.persistence) and original.costs.get('worker_io') is not None, 'durable original expert receipts and known worker accounting')
        result = reader.json(original.persistence['worker_result'], 8 * 2**20)
        selected = campaign.executor.selected[producer]
        need(selected['stage'] == 'S06' and selected['role'] == 'reference_predict', 'exact original bank stage and role')
        need(result['job'] == producer and result['source'] == selected['source'] and
             result['bindings']['programme'] == campaign.identity and result['bindings']['job'] == producer and
             result['bindings']['role'] == 'reference_predict' and result['bindings']['source'] == selected['source'] and
             result['bindings']['inputs'] == selected['input_manifests'], 'source-owned original reference result')
        from .contracts import parse
        request = parse(original.request['stdin'])['payload']
        body = request['body']
        need(request['job'] == producer and request['source'] == selected['source'] and
             request['expected_root_source'] == campaign.source and request['stage'] == 'S06' and request['role'] == 'reference_predict' and
             body['reference'] == rid and body['query'] == context['query'] and
             body['support'] == context['support'] and body['config'] == state['config'],
             'same original source/configuration/query/support')
        prefix = original.persistence['worker_result']['path'].rsplit('/', 1)[0]
        pair = {key: {**result['products'][product], 'path': prefix + '/' + result['products'][product]['path']}
                for key, product in (('metadata', 'state_metadata'), ('arrays', 'state_arrays'))}
        need(state['source'] == pair, 'exact actual adapted state, no stale caller-supplied cache')
        for pin in pair.values():
            descriptor(pin)
            need(any(a.pin == pin and a.producer == producer and a.stage == 'S06' and
                     a.condition == condition and a.group is None and a.role == 'source_state'
                     for a in campaign.artifacts.values()), 'same-condition public bank state lineage')
        entries[rid] = {'handle': name, 'source': selected['source'], 'state': pair,
                        'config': state['config'], 'query': context['query'], 'support': context['support'],
                        'public_metadata': state['public_metadata'],
                        'original_process': original.persistence['process'],
                        'original_worker_result': original.persistence['worker_result']}
    bank = {'schema': 'NLB017_actual_reference_bank_binding_v1', 'programme': campaign.identity,
            'condition': condition, 'references': list(expected), 'entries': entries}
    # Handle names are an API convenience, not a scientific difference across arms.
    identity = {**bank, 'entries': {rid: {k: v for k, v in row.items() if k != 'handle'} for rid, row in entries.items()}}
    return bank, digest(canonical(identity))


def reference_body(campaign, context, condition, gid, reference, handle, case_index, budget):
    bank, identity = reference_bank(campaign, context, condition, gid, budget)
    need(reference in bank['entries'] and bank['entries'][reference]['handle'] == handle, 'selected exact reference handle')
    if case_index is not None:
        integer(case_index, 0, 573)
    row = bank['entries'][reference]
    body = {'tool': 'reference_predict', 'state': row['state'], 'config': row['config'],
            'query': row['query'], 'case_index': case_index, 'support': row['support']}
    return body, bank, identity


def reference_slot(campaign, job, bank, reference):
    slot = campaign.executor.selected[job]
    need('tool_variants' in slot and 'reference_predict' in slot['tool_variants'], 'fresh selected original reference slot')
    variant = slot['tool_variants']['reference_predict']
    need(variant['source'] == bank['entries'][reference]['source'], 'actual tool uses the exact qualified bank source')
    return variant


class FrozenReferenceService:
    """One original frozen program, live reference calls, no model exchanges."""
    def __init__(self, campaign, context, condition, gid, job, captured_source, slots, io_reserve):
        self.campaign = campaign
        self.context = context
        self.condition = condition
        self.gid = gid
        self.job = job
        self.source = captured_source
        self.budget = campaign.group_budget(gid)
        need(gid.split('/')[1] in ('F-A', 'F-B') and job == gid + '/programme', 'original F actor')
        need(type(slots) is list and slots and len(slots) == len(set(slots)) and
             slots == [gid + '/reference-service-%06d' % i for i in range(1, len(slots) + 1)],
             'complete original finite service slot sequence')
        closed(io_reserve, Budget.IO_KEYS)
        for value in io_reserve.values(): integer(value, 1)
        self.io_reserve = dict(io_reserve)
        self.slots = list(slots)
        self.serial = 0
        self.events = []
        self.custody = Custody("frozen_reference_service:" + job)
        self.attempt_custodies = []
        self.active_slot = None
        bank, self.bank = reference_bank(campaign, context, condition, gid, self.budget)
        peer_gid = gid.replace('/F-', '/I-')
        peer = campaign.selection['participant_groups'][peer_gid]['preparation_context']
        peer = campaign.resolve({key: peer[key] for key in ('binding', 'references', 'states', 'query', 'support')}, 'S07', condition, gid)
        _, peer_bank = reference_bank(campaign, peer, condition, peer_gid, self.budget)
        need(peer_bank == self.bank, 'paired F/I original qualified bank and public metadata are identical')
        self.binding = digest(canonical({'programme': campaign.identity, 'root_source': campaign.source,
            'group': gid, 'condition': condition, 'code_view': gid.split('/')[1][-1], 'job': job,
            'captured_source': captured_source, 'bank': self.bank,
            'original_deadline': self.budget.deadline, 'slots': slots, 'io_reserve': self.io_reserve}))
        self.public = {'schema': 'NLB017_frozen_reference_service_v1', 'binding': self.binding,
                       'bank': self.bank, 'references': bank['references'],
                       'metadata': {rid: row['public_metadata'] for rid, row in bank['entries'].items()},
                       'max_calls': len(slots)}
        self.resource_pairs()

    def resource_pairs(self):
        parent = self.campaign.executor.selected[self.job]['sandbox']
        need(parent['runtime_profile'] == 'participant_' + self.gid.split('/')[1][-1], 'F physical source profile')
        for name in self.slots:
            need(name in self.campaign.executor.selected, 'every F service slot precommitted')
            slot = self.campaign.executor.selected[name]
            closed(slot, {'stage', 'role', 'parent_group', 'process_limit', 'tool_variants'})
            need(slot['stage'] == 'S07' and slot['role'] == 'participant_tool' and slot['parent_group'] == self.gid,
                 'same original F cumulative service pool')
            closed(slot['tool_variants'], {'reference_predict'})
            variant = slot['tool_variants']['reference_predict']
            for key in Budget.IO_KEYS:
                need(variant['worker_io_limits'][key] + variant['completion_io_limits'][key] <= self.io_reserve[key], 'explicit residual IO covers each reference worker and its original closure')
            child = variant['sandbox']
            need(child['runtime_profile'] == 'reference_tool' and child['cgroup_parent'] == parent['cgroup_parent'] and
                 child['cgroup_name'] != parent['cgroup_name'], 'distinct qualified tool containment')
            need(child['memory_bytes'] + parent['memory_bytes'] <= 16 * 2**30 and
                 child['pids'] + parent['pids'] <= 64 and
                 child['cpu_quota_us'] / child['cpu_period_us'] + parent['cpu_quota_us'] / parent['cpu_period_us'] <= 4 and
                 child['scratch_bytes'] + parent['scratch_bytes'] <= 2 * 2**30,
                 'combined live frozen-program/reference resources stay inside original arm ceilings')
            need(child['scratch_root'] != parent['scratch_root'], 'separate bounded actor and expert scratch')

    def admit_parent_io(self, selected):
        for key in Budget.IO_KEYS:
            need(selected['worker_io_limits'][key] + self.io_reserve[key] <= self.budget.available(key),
                 'held F worker allocation leaves selected reference IO reserve')

    def admit_service_io(self, job):
        selected = self.campaign.executor.selected[job]['tool_variants']['reference_predict']
        for key in Budget.IO_KEYS:
            need(selected['worker_io_limits'][key] + selected['completion_io_limits'][key] <= self.budget.available(key),
                 'actual nested reference residual IO, no release or reuse of live F counters')

    def exchange(self, raw):
        owner = Custody('frozen_reference_exchange')
        self.attempt_custodies.append(owner)
        self.custody.resources.append(owner)
        try:
            return self._exchange_owned(raw, owner)
        except BaseException as original:
            owner.fail(original, 'reference_exchange')
            try:self.events.append({'classification':'service_failed','original_cause':diagnostic(owner.first_error),'custody':owner.snapshot()})
            except BaseException as secondary:owner.fail(secondary,'service_failure_publication')
            self.custody.fail(None,'reference_exchange',owner)
            raise
        finally:
            self.active_slot = None

    def _exchange_owned(self, raw, owner):
        self.budget.admit()
        need(len(raw) <= FRAME_CAP, 'bounded original service request')
        from .contracts import parse
        request = parse(raw)
        closed(request, {'schema', 'binding', 'bank', 'serial', 'reference', 'case_index'})
        need(request['schema'] == 'NLB017_frozen_reference_request_v1' and
             request['binding'] == self.binding and request['bank'] == self.bank and
             request['serial'] == self.serial + 1 and self.serial < len(self.slots),
             'same original F service, ordered single-use request')
        reference = request['reference']
        bank, identity = reference_bank(self.campaign, self.context, self.condition, self.gid, self.budget)
        need(identity == self.bank and reference in bank['entries'], 'unchanged complete original bank')
        body, _, identity = reference_body(self.campaign, self.context, self.condition, self.gid, reference,
            bank['entries'][reference]['handle'], request['case_index'], self.budget)
        job = self.slots[self.serial]
        reference_slot(self.campaign, job, bank, reference)
        self.serial += 1  # consumed before dispatch; an original failure is not retried
        self.admit_service_io(job)
        self.active_slot = job
        try:
            original, result = self.campaign.native(job, 'S07', 'participant_tool', body,
                {'prediction': {'name': 'tool/' + job, 'role': 'prediction'}}, condition=self.condition, gid=self.gid)
        except BaseException as exc:
            owner.fail(exc, 'reference_dispatch')
            try:
                prior = self.campaign.executor.attempt_custodies.get(job)
                if type(prior) is Custody:owner.fail(None,'original_dispatch',prior)
            except BaseException as secondary:owner.fail(secondary,'original_dispatch_projection')
            raise
        finally:
            self.active_slot = None
        event = {'request': request, 'request_sha256': digest(raw), 'bank': identity, 'job': job,
                 'original_process': original.persistence.get('process'), 'known_original': original.public(),
                 'worker_result': None if result is None else result['original_worker_result']}
        self.events.append(event)
        receipt = {'job': job, 'bank': identity, 'original_process': event['original_process'],
                   'original_worker_result': event['worker_result'], 'reference': reference,
                   'case_index': request['case_index'], 'original_deadline': self.budget.deadline}
        header = {'schema': 'NLB017_frozen_reference_response_v1', 'request_sha256': digest(raw),
                  'binding': self.binding, 'serial': self.serial, 'receipt': receipt,
                  'status': 'tool_failed', 'prediction': None}
        if result is None:
            return [canonical(header)]
        reader = Store(self.campaign.store.root, self.budget, Custody('reference_service_result:' + job))
        owner.resources.append(reader.custody)
        prediction = result['products']['prediction']
        raw_prediction = reader.read(prediction, PREDICTION_CAP)
        header.update(status='complete', prediction={k: prediction[k] for k in ('bytes', 'sha256')})
        frames = [canonical(header)]
        for index, start in enumerate(range(0, len(raw_prediction), 64 * 2**10)):
            frames.append(canonical({'schema': 'NLB017_reference_prediction_chunk_v1', 'serial': self.serial,
                'sequence': index, 'data': base64.b64encode(raw_prediction[start:start + 64 * 2**10]).decode('ascii')}))
        frames.append(canonical({'schema': 'NLB017_reference_prediction_end_v1', 'serial': self.serial,
            'bytes': len(raw_prediction), 'sha256': digest(raw_prediction), 'chunks': len(frames) - 1}))
        need(all(len(frame) <= FRAME_CAP for frame in frames), 'finite binary transport, bounded metadata observations')
        event['actual_prediction'] = prediction
        event['response_bytes'] = sum(map(len, frames))
        event['response_sha256'] = digest(b''.join(frames))
        return frames

    def finish(self):
        # Custody publication remains available after an original deadline or stop.
        # Dispatch guards are enforced by exchange and the native process owner.
        return {'schema': 'NLB017_original_frozen_reference_service_closure_v1', 'job': self.job,
                'binding': self.binding, 'bank': self.bank, 'consumed_slots': self.serial,
                'events': self.events, 'custody': self.custody.snapshot(), 'original_deadline': self.budget.deadline, 'original_io_reserve': self.io_reserve,
                'no_continuing_authoring_model': True, 'budget': self.budget.snapshot()}
