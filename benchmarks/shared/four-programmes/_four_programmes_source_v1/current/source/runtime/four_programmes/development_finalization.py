"""Same-original-kernel stop, raw custody, receipt and typed output sequence."""
from .common import need
from .development_handles import DevelopmentAttemptHandle
from .development_worker_io import DevelopmentWorkerKernel
from .development_native_observations import DevelopmentNativeObservation
from .development_evidence import DevelopmentEvidenceCapture
from .backend_capture import CanonicalPublisher
from .development_host_terminal import DevelopmentHostTerminalCustody

class OriginalOutputFinalization:
    def __init__(self,attempt):
        need(type(attempt) is DevelopmentAttemptHandle,'actual original development attempt')
        attempt.require_live_original()
        need(attempt.output_finalization is None,'one finalization, including every failed prefix')
        self.attempt=attempt
        self.raw_first=attempt.raw_first if attempt.raw_first is not None else attempt.owner.parent.first_raw
        self.secondaries=[];self.entered=[];self.complete=False
        self.cleanup_dispositions={};self.publication_admitted=False
        attempt.output_finalization=self

    def retain(self,error,site):
        first=self.attempt.raw_first
        if first is None:first=self.attempt.owner.parent.first_raw
        if first is None:first=error
        if self.raw_first is None:self.raw_first=first
        if error is not self.raw_first:self.secondaries.append(error)
        try:self.attempt.retain(error,'original_output_'+site)
        except BaseException as later:self.secondaries.append(later)

    def require_completed(self):
        """The original completed caller, without replaying reads or cleanup."""
        a=self.attempt;producer=a.native_observations;evidence=a.evidence_capture
        need(a.output_finalization is self and self.complete and self.raw_first is None and
             a.raw_first is None and a.owner.parent.first_raw is None,
             'same original successful finalization; later failures cannot be hidden')
        need(type(a.host_terminal_custody) is DevelopmentHostTerminalCustody and
             a.host_terminal_custody.attempt is a and a.host_terminal_custody.require_completed() is a.host_terminal_custody,
             'actual original H receiver/native handles closed before final output authority')
        need(type(producer) is DevelopmentNativeObservation and producer.attempt is a and
             producer.kernel is a.worker_kernel and producer.kernel.native_observations is producer and
             producer.observation is a.process_observation and a.process_observation.success and
             producer.raw_first is None and producer.kernel.raw_first is None,
             'original process producer remains the actual completed object')
        need(type(evidence) is DevelopmentEvidenceCapture and evidence.attempt is a and
             evidence.raw_first is None and
             evidence.stream_manifest is a.complete_stream_capture and
             evidence.workspace_capture is a.descendant_workspace_closure and
             evidence.completion_cost is a.cost_observation and
             evidence.whole_arm_source is a.whole_arm_capture and
             evidence.workspace_source is a.arm.workspace,
             'same original stream/workspace/cost products used by the completed caller')
        return self

    def run_v2(self):
        need(not self.entered,'no repeated stop/read/close or publication after uncertainty')
        self.entered.append('cleanup_admission')
        a=self.attempt;k=a.worker_kernel;producer=a.native_observations
        # Acquired owners precede the optional later observation producer.
        # Failed preparation must still reach both independent release owners.
        if k is None:
            self.cleanup_dispositions['kernel']='not_acquired'
        else:
            self.entered.append('kernel_finish')
            self.cleanup_dispositions['kernel']='entered'
            try:
                need(type(k) is DevelopmentWorkerKernel and k.attempt is a,
                     'same actual registered kernel before raw cleanup')
                k.finish_raw_v1()
                self.cleanup_dispositions['kernel']='returned_raw_owner'
                if k.raw_first is not None:self.retain(k.raw_first,'kernel_prefix')
            except BaseException as error:
                self.cleanup_dispositions['kernel']='failed_or_unknown'
                self.retain(error,'kernel_finish')
        if a.native_channel is None and a.backend is None:
            # These original attempt slots are registered before launch. This
            # is an unreached owner, not a successful native close observation.
            self.cleanup_dispositions['host']='not_acquired'
        else:
            self.entered.append('host_terminal_custody')
            self.cleanup_dispositions['host']='entered'
            try:
                need(a.host_terminal_custody is None,'this original finalizer owns the sole H release continuation')
                terminal=DevelopmentHostTerminalCustody(a).close_v1()
                self.cleanup_dispositions['host']='returned_raw_owner'
                terminal.require_completed()
            except BaseException as error:
                self.cleanup_dispositions['host']='failed_or_unknown'
                self.retain(error,'host_terminal_custody')
        self.entered.append('publication_admission')
        try:
            need(type(k) is DevelopmentWorkerKernel and k.attempt is a and
                 type(producer) is DevelopmentNativeObservation and producer.attempt is a and
                 producer.kernel is k and k.native_observations is producer and
                 type(producer.publisher) is CanonicalPublisher and producer.publisher.owner is a.owner,
                 'fixed original kernel/producer/publisher before evidence publication')
            publisher=producer.publisher
            self.publication_admitted=True
        except BaseException as error:
            self.cleanup_dispositions['raw_capture']='unavailable_no_admitted_producer'
            self.cleanup_dispositions['process_receipt']='unavailable_no_admitted_producer'
            self.retain(error,'publication_admission');raise self.raw_first
        self.entered.append('raw_capture')
        try:
            need(a.evidence_capture is None,'this source route owns the sole raw capture pass')
            k.capture_available_evidence_v1(publisher)
        except BaseException as error:self.retain(error,'raw_capture')
        self.entered.append('process_receipt')
        try:producer.finish_original_process_v1()
        except BaseException as error:self.retain(error,'process_receipt')
        try:
            evidence=a.evidence_capture
            need(self.raw_first is None and a.raw_first is None and
                 type(evidence) is DevelopmentEvidenceCapture and evidence.attempt is a and
                 evidence.raw_first is None and a.process_observation is producer.observation and
                 a.process_observation.success,'actual complete original process/raw evidence, no nominal success')
            self.entered.append('stream_manifest');evidence.capture_stream_manifest_v2()
            self.entered.append('workspace_closure');evidence.capture_workspace_closure_v2()
            self.entered.append('aggregate_cost');evidence.capture_completion_cost_v2()
            from .development_process_receipt import require_original_process
            from .development_targets import require_targets
            self.entered.append('full_inverse')
            require_original_process(a);require_targets(a)
            a.pair.clock()  # Later failure keeps all original immutable captures.
            self.complete=True;return self.require_completed()
        except BaseException as error:self.retain(error,'typed_outputs');raise self.raw_first

def finalize_original_outputs_v2(attempt):
    return OriginalOutputFinalization(attempt).run_v2()
