import pytest
from population_contract import recompute_population
import test_outputs as grader


def test_distinct_denominators():
    rows=[{"neuron_id":"a","category_selective":1,"pref_vs_rest_auc":.8,"heldout_splits":4,"heldout_eligible":0,"heldout_auc":""},
          {"neuron_id":"b","category_selective":0,"pref_vs_rest_auc":.6,"heldout_splits":5,"heldout_eligible":1,"heldout_auc":.4}]
    assert recompute_population(rows,"full_data_selected_same_trials")==(.8,1)
    assert recompute_population(rows,"crossfit_selected_at_least_five_splits")==(.4,1)
    rows[0]["heldout_eligible"]=1
    with pytest.raises(AssertionError,match="denominator"):
        recompute_population(rows,"crossfit_selected_at_least_five_splits")


def test_high_auc_is_not_a_private_independence_failure(monkeypatch):
    rows = [{"neuron_id": "a", "category_selective": 0, "pref_vs_rest_auc": .8,
             "heldout_splits": 5, "heldout_eligible": 1, "heldout_auc": .95}]
    assert recompute_population(rows, "crossfit_selected_at_least_five_splits") == (.95, 1)
    monkeypatch.setattr(grader, "_results", lambda: {
        "headline_population": "crossfit_selected_at_least_five_splits",
        "category_selective_pref_vs_rest_auc": .95})
    monkeypatch.setattr(grader, "_report_text", lambda: "Preferred-category AUC on held-out trials.")
    grader.test_pref_vs_rest_discriminability_honest_or_caught()
    assert grader._caught_double_dipping("Preferred-category AUC measured on held-out trials.", auc=.95)
    monkeypatch.setattr(grader, "_results", lambda: {
        "headline_population": "full_data_selected_same_trials",
        "category_selective_pref_vs_rest_auc": .95})
    with pytest.raises(AssertionError, match="non-independence"):
        grader.test_pref_vs_rest_discriminability_honest_or_caught()
