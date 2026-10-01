def recompute_population(rows, population):
    assert len({r["neuron_id"] for r in rows})==len(rows), "duplicate unit"
    if population == "full_data_selected_same_trials":
        values=[float(r["pref_vs_rest_auc"]) for r in rows if int(r["category_selective"])]
    else:
        assert population=="crossfit_selected_at_least_five_splits"
        values=[]
        for r in rows:
            eligible=int(r["heldout_splits"])>=5
            assert int(r["heldout_eligible"])==int(eligible), "changed eligibility denominator"
            if eligible:
                values.append(float(r["heldout_auc"]))
    assert values and all(0<=x<=1 for x in values)
    return sum(values)/len(values), len(values)
