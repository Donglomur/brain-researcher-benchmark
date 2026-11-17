"""Exact absent external bindings remain absent; metadata cannot grant their authority."""
from .common import DependencyUnavailable, need

# New source acceptance must select exact independent bodies in a later reviewed
# configuration. These are not participant-provided choices or placeholders for success.
BINDINGS = {
    "hm_issuer_transport_native_qualification": None,
    "ci_early_parent_source_and_qualification": None,
    "ci_early_parent_completed_cost_observations": None,
    "ci_private_precommit_issuer": None,
    "ci_development_profile_and_backend": None,
    "context_v6_source_admission": None,
    "context_four_programme_source_templates": None,
    "root_issuer_source_and_qualification": None,
    "root_observer_host_clock_environment": None,
    "n098_same_process_startup_qualification": None,
}
HISTORICAL_UNAVAILABLE = {"n041_original_bank_a":"unresolved-owned original alternative"}

def require(role, selected):
    need(role in BINDINGS, "closed dependency role")
    expected = BINDINGS[role]
    if expected is None:
        raise DependencyUnavailable(role, "exact independently accepted source/runtime binding is not selected")
    need(selected == expected, "exact source-owned external binding")
    return expected
