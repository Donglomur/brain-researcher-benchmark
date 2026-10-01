import pytest
from population_contract import recompute_population


def test_distinct_denominators():
    rows=[{"neuron_id":"a","category_selective":1,"pref_vs_rest_auc":.8,"heldout_splits":4,"heldout_eligible":0,"heldout_auc":""},
          {"neuron_id":"b","category_selective":0,"pref_vs_rest_auc":.6,"heldout_splits":5,"heldout_eligible":1,"heldout_auc":.4}]
    assert recompute_population(rows,"full_data_selected_same_trials")==(.8,1)
    assert recompute_population(rows,"crossfit_selected_at_least_five_splits")==(.4,1)
    rows[0]["heldout_eligible"]=1
    with pytest.raises(AssertionError,match="denominator"):
        recompute_population(rows,"crossfit_selected_at_least_five_splits")
