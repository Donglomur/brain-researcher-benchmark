"""Source-free qualification of authoring component construction/classification.

No original_reference fixture request or scientific files. This module is not
part of the planned production scoring allowlist.
"""
import copy

import pytest

import proof_of_work as p
import spin_math as m
from test_actual_outputs import scalar_candidate, observable_differences


def manufactured(*, active=True, signed=True, tie=False):
    observed = -.5 if signed else .5
    nulls = [dict(rotation_id=i, status="ok" if active else "inactive_gradient",
                  r=((-.5 if tie else -.2) if signed else (.5 if tie else .2)) if active else None)
             for i in range(100)]
    derived = m.summarize("ok" if active else "inactive_gradient", observed if active else None, nulls)
    return p.expected_results(derived, "original", 0, 100)


@pytest.mark.parametrize("mode", ["gaussian_null", "absolute_signed_r", "strict_greater_count", "no_plus_one", "wrong_count", "fabricated_null_support"])
def test_effective_components_change_observable_and_fail_own_replay(mode):
    original = manufactured(tie=True)
    before = copy.deepcopy(original)
    changed, why = scalar_candidate(original, mode)
    assert why is None and observable_differences(original, changed)
    with pytest.raises(ValueError): p.validate_results(changed, original)
    assert original == before


@pytest.mark.parametrize("mode", ["gaussian_null", "strict_greater_count", "rounded_rank", "no_plus_one", "wrong_count"])
def test_inactive_components_explicitly_unavailable(mode):
    changed, why = scalar_candidate(manufactured(active=False), mode)
    assert changed is None and why


@pytest.mark.parametrize("mode", ["absolute_signed_r", "strict_greater_count", "rounded_rank"])
def test_nondiscriminating_components_not_claimed_rejections(mode):
    original = manufactured(signed=False, tie=False)
    changed, why = scalar_candidate(original, mode)
    assert why is None and not observable_differences(original, changed)
    p.validate_results(changed, original)


def test_rounded_rank_changes_exact_count_without_changing_nulls():
    original = manufactured(signed=False)
    original["pearson_r"] = .50000004
    for row in original["null_distribution"]: row["r"] = .50000001
    changed, why = scalar_candidate(original, "rounded_rank")
    assert why is None and changed["n_exceedances"] == 100
    assert original["n_exceedances"] == 0
    assert changed["null_distribution"] == original["null_distribution"]
    assert observable_differences(original, changed)


def test_canonical_inactive_support_fabrication_is_effective():
    original = manufactured(active=False)
    changed, why = scalar_candidate(original, "fabricated_null_support")
    assert why is None and observable_differences(original, changed)
    with pytest.raises(ValueError): p.validate_results(changed, original)


def test_integer_count_change_is_exact_even_when_p_change_rounds_small():
    assert observable_differences(1, 2)
    assert not observable_differences(.1, .10000001)


def test_unknown_component_rejected():
    with pytest.raises(ValueError): scalar_candidate(manufactured(), "unknown")
