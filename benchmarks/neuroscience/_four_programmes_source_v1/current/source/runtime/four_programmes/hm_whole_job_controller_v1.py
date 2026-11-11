"""Actual original C/H custody for the distinct whole-job HM profile.

The qualified outer C launcher supplies inherited descriptors and the original
bootstrap Share. This module constructs and retains the real endpoint; it does
not invent native channel or environment qualification.
"""
import os
from .common import need, encode
from .resources import Share
from .source_session import SourceSession
from .channel import RootChannel, HostEndpoint
from .observer import HostObserver, RunningProcess
from .identity import process_identity
from .hm_whole_job_profile_v1 import HMWholeJobPlanV1, HMWholeJobReservationOwnerV1, PROGRAMME
from .hm_issuer_transport_v1 import HMChannelConstructionV1, _CUSTODY

_TOKEN = object()
_LIVE = {}


class HMWholeControllerCustodyV1:
    def __init__(self, token, *, plan, meter, endpoint, session=None, reservations=None):
        need(token is _TOKEN and type(plan) is HMWholeJobPlanV1 and type(meter) is Share,
             'source-created original whole-job controller custody')
        self.plan = plan;self.meter = meter;self.is_endpoint = endpoint
        self.session = session;self.reservations = reservations
        self.channel = None;self.construction = None;self.raw_first = None;self.secondaries = []
        self.close_entered = False;self.close_complete = False
        self.controller_identity = None;self.host_identity = None
        self.controller_process = None;self.observer = None
        self.pid = os.getpid();self._binding_raw = None
        self.publications = [];self.dispatches = [];self.final_request = None
        _LIVE[id(self)] = self

    @property
    def endpoint(self):
        need(self.is_endpoint, 'actual H endpoint role')
        return self.channel

    def retain(self, error, site):
        if self.raw_first is None:self.raw_first = error
        elif error is not self.raw_first:self.secondaries.append((error, site))

    def require_original(self):
        c = self.construction
        need(_LIVE.get(id(self)) is self and type(c) is HMChannelConstructionV1 and
             c.owner is self and c.channel is self.channel and c.endpoint is self.is_endpoint and
             c.complete and type(self.channel) is (HostEndpoint if self.is_endpoint else RootChannel) and
             self.channel.meter is self.meter and encode(self.channel.binding) == self._binding_raw and
             not self.close_entered and os.getpid() == self.pid,
             'same exact constructed original channel, process, immutable source binding and meter')
        self.plan.require_original()
        if self.is_endpoint:
            need(type(self.reservations) is HMWholeJobReservationOwnerV1 and
                 self.reservations.controller_custody is self and
                 self.reservations.controller_endpoint is c.channel and
                 self.meter is self.reservations.host_share,
                 'same original H reservation and actual retained controller endpoint')
        else:
            need(type(self.session) is SourceSession and not self.session.closed and
                 self.session._hm_whole_controller_custody_v1 is self,
                 'same original admitted C source session and custody')
        if self.raw_first is not None:raise self.raw_first
        return self

    def close_once(self, primary=None):
        if primary is not None:self.retain(primary, 'caller_primary')
        c = self.construction
        need(_LIVE.get(id(self)) is self and type(c) is HMChannelConstructionV1 and c.owner is self,
             'retained original constructor before any close')
        if self.channel is not c.channel:
            self.retain(RuntimeError('original whole-job channel object replaced'), 'custody_loss')
        # This real constructor retains each independently selected FD and
        # rechecks it before a once-only close. A foreign replacement is never
        # adopted. Both normal and partial initialization use the same owner.
        return c.close_failed_once(primary=self.raw_first)


def _initialize(owner, read_fd, write_fd, binding, selected_qualification):
    channel = object.__new__(HostEndpoint if owner.is_endpoint else RootChannel)
    owner.channel = channel;owner._binding_raw = encode(binding)
    construction = HMChannelConstructionV1(_CUSTODY, owner, channel, endpoint=owner.is_endpoint)
    construction.initialize_once(read_fd, write_fd, binding=binding,
                                 selected_qualification=selected_qualification)
    return owner.require_original()


def open_original_hm_whole_controller_endpoint_v1(*, reservations, observer, controller_process,
        read_fd, write_fd, binding, selected_qualification, host_identity):
    need(type(reservations) is HMWholeJobReservationOwnerV1 and type(observer) is HostObserver and
         type(controller_process) is RunningProcess and controller_process.owner is observer,
         'original H resource owner and actual source-created observed C process')
    reservations.require_original()
    need(getattr(reservations, 'controller_custody', None) is None and
         observer.meter is reservations.host_share and
         observer.active.get(controller_process.spec['nonce']) is controller_process,
         'one original C channel under the original H observer/share')
    owner = HMWholeControllerCustodyV1(_TOKEN, plan=reservations.plan,
        meter=reservations.host_share, endpoint=True, reservations=reservations)
    reservations.controller_custody = owner;reservations.controller_endpoint = None
    owner.observer = observer;owner.controller_process = controller_process
    try:
        need(controller_process.spec['mode'] == 'coordinator' and
             controller_process.spec['campaign'] == reservations.plan.body['campaign_id'] and
             controller_process.identity is not None and controller_process.child is not None and
             controller_process.primary is None and not controller_process.finish_attempted,
             'actual live original C launch, not a process identity dictionary')
        controller = controller_process.identity
        actual = process_identity(controller_process.child.pid,
            launch_nonce=controller_process.spec['nonce'], source=controller_process.spec['source'],
            parent_launch=controller_process.spec['parent_launch'],
            mapping=observer.mapping, meter=owner.meter)
        need(actual == controller, 'same actual observed C process boot/PID/start/source')
        actual_host = process_identity(os.getpid(), launch_nonce=host_identity['launch_nonce'],
            source=reservations.plan.body['observer_source'], parent_launch=host_identity['parent_launch'],
            mapping=observer.mapping, meter=owner.meter)
        need(actual_host == host_identity and actual_host != actual,
             'actual separate original H process under selected observer source')
        owner.controller_identity = actual;owner.host_identity = actual_host
        need(binding['campaign'] == reservations.plan.body['campaign_id'] and
             binding['source'] == reservations.plan.body['observer_source'] and
             binding['launch'] == controller['parent_launch'],
             'exact selected H source/campaign and original C launch binding')
        # Register the exact provisional channel before constructor effects.
        channel = object.__new__(HostEndpoint);owner.channel = channel
        reservations.controller_endpoint = channel;owner._binding_raw = encode(binding)
        construction = HMChannelConstructionV1(_CUSTODY, owner, channel, endpoint=True)
        construction.initialize_once(read_fd, write_fd, binding=binding,
                                     selected_qualification=selected_qualification)
        return owner.require_original()
    except BaseException as error:
        owner.retain(error, 'H_controller_channel_factory')
        if owner.construction is not None:
            try:owner.close_once(primary=owner.raw_first)
            except BaseException as later:owner.retain(later, 'H_controller_channel_factory_cleanup')
        raise owner.raw_first


def open_original_hm_whole_controller_channel_v1(*, session, plan, bootstrap_share,
        read_fd, write_fd, binding, selected_qualification, controller_identity, mapping):
    need(type(session) is SourceSession and session.programme == PROGRAMME and not session.closed and
         type(plan) is HMWholeJobPlanV1 and type(bootstrap_share) is Share and
         session.store.meter is bootstrap_share,
         'actual captured C source session and its original bootstrap share')
    need(getattr(session, '_hm_whole_controller_custody_v1', None) is None,
         'one original C whole-job channel including failures')
    owner = HMWholeControllerCustodyV1(_TOKEN, plan=plan, meter=bootstrap_share,
                                      endpoint=False, session=session)
    session._hm_whole_controller_custody_v1 = owner
    try:
        plan.require_original()
        need(bootstrap_share.row in plan.resource_plan['adapter_reservations'],
             'earlier selected original C transport share, no new standalone allowance')
        actual = process_identity(os.getpid(), launch_nonce=controller_identity['launch_nonce'],
            source=controller_identity['source'], parent_launch=controller_identity['parent_launch'],
            mapping=mapping, meter=bootstrap_share)
        need(actual == controller_identity and binding['campaign'] == plan.body['campaign_id'] and
             binding['source'] == plan.body['observer_source'] and
             binding['launch'] == actual['parent_launch'],
             'actual current C identity and exact original H source/launch')
        owner.controller_identity = actual
        return _initialize(owner, read_fd, write_fd, binding, selected_qualification)
    except BaseException as error:
        owner.retain(error, 'C_controller_channel_factory')
        if owner.construction is not None:
            try:owner.close_once(primary=owner.raw_first)
            except BaseException as later:owner.retain(later, 'C_controller_channel_factory_cleanup')
        raise owner.raw_first


def require_original_controller_v1(reservations):
    need(type(reservations) is HMWholeJobReservationOwnerV1,
         'actual original whole-job reservation owner')
    owner = getattr(reservations, 'controller_custody', None)
    need(type(owner) is HMWholeControllerCustodyV1 and owner.is_endpoint and
         owner.reservations is reservations, 'actual source-created original C/H endpoint custody')
    return owner.require_original()
