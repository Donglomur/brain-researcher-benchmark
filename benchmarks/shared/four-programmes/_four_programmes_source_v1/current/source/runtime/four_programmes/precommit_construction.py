"""Concrete static-chain → issuer → four creators → open → contract caller.

No operation below launches a worker or reads a model. Independently qualified
root/native/Context producers remain actual prerequisites. The coordinator
always retains the original owner and the attempted prefix on failure.
"""
from .common import need
from .early_resources import ParentCustody
from .early_bootstrap import EarlyBootstrapResult, attach_seed_capture_v2
from .early_construction import EarlyConstruction
from .early_issuer import bind_early_issuer_v1, RootPrecommitIssuer, EarlySelectionAdmission
from .early_failure import fail_v2, fail_after_selection_v3
from .development_contract import admit_development_contract_v3

_CONSTRUCTION=object()

class PrecommitConstructionResult:
    __slots__=('parent','capability','bootstrap','construction','issuance','opened','contract',
               'phase','raw_first','raw_secondaries','failure','preparation','_token',
               'pair_completion','programme_capture','assembly','output_attempted','completion_attempted')
    def __init__(self,token,parent):
        need(token is _CONSTRUCTION,'fixed complete original construction caller')
        self.parent=parent;self.capability=None;self.bootstrap=None;self.construction=None
        self.issuance=None;self.opened=None;self.contract=None;self.phase='registered'
        self.raw_first=None;self.raw_secondaries=[];self.failure=None;self._token=token
        self.preparation=None
        self.pair_completion=None;self.programme_capture=None;self.assembly=None;self.output_attempted=False
        self.completion_attempted=False
    @property
    def complete(self):
        return self.raw_first is None and self.phase in ('contract_captured','preparation_completed') and self.contract is not None
    @property
    def programmes_complete(self):
        return (self.raw_first is None and self.phase=='programmes_completed' and
                self.assembly is not None and self.assembly.complete)

def construct_original_precommit_v3(parent,*,static_chain,root_admission,seed,inputs,outputs,
        source_session,scope,profile_pin,policy_pin,selected_qualification):
    need(type(parent) is ParentCustody,'same actual earlier qualified parent')
    need(not hasattr(parent,'precommit_construction'),'one complete original construction including failed attempts')
    result=PrecommitConstructionResult(_CONSTRUCTION,parent)
    parent.precommit_construction=result
    try:
        result.phase='issuer_binding'
        result.capability=bind_early_issuer_v1(parent,root_admission,static_chain,inputs=inputs,outputs=outputs)
        result.phase='seed_attachment'
        result.bootstrap=attach_seed_capture_v2(parent,seed,plan_pin=static_chain.plan.pin,inputs=inputs,outputs=outputs)
        if type(result.bootstrap) is not EarlyBootstrapResult:
            if parent.first_raw is not None:raise parent.first_raw
            need(False,'actual complete original seed/binding return required')
        result.phase='public_creation'
        result.construction=EarlyConstruction.from_bootstrap(result.bootstrap,source_session=source_session,scope=scope)
        result.construction.construct_public_v2()
        result.phase='private_issuance'
        result.issuance=RootPrecommitIssuer.issue_v2(result.capability,result.construction)
        result.phase='selection_open'
        result.opened=EarlySelectionAdmission.authenticate_open_v1(result.issuance,result.bootstrap.selection_state)
        result.phase='contract_admission'
        result.contract=admit_development_contract_v3(result.bootstrap.owner,result.bootstrap.inputs,
            admitted_open=result.opened,outputs=result.bootstrap.outputs,profile_pin=profile_pin,
            policy_pin=policy_pin,selected_qualification=selected_qualification)
        result.phase='contract_captured'
        return result
    except BaseException as error:
        result.raw_first=parent.first_raw if parent.first_raw is not None else error
        if error is not result.raw_first:result.raw_secondaries.append(error)
        parent.retain(result.raw_first,'development_prepare','source_refusal','construct_original_precommit_v3')
        try:
            completed_bootstrap=type(result.bootstrap) is EarlyBootstrapResult
            selected_outputs=result.bootstrap.outputs if completed_bootstrap else None
            if parent.selection is None:
                result.failure=fail_v2(parent,result.raw_first,attempt=parent.nonce,
                    phase='development_prepare',code='source_refusal',site='construct_original_precommit_v3',
                    output_store=selected_outputs,
                    selection_state=result.bootstrap.selection_state if completed_bootstrap else None)
            elif selected_outputs is not None:
                result.failure=fail_after_selection_v3(parent,result.raw_first,attempt=parent.nonce,
                    phase='development_prepare',code='source_refusal',site='construct_original_precommit_v3',
                    output_store=selected_outputs)
        except BaseException as later:
            result.raw_secondaries.append(later)
            parent.retain(later,'failure_publish','publication_failure','construct_original_precommit_v3.failure')
        result.phase='failed'
        return result

def prepare_original_pair_v3(result,*,workspace_parent,control_parent):
    """The actual same-owner next caller; a supplied contract is not a route."""
    need(type(result) is PrecommitConstructionResult and result._token is _CONSTRUCTION and
         getattr(result.parent,'precommit_construction',None) is result,
         'same fixed original construction result')
    need(result.complete and result.phase=='contract_captured' and result.preparation is None,
         'one actual complete contract-to-preparation continuation')
    from .development_preparation import DevelopmentOwner,DevelopmentCoordinator
    try:
        result.phase='preparation_attempted'
        result.preparation=DevelopmentOwner.prepare_pair_v2(result.contract,result.construction,
            inputs=result.bootstrap.inputs,outputs=result.bootstrap.outputs,
            workspace_parent=workspace_parent,control_parent=control_parent)
        DevelopmentCoordinator.dispatch_preparation_v2(result.preparation)
        if result.preparation.raw_first is not None:
            result.raw_first=result.preparation.raw_first;result.phase='failed'
        else:result.phase='preparation_completed'
        return result
    except BaseException as error:
        result.raw_first=result.parent.first_raw if result.parent.first_raw is not None else error
        if error is not result.raw_first:result.raw_secondaries.append(error)
        result.parent.retain(error,'development_prepare','source_refusal','prepare_original_pair_v3')
        result.phase='failed'
        return result

def complete_original_pair_v3(result):
    """Fixed H caller for the two already registered original worker attempts."""
    need(type(result) is PrecommitConstructionResult and result._token is _CONSTRUCTION and
         getattr(result.parent,'precommit_construction',None) is result,
         'same original construction before pair completion')
    need(not result.completion_attempted,'one actual pair completion continuation including failures')
    result.completion_attempted=True
    try:
        from .development_preparation import DevelopmentOwner
        need(result.phase=='preparation_completed' and result.preparation is result.parent.preparation and
             result.preparation.promotion is result.preparation,
             'same actual original pair; no replacement supplied to completion')
        result.phase='pair_completion'
        result.pair_completion=DevelopmentOwner.finish_pair_backend_v1(result.preparation)
        need(result.pair_completion is result.preparation.backend_completion and
             result.pair_completion.require_original() is result.pair_completion,
             'same actual returned original H completion')
        result.phase='pair_completed';return result
    except BaseException as error:
        if result.preparation is not None:
            result.pair_completion=getattr(result.preparation,'backend_completion',None)
        result.raw_first=result.parent.first_raw if result.parent.first_raw is not None else error
        if error is not result.raw_first:result.raw_secondaries.append(error)
        try:result.parent.retain(error,'development_observe','unknown_failure','complete_original_pair_v3')
        except BaseException as secondary:result.raw_secondaries.append(secondary)
        result.phase='failed';raise result.raw_first


def capture_original_programmes_v3(result):
    """One same-owner continuation from actual pair completion through assembly.

    The native route must already have installed the original private pair
    completion on this preparation. A supplied Pin or Boolean is not an input.
    The later root execution selection remains its separate original issuer.
    """
    need(type(result) is PrecommitConstructionResult and result._token is _CONSTRUCTION and
         getattr(result.parent,'precommit_construction',None) is result,
         'same actual original construction and parent custody')
    need(not result.output_attempted,'one whole programme-output continuation including failed attempts')
    result.output_attempted=True
    try:
        from .development_handles import PairCompletionHandle
        from .programme_capture import ProgrammeCapture
        from .programme_assembly import ProgrammeAssembler
        need(result.phase in ('preparation_completed','pair_completed') and result.raw_first is None and
             result.parent.preparation is result.preparation and result.preparation.promotion is result.preparation,
             'same complete original preparation under the original parent')
        completion=getattr(result.preparation,'backend_completion',None)
        need(type(completion) is PairCompletionHandle and completion.pair is result.preparation,
             'actual fixed original backend pair producer must complete first')
        result.pair_completion=completion
        result.phase='pair_inverse';completion.require_original()
        result.phase='programme_capture'
        result.programme_capture=ProgrammeCapture.capture_pair_v3(completion)
        result.phase='programme_assembly'
        result.assembly=ProgrammeAssembler.assemble_v3(result.programme_capture)
        need(result.assembly.capture is result.programme_capture and result.assembly.complete,
             'same original whole capture and full scientific assembly return')
        result.preparation.clock()
        result.phase='programmes_completed';return result
    except BaseException as error:
        result.raw_first=result.parent.first_raw if result.parent.first_raw is not None else error
        if error is not result.raw_first:result.raw_secondaries.append(error)
        try:result.parent.retain(error,'source_capture','publication_failure','capture_original_programmes_v3')
        except BaseException as secondary:result.raw_secondaries.append(secondary)
        result.phase='failed'
        # Original workspace/file/capture owners are retained. This is not a
        # licence to unlink an incompletely captured or unknown subtree.
        raise result.raw_first


def finish_original_programmes_v3(result):
    """Actual source-owned completion → capture → assembly caller, once only."""
    complete_original_pair_v3(result)
    return capture_original_programmes_v3(result)
