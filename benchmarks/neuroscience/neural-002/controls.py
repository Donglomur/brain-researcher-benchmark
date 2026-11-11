"""Deterministic training-only null and nuisance contracts."""
import random
from collections import defaultdict
from contract import require


def permute_training_labels(training, seed):
    require(type(seed) is int and 0 <= seed < 2**63, "permutation seed")
    result = [dict(row) for row in training]
    grouped = defaultdict(list)
    for i, row in enumerate(result):
        grouped[row["participant"], row["cell"]].append(i)
    rng = random.Random(seed)
    for key in sorted(grouped):
        indices = grouped[key]
        labels = [result[i]["label"] for i in indices]
        rng.shuffle(labels)
        for i, label in zip(indices, labels):
            result[i]["label"] = label
    return result


CONTROL_PLAN = {
    "erp_shrinkage": "original train-only diagonal-shrinkage centroid baseline",
    "prior_only": "training-fold class frequencies; no query labels",
    "order_only": "trusted diagnostic from original chronological trial index, never candidate input",
    "premarker": "same301 samples immediately before marker, same32folds and preprocessing",
    "permutation": "training labels shuffled within participant/cell; held query targets fixed",
    "response_only": "unavailable until independently authenticated exact behavioral join/response encoding",
    "duration_only": "unavailable until event duration provenance and exact behavior timing authenticated",
    "mode_comparison": "frozen program vs case-adaptive; same tools/input/budget, no label feedback",
}
