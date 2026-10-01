from metric_contract import pooled_balanced_accuracy


def test_constant_predictions_have_pooled_half_chance():
    labels = [1]*6 + [0]*4
    assert pooled_balanced_accuracy(labels, [1]*10) == .5
    assert pooled_balanced_accuracy(labels, [0]*10) == .5
    assert sum([1]*6+[0]*4)/10 == .6  # Legacy equal-site one-class recall is different.
