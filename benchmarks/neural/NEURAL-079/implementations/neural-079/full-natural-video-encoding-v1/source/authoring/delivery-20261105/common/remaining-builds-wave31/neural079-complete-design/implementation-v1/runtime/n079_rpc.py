"""Named authenticated service transport. No dynamically supplied scientific callbacks."""
import os
import socket
import stat
from ach_resource_common import peer_identity, collect_errors
from ach_resource_admission import verify_peer
from ach_resource_endpoints import send_frame, receive_frame
from n079_common import require, fields, identity, error_record


class ServiceClient:
    def __init__(self, context, role, selected, endpoints):
        fields(selected, ('socket', 'peer', 'source_pin', 'endpoint', 'operations'))
        require(selected['peer'] == context.admission['selection']['peers'][role] and
                selected['source_pin'] == context.source_pin, 'same admitted actual service role/source')
        self.context, self.role, self.selected, self.endpoints = context, role, selected, endpoints
        self.sequence = 0; self.exchanges = []

    def request(self, operation, payload, phase='scientific'):
        require(operation in self.selected['operations'], 'closed source-selected service operation')
        self.context.tick(phase); self.sequence += 1
        request = {'schema': 'n079_service_request_v1', 'sequence': self.sequence, 'operation': operation,
                   'source_pin': self.context.source_pin, 'payload': payload, 'phase': phase}
        exchange = {'request': request, 'reply': None, 'status': 'attempted'}; self.exchanges.append(exchange)
        attempt = self.endpoints.begin(self.selected['endpoint']); connection = None; first = None; result = None
        try:
            connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            connection.settimeout((getattr(self.context.clock, phase) - self.context.tick(phase)) / 1e9)
            connection.connect(self.selected['socket'])
            verify_peer(peer_identity(connection), self.selected['peer'], self.context.profile, self.context.clock, phase)
            send_frame(connection, request, self.context.profile, self.endpoints, attempt, self.context.clock, phase)
            reply, reply_raw = receive_frame(connection, self.context.profile, self.endpoints, attempt, self.context.clock, phase)
            exchange['reply'] = reply
            import base64
            exchange['raw_reply_base64'] = base64.b64encode(reply_raw).decode('ascii')
            fields(reply, ('schema', 'request_pin', 'source_pin', 'status', 'payload'))
            require(reply['schema'] == 'n079_service_response_v1' and reply['source_pin'] == self.context.source_pin and
                    reply['request_pin'] == identity(request, self.context.encoding_limits), 'exact authenticated service return')
            require(reply['status'] == 'complete', 'actual service refused/failed; retained reply prefix')
            self.context.tick(phase); result = reply['payload']; exchange['status'] = 'complete'
        except BaseException as error:
            first = error; exchange['status'] = 'failed_or_unknown'
        first = collect_errors([] if connection is None else [('service socket close', connection.close)], first)
        exchange['failure'] = None if first is None else error_record(first)
        first = collect_errors([('complete service exchange retention', lambda: self.context.journal.append('service_exchange', exchange, 'closeout'))], first)
        first = collect_errors([('service endpoint disposition', lambda: self.endpoints.end(attempt, failed=first is not None))], first)
        if first is not None:
            first.n079_prefix = exchange; raise first
        return result


class SupervisorClient(ServiceClient):
    def run(self, request):
        return self.request('run', request)

    def promote(self, context_id, name, material_name):
        return self.request('promote', {'context': context_id, 'name': name, 'material_name': material_name})


class ProviderClient(ServiceClient):
    def call(self, work_id, messages, tools, current_context_evidence, image_sources=None):
        return self.request('call', {'work_id': work_id, 'messages': messages, 'tools': tools,
            'current_context_evidence': current_context_evidence, 'image_sources': image_sources})

    def seal_policies(self, records):
        return self.request('seal_policies', records)

    def numeric_exposure(self, bundle_id, view_pin, observed_stage_evidence):
        return self.request('numeric_exposure', {'bundle_id': bundle_id, 'view_pin': view_pin,
                                               'observed_stage_evidence': observed_stage_evidence})


def dispatch(role, service, operation, payload, actual_peer):
    # Actual classes are checked; no operator-provided callable can return a
    # scientific success in place of the selected producer/math path.
    if role == 'supervisor':
        from n079_jobs import JobSupervisor
        require(type(service) is JobSupervisor, 'actual concrete process supervisor')
        if operation == 'run':
            return service.run(payload)
        if operation == 'promote':
            fields(payload, ('context', 'name', 'material_name'))
            return service.promote(payload['context'], payload['name'], payload['material_name'])
        if operation == 'register_report_material':
            fields(payload, ('bundle_id', 'object', 'material_name', 'relative_path'))
            return service.register_report_material(**payload)
        if operation == 'register_public_materials':
            fields(payload, ('catalog', 'export_evidence'))
            return service.register_public_materials(**payload)
        if operation == 'material_record':
            fields(payload, ('material_name',))
            return service.material_record(payload['material_name'])
    elif role == 'provider':
        from n079_provider import ProviderProxy
        require(type(service) is ProviderProxy, 'actual concrete provider proxy')
        if operation == 'call':
            return service.call(**payload)
        if operation == 'seal_policies':
            service.seal_policies(payload); return {'sealed': sorted(service.sealed)}
        if operation == 'numeric_exposure':
            service.numeric_exposure(**payload); return {'exposure_policies': sorted(service.exposed)}
    elif role == 'observer':
        from n079_observer import ObserverService
        require(type(service) is ObserverService, 'actual concrete observer')
        return service.handle(operation, payload, actual_peer)
    elif role == 'issuer':
        from n079_issuer import IssuerService
        require(type(service) is IssuerService, 'actual concrete protected issuer')
        return service.handle(operation, payload, actual_peer)
    elif role == 'grader':
        from n079_grading import ProtectedGrader
        require(type(service) is ProtectedGrader and operation == 'grade', 'actual independently authored protected grade path')
        return service.grade(payload)
    raise ValueError('unselected source-owned service operation')


def serve(context, role, service, selected, endpoints):
    fields(selected, ('socket', 'peers', 'endpoint', 'operations', 'maximum_requests'))
    require(type(selected['maximum_requests']) is int and selected['maximum_requests'] > 0, 'selected bounded service work')
    listener = None; owned_identity = None; first = None; accepted = 0; history = []
    ready_fd = getattr(context, 'ready_fd', None); context.ready_fd = None
    sequences = {}
    try:
        context.tick(); listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(selected['socket'])
        st = os.lstat(selected['socket']); owned_identity = (st.st_dev, st.st_ino)
        require(stat.S_ISSOCK(st.st_mode), 'actual owned Unix socket before chmod')
        os.chmod(selected['socket'], 0o600); listener.listen(1)
        if ready_fd is not None:
            fd, ready_fd = ready_fd, None; ready_error = None
            try:
                require(os.write(fd, b'R') == 1, 'actual bound service readiness')
            except BaseException as error:
                ready_error = error; raise
            finally:
                from n079_common import close_all
                close_all([('service readiness pipe close', lambda: os.close(fd))], ready_error)
        while True:
            context.tick('closeout')
            listener.settimeout((context.clock.closeout - context.tick('closeout')) / 1e9)
            connection, _ = listener.accept(); accepted += 1
            one = None; record = {'sequence': accepted, 'request': None, 'reply': None, 'failure': None}
            history.append(record); attempt = None
            stop = False
            try:
                attempt = endpoints.begin(selected['endpoint'])
                require(accepted <= selected['maximum_requests'], 'complete declared service request ceiling')
                actual = peer_identity(connection)
                peers = [p for p in selected['peers'] if all(actual[k] == p[k] for k in ('pid', 'uid', 'gid'))]
                require(len(peers) == 1, 'one independently selected live caller')
                verify_peer(actual, peers[0], context.profile, context.clock, 'closeout')
                connection.settimeout((context.clock.closeout - context.tick('closeout')) / 1e9)
                request, request_raw = receive_frame(connection, context.profile, endpoints, attempt, context.clock, 'closeout')
                record['request'] = request
                import base64
                record['raw_request_base64'] = base64.b64encode(request_raw).decode('ascii')
                sequence_key = (actual['pid'], request.get('schema'))
                require(type(request.get('sequence')) is int and request['sequence'] == sequences.get(sequence_key, 0) + 1,
                        'source-owned once-only caller/protocol sequence')
                sequences[sequence_key] = request['sequence']
                if request.get('schema') == 'n079_additive_charge_v1':
                    require(role == 'observer' and 'reserve' in selected['operations'], 'only actual budget owner')
                    reply = service.budget.handle(request, actual)
                    record['reply'] = reply
                    context.journal.append('additive_reservation_before_publication', record, request['phase'])
                    send_frame(connection, reply, context.profile, endpoints, attempt, context.clock, request['phase'])
                    operation = 'reserve'
                elif request.get('schema') == 'n079_issuer_request_v1':
                    require(role == 'issuer' and 'admit' in selected['operations'], 'only actual custody issuer')
                    fields(request, ('schema', 'sequence', 'kind', 'source_pin', 'payload'))
                    require(request['source_pin'] == context.source_pin, 'same issuer request source closure')
                    evidence = service.handle(request['kind'], request['payload'], actual)
                    reply = {'schema': 'n079_issuer_response_v1', 'request_pin': identity(request, context.encoding_limits),
                             'issuer_source_pin': context.source_pin, 'decision': 'admit', 'evidence': evidence}
                    record['reply'] = reply
                    context.journal.append('issuer_return_before_publication', record)
                    send_frame(connection, reply, context.profile, endpoints, attempt, context.clock, 'scientific')
                    operation = 'admit'
                else:
                    operation = None
                if operation is not None:
                    # Raw protocols above remain source-owned, fully framed and
                    # authenticated; cleanup is shared with generic services.
                    pass
                else:
                    reply, stop = generic_request(context, role, service, selected, request, actual)
                    record['reply'] = reply
                    context.journal.append('service_return_before_publication', record, request['phase'])
                    send_frame(connection, reply, context.profile, endpoints, attempt, context.clock, request['phase'])
            except BaseException as error:
                one = error; record['failure'] = error_record(error)
            one = collect_errors([('accepted service connection close', connection.close)], one)
            if attempt is not None:
                one = collect_errors([('service endpoint closure', lambda: endpoints.end(attempt, failed=one is not None))], one)
            if one is not None:
                one.n079_prefix = record; raise one
            if stop:
                break
        return {'requests': accepted, 'history': history}
    except BaseException as error:
        first = error; error.n079_prefix = {'accepted_requests': accepted, 'history': history}; raise
    finally:
        def unlink_owned():
            if owned_identity is None:
                return
            current = os.lstat(selected['socket'])
            require((current.st_dev, current.st_ino) == owned_identity and stat.S_ISSOCK(current.st_mode), 'never unlink a replaced socket')
            os.unlink(selected['socket'])
        operations = ([] if listener is None else [('service listener close', listener.close)]) + [('owned socket unlink', unlink_owned)]
        if ready_fd is not None:
            operations.append(('unpublished service readiness pipe', lambda: os.close(ready_fd)))
        from n079_common import close_all
        close_all(operations, first)


def generic_request(context, role, service, selected, request, actual):
                fields(request, ('schema', 'sequence', 'operation', 'source_pin', 'payload', 'phase'))
                require(request['schema'] == 'n079_service_request_v1' and request['source_pin'] == context.source_pin and
                        request['operation'] in selected['operations'], 'same complete source and named operation')
                context.tick(request['phase'])
                if request['operation'] == 'finish':
                    expected = context.admission['selection']['peers']['finalizer']
                    require(all(actual[k] == expected[k] for k in ('pid', 'uid', 'gid')), 'only finalizer closes a service')
                    stop = True; payload = {'source_pin': context.source_pin}
                else:
                    stop = False
                    payload = dispatch(role, service, request['operation'], request['payload'], actual)
                reply = {'schema': 'n079_service_response_v1', 'request_pin': identity(request, context.encoding_limits),
                         'source_pin': context.source_pin, 'status': 'complete', 'payload': payload}
                return reply, stop
