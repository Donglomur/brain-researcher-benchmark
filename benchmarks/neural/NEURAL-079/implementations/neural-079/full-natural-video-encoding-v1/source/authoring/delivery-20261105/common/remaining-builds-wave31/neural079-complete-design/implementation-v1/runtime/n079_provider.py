"""Disabled-until-admitted concrete provider transport, distinct from model science."""
import http.client
import ssl
from urllib.parse import urlsplit
from ach_resource_common import collect_errors
from ach_resource_credential import read_authorization_pipe
from investigator_wire import build_request, parse_response
from n079_common import require, fields, integer, checked_pin, identity, error_record, pin
from n079_plan import policies, bundles


class ProviderProxy:
    def __init__(self, context, selected, endpoints):
        context.require_effect('provider_http', 'provider-proxy')
        fields(selected, ('schema', 'allocation_pin', 'source_pin', 'deployment_evidence', 'spend_evidence',
                          'policy_records', 'per_call_cost_nano_units', 'endpoint_name', 'advertised_models'))
        require(selected['schema'] == 'n079_actual_provider_deployment_v1' and
                selected['allocation_pin'] == context.effect_admission['allocation_pin'] and
                selected['source_pin'] == context.source_pin, 'actual source/complete allocation/provider deployment join')
        for key in ('deployment_evidence', 'spend_evidence'):
            checked_pin(selected[key])
        integer(selected['per_call_cost_nano_units'], 1)
        require(type(selected['policy_records']) is dict and set(selected['policy_records']) == {p['id'] for p in policies()},
                'all12 global provider policies')
        self.context, self.selected, self.endpoints = context, selected, endpoints
        self.policies = {p['id']: p for p in policies()}; self.bundles = {b['id']: b for b in bundles()}
        self.sealed = None; self.exposed = set(); self.credential = None; self.calls = []; self.closed = False
        from n079_budget import allocation
        allocated = allocation(context.allocation)['rows']
        for policy_id, item in selected['policy_records'].items():
            limits = item['limits']
            for work, row in allocated.items():
                belongs = work == 'policy/' + policy_id or any(
                    b['policy_id'] == policy_id and (work == 'training/' + b['id'] or work == 'report/' + b['id'] or
                    work.startswith('query/' + b['id'] + '/')) for b in self.bundles.values())
                if belongs:
                    calls = row['provider_calls']
                    require(row['provider_input_tokens'] >= calls * limits['max_input_tokens'] and
                            row['provider_output_tokens'] >= calls * limits['max_output_tokens'] and
                            row['spend_nano_units'] >= calls * selected['per_call_cost_nano_units'],
                            'actual complete local call allocation covers every token/spend ceiling')
        for seed in range(3):
            records = [selected['policy_records'][p['id']] for p in self.policies.values() if p['seed'] == seed]
            require(all(r['policy'] == records[0]['policy'] and r['limits'] == records[0]['limits'] for r in records),
                    'same provider/model/transport capacities across matched F/I and tool arms')
        # Admission precedes opaque credential access and every HTTP effect.
        self.admission = context.authority.exchange('provider_deployment_and_spend', selected)
        for policy_id, item in selected['policy_records'].items():
            fields(item, ('policy', 'limits', 'tools_pin', 'policy_source_pin'))
            checked_pin(item['tools_pin']); checked_pin(item['policy_source_pin'])
            endpoint = urlsplit(item['policy']['endpoint'])
            require(endpoint.scheme == 'https' and endpoint.hostname and endpoint.port in (None, 443) and
                    not endpoint.username and not endpoint.password and not endpoint.fragment, 'one fixed TLS endpoint')

    def bind_credential(self, inherited_fd):
        require(self.admission is not None and self.credential is None and not self.closed, 'one admitted opaque credential binding')
        self.context.tick()
        self.credential = read_authorization_pipe(inherited_fd, self.context.clock.origin, self.context.clock.scientific)

    def seal_policies(self, records):
        require(self.sealed is None and type(records) is dict and set(records) == set(self.policies), 'all12 immutable global source policies before data')
        for key, value in records.items():
            fields(value, ('policy_source_pin', 'program_pin'))
            require(value['policy_source_pin'] == self.selected['policy_records'][key]['policy_source_pin'], 'exact declared fixed policy source')
            checked_pin(value['program_pin'])
        self.context.authority.exchange('all_policy_sources_sealed', records)
        self.sealed = {k: dict(v) for k, v in records.items()}

    def numeric_exposure(self, bundle_id, view_pin, observed_stage_evidence):
        require(self.sealed is not None and bundle_id in self.bundles, 'global policies sealed before first numeric exposure')
        checked_pin(view_pin); checked_pin(observed_stage_evidence)
        self.context.authority.exchange('actual_numeric_view_exposure',
            {'bundle': bundle_id, 'view_pin': view_pin, 'observed_stage': observed_stage_evidence})
        self.exposed.add(self.bundles[bundle_id]['policy_id'])

    def _policy_for_work(self, work_id):
        kind, _, tail = work_id.partition('/')
        if kind == 'policy':
            require(self.sealed is None and tail in self.policies, 'source generation only before all-policy seal')
            return tail
        require(kind in ('training', 'query', 'report') and self.sealed is not None, 'named post-exposure provider phase')
        bundle = tail.rsplit('/', 1)[0] if kind == 'query' else tail
        require(bundle in self.bundles, 'exact active all-person bundle')
        policy = self.bundles[bundle]['policy_id']
        require(self.policies[policy]['mode'] == 'I', 'F provider prohibited after numerical exposure, including reports')
        require(policy in self.exposed, 'independently observed training view before I analysis')
        if kind == 'query':
            require(int(tail.rsplit('/', 1)[1]) in self.bundles[bundle]['query_ids'], 'current held query identity')
        return policy

    def call(self, work_id, messages, tools, current_context_evidence, image_sources=None):
        require(not self.closed and self.credential is not None, 'provider hard-refused until credential binding')
        policy_id = self._policy_for_work(work_id); record = self.selected['policy_records'][policy_id]
        checked_pin(current_context_evidence)
        require(identity(tools, self.context.encoding_limits) == record['tools_pin'], 'fixed source-owned tool set')
        self.context.authority.exchange('provider_current_public_context',
            {'work_id': work_id, 'policy': policy_id, 'context_evidence': current_context_evidence})
        request = build_request(record['policy'], messages, tools, record['limits'], image_sources=image_sources)
        limits = record['limits']; cost = self.selected['per_call_cost_nano_units']
        self.context.ledger.charge(work_id, {'provider_calls': 1, 'provider_input_tokens': limits['max_input_tokens'],
            'provider_output_tokens': limits['max_output_tokens'], 'spend_nano_units': cost}, 'whole per-call token/spend reservation')
        endpoint = urlsplit(request['endpoint']); attempt = self.endpoints.begin(self.selected['endpoint_name'])
        connection = None; response = None; first = None; parts = []; status = None; result = None
        observed = {'policy_id': policy_id, 'work_id': work_id, 'request_pin': request['request_pin'],
                    'reserved_input_tokens': limits['max_input_tokens'], 'reserved_output_tokens': limits['max_output_tokens'],
                    'reserved_spend_nano_units': cost, 'response_prefix': None, 'actual_usage': None,
                    'actual_spend': 'unknown_without_independent_billing_evidence', 'failure': None}
        self.calls.append(observed)
        try:
            connection = http.client.HTTPSConnection(endpoint.hostname, 443,
                timeout=(self.context.clock.scientific - self.context.tick()) / 1e9, context=ssl.create_default_context())
            connection.request('POST', endpoint.path + ('?' + endpoint.query if endpoint.query else ''), body=request['body'],
                               headers={'Authorization': self.credential, 'Content-Type': 'application/json'})
            # This is an application body submission count, not socket-return,
            # TLS wire bytes, unique network totals or remote model resources.
            self.endpoints.charge(attempt, 'write_bytes', len(request['body']))
            response = connection.getresponse(); status = response.status
            require(status == 200, 'complete provider response required; no automatic retry')
            length = response.getheader('Content-Length')
            require(length is None or length.isdecimal() and int(length) <= limits['max_response_bytes'], 'bounded response length')
            total = 0
            while True:
                self.context.tick(); raw = response.read(min(65536, limits['max_response_bytes'] + 1 - total))
                if not raw:
                    break
                parts.append(raw); total += len(raw)
                self.endpoints.charge(attempt, 'read_bytes', len(raw))
                require(total <= limits['max_response_bytes'], 'complete bounded provider body')
            raw = b''.join(parts)
            import base64
            observed['response_prefix_base64'] = base64.b64encode(raw).decode('ascii')
            result = parse_response(raw, request)
            observed['actual_usage'] = result['usage']; observed['response_pin'] = pin(raw)
            self.context.tick()
        except BaseException as error:
            first = error
        observed['http_status'] = status
        if observed['response_prefix'] is None:
            import base64
            observed['response_prefix_base64'] = base64.b64encode(b''.join(parts)).decode('ascii')
        first = collect_errors(([('HTTP response close', response.close)] if response is not None else []) +
                               ([('HTTPS connection close', connection.close)] if connection is not None else []), first)
        first = collect_errors([('original provider return cutoff', self.context.tick)], first)
        observed['failure'] = None if first is None else error_record(first)
        first = collect_errors([('provider complete/failed-prefix journal',
                                 lambda: self.context.journal.append('provider_exchange', observed, 'closeout'))], first)
        first = collect_errors([('provider endpoint disposition',
                                 lambda: self.endpoints.end(attempt, failed=first is not None))], first)
        if first is not None:
            first.n079_prefix = observed; raise first
        return result

    def close(self):
        self.closed = True; self.credential = None
