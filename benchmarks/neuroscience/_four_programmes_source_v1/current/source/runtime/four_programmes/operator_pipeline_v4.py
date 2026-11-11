"""Prospective actual installed-entry through completed static-chain caller.

No operands are accepted from a participant. Unavailable installed profile,
Q1 or either native-domain evidence fails at its actual verifier. This route
does not activate a worker or supply an environment/qualification by default.
"""
from .operator_intake import require
from .early_resources import retain_source_failure

_PIPELINE=object()
class InstalledStaticPipelineV4:
    def __init__(self,token,root):
        require(token is _PIPELINE,'fixed no-argument installed entry caller')
        self.root=root;self.parent=root.parent;self.outputs=None;self.publisher_binding=None
        self.tools=None;self.anchor=None;self.chain=None;self.complete=False
        self.raw_first=None;self.secondaries=[];self.close_entered=False;self.closed=False
    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        return retain_source_failure(self.parent,error,'InstalledStaticPipelineV4.'+site)
    def require_original(self):
        p=self.parent
        if p.first_raw is not None:raise p.first_raw
        try:
            self.root.require_verified_root_v1()
            require(getattr(self.root,'installed_pipeline_v4',None)is self and self.complete and
                    self.root.phase=='static_bound'and self.root.chain is self.chain and
                    self.root.prior_static.native_static_anchor is self.anchor and
                    self.publisher_binding is self.root.prior_static.canonical_publisher_binding,
                    'same original completed source/qualification/native/static pipeline')
            self.anchor.require_completed_policy_profile_v3();return self
        except BaseException as error:raise self.retain(error,'require_original')
    def close_native_once(self):
        # Resource-owner terminal caller must invoke this once after the last
        # actual source consumer. It grants no publication/measurement success.
        if self.close_entered:return self.closed
        self.close_entered=True
        if self.anchor is None:self.closed=True;return True
        try:self.closed=self.anchor.close_all_once()
        except BaseException as error:self.retain(error,'terminal_close');self.closed=False
        return self.closed

def installed_static_pipeline_v4():
    from .operator_entry import installed_operator_entry_v1
    from .operator_bootstrap_owner import RootBootstrapAdmission
    from .operator_source_binding import bind_canonical_publisher_source_v3
    from .operator_tool_commands import produce_qualified_programme_tool_commands_v1
    from .backend_native_v3_issuers import admit_native_static_v4
    from .operator_native_static import bind_native_static_completion_v1
    from .early_issuer import prepare_static_issuer_inputs_v1
    from .common import Store
    root=installed_operator_entry_v1()
    require(type(root)is RootBootstrapAdmission,'actual original entry returned private root owner')
    parent=root.parent
    if parent.first_raw is not None:raise parent.first_raw
    require(getattr(root,'installed_pipeline_v4',None)is None,'one original fixed static pipeline')
    attempt=InstalledStaticPipelineV4(_PIPELINE,root);root.installed_pipeline_v4=attempt
    try:
        attempt.publisher_binding=bind_canonical_publisher_source_v3(root)
        config=root.prior_static.configuration
        # The selected path and its Store observations are charged before
        # constructing the real Store; no path is inferred from a tool Pin.
        path=config['policy_constants']['capture_root']
        parent.share.charge('work_units',len(path.encode('utf-8'))*64+4096)
        parent.share.charge('retained_bytes',len(path.encode('utf-8'))*16+4096)
        attempt.outputs=Store(path,parent.share)
        attempt.tools=produce_qualified_programme_tool_commands_v1(root,attempt.outputs)
        attempt.anchor=admit_native_static_v4(root,attempt.outputs)
        prior=bind_native_static_completion_v1(root,attempt.anchor)
        attempt.chain=prepare_static_issuer_inputs_v1(prior,attempt.anchor,attempt.outputs)
        attempt.complete=True;return attempt.require_original()
    except BaseException as error:
        attempt.retain(error,'run')
        # The anchor registers before acquisition, including failed calls that
        # could not return to the assignment above. Retain that exact owner.
        if attempt.anchor is None:
            attempt.anchor=root.native_context_anchor_attempts.get('native_C00_v4')
        attempt.close_native_once()
        raise attempt.raw_first
