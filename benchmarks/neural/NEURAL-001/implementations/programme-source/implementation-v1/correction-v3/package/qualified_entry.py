"""Concrete source composition for a future independently qualified environment.

Nothing selects or creates such an environment in the default CLI. The binding
object supplies custody/measurement/credentials and protected stores, not candidate
predictions, reference fits or scores. Those operations use this captured source.
"""
from types import SimpleNamespace
import time
from .protocol import canonical,pin_bytes,require
from .runtime import Qualification,StudyRuntime
from .instructions import INSTRUCTIONS


def run_full(*, qualification, source_pin, binding):
    require(type(qualification)is Qualification,'exact reviewed qualification gate type')
    require(binding.clock is time.monotonic,'selected clock must be actual host time.monotonic, matching caller observer')
    admission=binding.independent_admission
    q=qualification.validate(admission,source_pin=source_pin)
    config=binding.configuration()
    require(type(config)is dict and set(config)=={'resource_profile','storage','host','container','provider',
            'documents','source_tools','replicate','instructions_pin','clock_domain'},'complete exact environment configuration')
    require(pin_bytes(canonical(config))==q.get('environment_binding_pin'),
            'independently qualified exact provider/container/storage/exposure binding')
    require(config['clock_domain']=='host_time_monotonic','explicit qualified observer clock domain')
    require(config['instructions_pin']==pin_bytes(canonical(INSTRUCTIONS)),'exact fixed instructions')
    require(set(config['source_tools'])=={'candidate_reference_tool.py','reference_engine.py','reference_bundle_codec.py'},
            'complete exact frozen reference tool source set')

    def guard():
        require(admission.guard(qualification.receipt_pin,source_pin,q['original_origin'],q['original_deadline']) is True,
                'live independent original-clock/source/custody authority refused')

    def driver_factory(admitted,selected_source,subjects):
        guard()
        from .store_loader import load_stores
        from .host import QualifiedHost
        from .driver import ExecutionDriver
        packet_module,artifact_module=load_stores(guard)
        storage=config['storage']
        records=binding.input_records()
        budget=packet_module.IOBudget(**storage['packet_logical_limits'])
        packets=packet_module.PacketStore(storage['packet_root'],records,budget)
        artifact=artifact_module.ArtifactStore(storage['artifact_root'],
            role_caps=storage['role_caps'],metadata_cap=storage['metadata_cap'],
            expanded_cap=storage['expanded_cap'],meter=binding.artifact_meter,
            qualify=binding.artifact_qualifier,max_audit_events=storage['max_audit_events'])
        serializers=SimpleNamespace(budget=budget,serialize_training=packet_module.serialize_training,
                                    serialize_query=packet_module.serialize_query)
        host=QualifiedHost(guard=guard,root=storage['execution_root'],artifacts=artifact,
            serializers=serializers,monitor_factory=binding.monitor_factory,journal=binding.journal,
            custody=binding.custody,container_selection=config['container'],profile=config['host'],
            docs=config['documents'],source_tools=config['source_tools'],
            credential_capability=binding.credential_capability,
            protected_target_loader=binding.protected_target_loader,
            protected_group_loader=binding.protected_group_loader,replicate=config['replicate'],clock=binding.clock)
        # The complete admitted roster and pinned store metadata must agree;
        # no reduced fixture path or caller-supplied predictions are accepted.
        for s in subjects:
            row=records[s.canonical_id]
            require(row['subject']==s.support() and tuple(row['training']['run_ids'])==s.run_ids
                and tuple(row['training']['epoch_ids'])==s.epoch_ids
                and tuple(row['training']['epoch_runs'])==s.epoch_runs
                and tuple(row['training']['epoch_lengths'])==s.epoch_lengths,
                'exact full source/store/roster support join')
        kinds={s.canonical_id:tuple(records[s.canonical_id]['training']['channel_kinds']) for s in subjects}
        return ExecutionDriver(host=host,packet_store=packets,subjects=subjects,
            provider_selection=config['provider'],instructions=INSTRUCTIONS,
            method_reviewer=binding.method_reviewer,reference_progress=binding.reference_progress,
            channel_kinds_by_person=kinds)

    runtime=StudyRuntime(qualification=qualification,source_pin=source_pin,
        independent_admission=admission,manifest_factory=binding.manifest,
        driver_factory=driver_factory,profile=config['resource_profile'],clock=binding.clock,
        sink=binding.sink)
    return runtime.run()
