"""Explicit missing source issuers. Scope metadata never creates live authority."""
from .contracts import ContractError

MISSING_PRODUCERS=(
 'same_open_original_capture_and_projection_observer',
 'original_scope_allocations_panel_leases_and_actual_capacity',
 'native_launcher_process_mount_and_state_isolation',
 'provider_identity_call_token_spending_and_transcript_owner',
 'safe_primitive_method_state_and_same_cell_tool_transport',
 'complete_operation_return_exit_EOF_reap_resource_observer',
 'original_outside_completion_and_late_target_capability')

class MissingNativeProducers(ContractError):
    def __init__(self,stage):
        super().__init__('N061 actual native issuer unavailable: '+stage)
        self.stage=stage;self.missing=MISSING_PRODUCERS

def require_native(stage,*actual_objects):
    # No Boolean, digest, callback, class-name or request factory can satisfy this.
    # A future separately reviewed concrete issuer/consumer must replace this
    # explicit source gap. The scientific algorithms/controller below remain real.
    raise MissingNativeProducers(stage)
