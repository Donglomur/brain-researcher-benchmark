"""Closed, currently unavailable native boundary for the Four backend.

No wire record, qualification Pin, user provider, or callback mints these live
capabilities. Production acquisition must be implemented by the actual H
launch owner and independently qualified native observers. This file performs
no process, socket, model, entropy or scientific operation, including at import.
"""
from .common import DependencyUnavailable, need

_NATIVE = object()


class HWorkerLaunchAdmission:
    __slots__ = ('owner', 'condition', 'ack', 'request', 'preparation', 'workspace',
                 'profile', 'native', 'consumed', 'backend_handle')

    def __init__(self, token, owner, condition, ack, request, preparation,
                 workspace, profile, native):
        need(token is _NATIVE, 'actual H launch capability, never decoded evidence')
        self.owner=owner; self.condition=condition; self.ack=ack
        self.request=request; self.preparation=preparation; self.workspace=workspace
        self.profile=profile; self.native=native; self.consumed=False
        self.backend_handle=None


class HBackendAdmission:
    __slots__ = ('worker_admission', 'backend_handle', 'ack', 'host_observation')

    def __init__(self, token, worker_admission, backend_handle, ack, host_observation):
        need(token is _NATIVE, 'independent actual H initialization admission')
        self.worker_admission=worker_admission; self.backend_handle=backend_handle
        self.ack=ack; self.host_observation=host_observation


def acquire_worker_launch_admission(owner, preparation_handle, development_attempt):
    # Deliberately do not inspect/deserialize supplied values or touch aliases.
    raise DependencyUnavailable('four_actual_H_worker_launch_admission',
        'actual preparation/launch owner and native H observation producer are not integrated')


class BackendNativeOwner:
    """Fixed methods, no injected implementations. All leaves are unavailable.

    Future spawn must store returned process/FDs in this original owner before
    any fallible observation. Every close slot must clear before ambiguous
    close; stream reads require pre-admission and confirmed nonblocking setup.
    All methods receive the original lifecycle handle, never a fresh budget.
    """
    __slots__ = ('admission', 'process', 'stdout', 'stderr', 'socket', 'group',
                 'raw_first', 'raw_secondaries', 'unknown_effects')

    def __init__(self, token):
        need(token is _NATIVE, 'fixed native owner creator')
        self.admission=None; self.process=None; self.stdout=None; self.stderr=None
        self.socket=None; self.group=None; self.raw_first=None
        self.raw_secondaries=[]; self.unknown_effects=[]

    def _missing(self, role):
        raise DependencyUnavailable(role, 'source-owned native producer and qualification unavailable')

    def assert_worker_admission(self, admission):
        self._missing('four_native_worker_admission_identity')

    def now_ns(self, handle): self._missing('four_original_worker_clock_observation')
    def spawn(self, handle): self._missing('four_owned_server_spawn')
    def process_observations(self, handle): self._missing('four_server_identity_group_observation')
    def initialization_evidence(self, handle): self._missing('four_bounded_source_initialization')
    def consume_host_admission(self, handle): self._missing('four_independent_H_backend_admission')
    def completion_evidence(self, handle, semantic_request): self._missing('four_fixed_bounded_HTTP_completion')
    def signal(self, handle, purpose): self._missing('four_once_owned_server_signal')
    def wait(self, handle): self._missing('four_bounded_original_server_wait')
    def streams(self, handle): self._missing('four_owned_nonblocking_stream_closure')
    def socket_closure(self, handle): self._missing('four_anchored_socket_closure')
    def subtree(self, handle): self._missing('four_complete_server_subtree_observation')


class InitializationEvidence:
    __slots__ = ('selection', 'artifacts', 'executable', 'environment', 'socket', 'peer', 'health', 'slots')
    def __init__(self, token, selection, artifacts, executable, environment, socket, peer, health, slots):
        need(token is _NATIVE, 'actual fixed initialization observer product')
        self.selection=selection; self.artifacts=artifacts; self.executable=executable; self.environment=environment
        self.socket=socket; self.peer=peer; self.health=health; self.slots=slots


class CompletionEvidence:
    __slots__ = ('wire_request', 'raw_response', 'parsed_response')
    def __init__(self, token, wire_request, raw_response, parsed_response):
        need(token is _NATIVE, 'actual fixed HTTP observer product')
        self.wire_request=wire_request; self.raw_response=raw_response
        self.parsed_response=parsed_response
