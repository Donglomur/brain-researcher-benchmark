"""Fixed prepared-pair launch, original H bootstrap, fair service and terminal.

This consumes the real earlier HostObserver. It does not replace its source or
native qualification producer, nor the later whole-campaign root observation.
"""
from .common import need,Store
from .development_preparation import PreparationHandle
from .development_handles import DevelopmentAttemptHandle,_ATTEMPT
from .development_pair_service import DevelopmentPairService
from .backend_capture import CanonicalPublisher
from .observer import HostObserver
from .precommit_records import CONDITIONS
from .native_launch_pipeline_v4 import launch_native_worker_v4
from .backend_h_bootstrap_v3 import prepare_actual_h_receiver_v3


def run_prepared_native_pair_v3(pair,host):
    need(type(pair)is PreparationHandle and pair.promotion is pair and
         pair.owner.parent.preparation is pair,'actual complete same-owner prepared pair')
    parent=pair.owner.parent
    if parent.first_raw is not None:raise parent.first_raw
    service=DevelopmentPairService(pair)
    try:
        need(type(host)is HostObserver and host.meter is pair.owner.host and
             type(host.outputs)is Store and host.outputs.meter is pair.owner.host and
             host.outputs.root==pair.outputs.root and
             host.mapping['source']==parent.clock['mapping_source'] and
             host.mapping['boot_id']==parent.identity['boot_id'],
             'actual earlier original H observer, Store, clock and custody')
        publisher=pair.host_publisher
        need(type(publisher)is CanonicalPublisher and publisher.owner is pair.owner and
             publisher.condition is None and not pair.launches,
             'same completed original pair publisher and no previous worker attempts')
        publisher.require_native_source_v3()
        # Both original attempted-arm identities exist before either launch.
        # A first-arm failure therefore cannot erase the other terminal slot.
        for condition in CONDITIONS:
            pair.launches[condition]=DevelopmentAttemptHandle(_ATTEMPT,pair,condition,host)
        for condition in CONDITIONS:
            attempt=pair.launches[condition]
            launch_native_worker_v4(attempt,publisher)
            prepare_actual_h_receiver_v3(attempt,publisher)
        service.run()
    except BaseException as error:
        service.entered=True
        service.retain(error,'run_prepared_native_pair_v3')
    # Existing fixed terminal continuation visits every retained original arm,
    # including failed launch/setup prefixes. It never promotes a failed pair.
    return service.finish()
