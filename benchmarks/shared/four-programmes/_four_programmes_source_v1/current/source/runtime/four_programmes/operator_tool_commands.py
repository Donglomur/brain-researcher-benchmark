"""Fixed original qualifier continuation and actual table capture under same H."""
from .operator_intake import require,canonical
from .operator_bootstrap_owner import RootBootstrapAdmission
from .backend_capture import CanonicalPublisher,CapturedRecord

_OWNER=object();_TABLE=object()

class QualifiedToolCommandOwnerV1:
    def __init__(self,token,admission):
        require(token is _OWNER,'same actual original qualifier continuation')
        self.admission=admission;self.parent=admission.parent
        self.entered=True;self.capture=None;self.binding=None;self.raw_first=None
        s=admission.prior_static.invocation.intake.body
        self.report=next(x for x in s['qualification_reports']if x['body']['domain']=='programme_tool_commands')
        self.source=next(x for x in s['qualification_reports']if x['body']['domain']=='installed_source')
        self.environment=admission.prior_static.invocation.profile['environment']
        self.pairs=s['static_values']['qualified_command_pairs']
    def require_original(self):
        from .early_resources import retain_source_failure
        parent=self.parent
        if parent.first_raw is not None:raise parent.first_raw
        try:
            self.admission.require_verified_root_v1()
            require(self.admission.prior_static.tool_owner is self and self.raw_first is None and
                    self.parent is self.admission.parent,'actual same earlier source/qualifier owner')
            return self
        except BaseException as error:
            raise retain_source_failure(parent,error,'QualifiedToolCommandOwnerV1.require_original')

class QualifiedProgrammeToolBindingV1:
    def __init__(self,token,owner,capture):
        require(token is _TABLE,'fixed completed table capture issuer')
        self.owner=owner;self.table_capture=capture
    def require_original(self):
        from .early_resources import retain_source_failure
        parent=self.owner.parent
        if parent.first_raw is not None:raise parent.first_raw
        try:
            self.owner.require_original();c=self.table_capture
            require(self.owner.binding is self and self.owner.capture is c and type(c)is CapturedRecord and
                    c.owner is self.owner.parent and c._attempt.complete is c and c._attempt.raw_first is None,
                    'actual same original completed tool table capture')
            return self
        except BaseException as error:
            raise retain_source_failure(parent,error,'QualifiedProgrammeToolBindingV1.require_original')
    def command_for_tool_v1(self,tool):
        from .early_resources import retain_source_failure
        parent=self.owner.parent
        if parent.first_raw is not None:raise parent.first_raw
        try:
            self.require_original();self.owner.parent.share.charge('work_units',len(self.owner.pairs)*64+4096)
            found=[x for x in self.owner.pairs if x['tool']==tool]
            require(len(found)==1,'exact selected qualified tool identity')
            return found[0]['command']
        except BaseException as error:
            raise retain_source_failure(parent,error,'QualifiedProgrammeToolBindingV1.command_for_tool_v1')

def produce_qualified_programme_tool_commands_v1(admission,outputs):
    require(type(admission)is RootBootstrapAdmission,'actual original fixed root admission')
    from .early_resources import retain_source_failure
    parent=admission.parent
    if parent.first_raw is not None:raise parent.first_raw
    try:
        admission.require_verified_root_v1();admission.require_canonical_publisher_binding_v3()
        p=admission.prior_static;require(p.tool_owner is None,'one qualifier table attempt including failure')
        owner=QualifiedToolCommandOwnerV1(_OWNER,admission);p.tool_owner=owner
        try:
            owner.require_original();plan=p.configuration['plan_constants']
            # Reserve before constructing/encoding the derived table; the complete
            # retained selection dominates this projection plus its fixed wrapper.
            bound=len(p.invocation.intake.raw)+4096
            owner.parent.share.charge('work_units',bound*8+4096)
            owner.parent.share.charge('retained_bytes',bound*16+4096)
            body={'schema':'ci_qualified_programme_tool_commands_v1',
                'source_admission':owner.source['descriptor'],'qualification':owner.report['descriptor'],
                'environment':owner.environment,
                'entries':[{'tool':x['tool'],'command':x['command']}for x in owner.pairs]}
            # The whole actual roster and all original qualification triples were
            # verified before this owner existed; never accept a supplied table.
            size=len(canonical(body));require(size<=bound,'earlier table allocation reservation')
            publisher=CanonicalPublisher(owner.parent,outputs,maximum_bytes=plan['maximum_output_bytes'],
                maximum_members=plan['maximum_members'],maximum_depth=plan['maximum_depth'])
            owner.publisher=publisher
            c=publisher.capture('qualified_programme_tool_commands_v1.json','QualifiedProgrammeToolCommandsV1',body)
            owner.capture=c;binding=QualifiedProgrammeToolBindingV1(_TABLE,owner,c);owner.binding=binding
            binding.require_original();return binding
        except BaseException as e:
            if owner.raw_first is None:owner.raw_first=e
            owner.parent.retain(e,'source_capture','publication_failure','produce_qualified_programme_tool_commands_v1')
            raise owner.raw_first
    except BaseException as error:
        raise retain_source_failure(parent,error,'produce_qualified_programme_tool_commands_v1')

def qualified_command_for_contract_v1(contract,tool):
    """One argv element from the same actual earlier admitted table only."""
    from .development_contract import DevelopmentContract,_CONTRACT
    require(type(contract)is DevelopmentContract and contract._token is _CONTRACT,
            'actual fixed admitted development contract')
    parent=contract.owner.parent
    from .early_resources import retain_source_failure
    if parent.first_raw is not None:raise parent.first_raw
    try:
        root=parent.operator_root_admission
        require(type(root)is RootBootstrapAdmission and root.parent is parent and
                parent.owner is contract.owner,'same actual original H owner')
        root.require_verified_root_v1()
        require(root.phase=='static_bound' and contract.admitted_open is parent.admitted_open and
                contract.admitted_open is not None and contract.identity_capture is not None,
                'actual earlier completed root, selection and contract publications')
        p=root.prior_static;captures=p.native_static_captures
        require(contract.policy_pin==captures['agent_policy'].pin and
                contract.policy==captures['agent_policy'].body and
                contract.profile_pin==captures['development_profile'].pin and
                contract.profile==captures['development_profile'].body,
                'same entire current native policy/profile, not an equal tool Pin alone')
        binding=p.tool_owner.binding;binding.require_original()
        require(contract.policy['tool_commands']==binding.table_capture.pin and
                tool in contract.policy['tool_closure'],'same complete selected earlier tool table')
        return binding.command_for_tool_v1(tool)
    except BaseException as error:
        raise retain_source_failure(parent,error,'qualified_command_for_contract_v1')

