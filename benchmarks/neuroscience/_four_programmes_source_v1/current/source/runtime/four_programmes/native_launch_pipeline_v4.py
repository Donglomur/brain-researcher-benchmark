"""Fixed full control-plan -> group -> channel -> start -> carrier -> spawn.

This source route does not manufacture the later worker import, Hello grant,
runtime renderer or backend admission. Those distinct consumers remain bound
to their actual original source producers and qualification prerequisites.
"""
from .common import need
from .early_resources import retain_source_failure

class NativeLaunchPipelineV4:
    def __init__(self,attempt,publisher):
        self.attempt=attempt;self.publisher=publisher;self.plan=None;self.kernel=None
        self.observation=None;self.channel=None;self.setup=None;self.start=None;self.carrier=None
        self.raw_first=None;self.secondaries=[];self.complete=False
    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        self.attempt.retain(error,'NativeLaunchPipelineV4.'+site)
        retain_source_failure(self.attempt.owner.parent,error,'NativeLaunchPipelineV4.'+site)

def launch_native_worker_v4(attempt,publisher):
    from .development_handles import DevelopmentAttemptHandle
    from .backend_capture import CanonicalPublisher
    from .native_control_plan_v4 import preflight_native_control_v4
    from .development_worker_io import DevelopmentWorkerKernel
    from .development_native_observations import DevelopmentNativeObservation
    from .backend_linux_channel import HNativeChannelOwner
    from .backend_bootstrap_carrier_v3 import HChannelSetupCaptureV4,HBootstrapCarrierOwnerV3
    from .backend_launch_start_v3 import HWorkerStartOwnerV3
    need(type(attempt)is DevelopmentAttemptHandle,'actual original H attempt')
    parent=attempt.owner.parent
    if parent.first_raw is not None:raise parent.first_raw
    try:
        attempt.require_live_original()
        need(type(publisher)is CanonicalPublisher and publisher.owner is attempt.owner and publisher.condition is None and
             attempt.native_launch_pipeline is None,'one actual original H launch caller and publisher')
        owner=NativeLaunchPipelineV4(attempt,publisher);attempt.native_launch_pipeline=owner
        owner.plan=preflight_native_control_v4(attempt)
        owner.channel=HNativeChannelOwner(attempt);owner.plan.reserve_channel(owner.channel)
        owner.kernel=DevelopmentWorkerKernel(attempt)
        owner.kernel.prepare_v1()
        owner.observation=DevelopmentNativeObservation(owner.kernel,publisher)
        owner.observation.capture_attempt_v1()
        owner.setup=HChannelSetupCaptureV4(owner.channel,publisher);owner.setup.capture_v4()
        owner.start=HWorkerStartOwnerV3(owner.kernel);owner.start.capture_before_carrier_v3()
        owner.carrier=HBootstrapCarrierOwnerV3(owner.kernel);owner.carrier.prepare_v3()
        owner.kernel.spawn_original_v3(owner.carrier)
        # spawn returns through its alias-cleanup finally. That cleanup may
        # retain a failure without replacing the original returned process.
        # No later local completion may hide that poisoned original custody.
        for retained in (parent.first_raw,attempt.raw_first,owner.kernel.raw_first,
                         owner.carrier.raw_first):
            if retained is not None:raise retained
        need(owner.carrier.close_entered and owner.carrier.closed,
             'actual parent exec aliases known closed before launch completion')
        owner.complete=True;return owner
    except BaseException as error:
        current=attempt.native_launch_pipeline
        if current is not None:current.retain(error,'launch')
        # The original pair terminal/scheduler owns group/child/stream cleanup;
        # all partially returned owners are registered on the same attempt.
        # Relinquish parent-only exec aliases independently here if acquired.
        carrier=attempt.bootstrap_carrier
        if carrier is not None:
            try:carrier.close_parent_exec_aliases_once()
            except BaseException as later:
                if current is not None:current.retain(later,'alias_cleanup')
        raise retain_source_failure(parent,error,'launch_native_worker_v4')
