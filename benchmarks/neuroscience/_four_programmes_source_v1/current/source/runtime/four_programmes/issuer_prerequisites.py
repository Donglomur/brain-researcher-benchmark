"""Fixed actual installed-entry admission, replacing the old unconditional holds."""
from .common import need
from .operator_bootstrap_owner import PriorStaticAdmission,RootBootstrapAdmission

def require_prior_static_owner(owner,selection):
    need(type(owner)is PriorStaticAdmission,'actual source-owned earlier original admission')
    owner.require_original()
    need(owner.static_selection is selection and owner.plan_values is not None and owner.policy_values is not None,
         'actual completed native/static producer selection, no wire substitute')
    return owner

def require_root_bootstrap_admission(admission,parent,chain):
    need(type(admission)is RootBootstrapAdmission,'actual registered installed-root admission')
    admission.require_verified_root_v1()
    need(admission.parent is parent and admission.phase=='static_bound'and admission.chain is chain,
         'same later actual completed static chain and original ParentCustody')
    return admission
