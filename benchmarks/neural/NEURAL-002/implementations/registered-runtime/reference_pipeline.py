"""Full32-fold trusted baseline composition. Source only, unqualified.

An explicit future execution decision is required. Candidate model execution is
not hidden in this API; qualified process workers remain an unavailable route.
"""
import hashlib
from collections import defaultdict
from contract import PEOPLE, CELLS, vocabulary, require
from packets import fold
from controls import permute_training_labels
import morse_baselines as baseline
from scorer import score


def _nuisance(nuisance, records, arm):
    require(isinstance(nuisance, dict) and set(nuisance) ==
            {"arm", "independent_join_verified", "fields", "rows", "certificate_sha256"},
            "nuisance certificate schema")
    require(nuisance["arm"] == arm and nuisance["independent_join_verified"] is True,
            "unauthenticated diagnostic route")
    pin = nuisance["certificate_sha256"]
    require(isinstance(pin, str) and len(pin) == 64 and all(c in "0123456789abcdef" for c in pin),
            "independently reviewed nuisance certificate required")
    fields = tuple(nuisance["fields"])
    if arm == "order_only":
        require(fields == ("within_block_order",), "order diagnostic field")
    elif arm == "duration_only":
        require(fields == ("stimulus_duration_ms",), "duration diagnostic field")
    elif arm == "response_only":
        require(fields and all(isinstance(k, str) and k.startswith("response_onehot_") for k in fields),
                "response codes need independently frozen one-hot vocabulary")
    require(set(nuisance["rows"]) == {r["id"] for r in records}, "exact diagnostic ID coverage")
    return fields, nuisance["rows"]


def run_reference(records, arm="erp_shrinkage", *, seed=2002, nuisance=None):
    import numpy as np
    require(arm in ("erp_shrinkage", "prior_only", "permutation", "premarker",
                    "order_only", "duration_only", "response_only"), "unknown reference arm")
    # A premaker arm accepts independently prepared premarker records only.
    if arm == "premarker":
        require(isinstance(records, dict) and set(records) == {"window", "records"}
                and records["window"] == "sample-302 through sample-2 inclusive",
                "explicit fixed premarker preparation required")
        records = records["records"]
    diagnostic = arm in ("order_only", "duration_only", "response_only")
    fields, diagnostic_rows = _nuisance(nuisance, records, arm) if diagnostic else (None, None)
    predictions, targets, fitting = [], [], []
    for held in PEOPLE:
        views, private = fold(records, held)
        train = views["training"]
        if arm == "permutation":
            train = permute_training_labels(train, seed + PEOPLE.index(held))
        query = views["query"]
        for cell in CELLS:
            tr = [r for r in train if r["cell"] == cell]
            qu = [r for r in query if r["cell"] == cell]
            y = np.asarray([r["label"] for r in tr], dtype=np.int64)
            train_people, query_people = [r["participant"] for r in tr], [held]*len(qu)
            if arm == "prior_only":
                model = baseline.fit_prior(y, train_people, cell, vocabulary(cell))
                probs = baseline.predict_prior(model, query_people, cell)
            elif diagnostic:
                train_values = np.asarray([diagnostic_rows[r["id"]] for r in tr], dtype=np.float64)
                query_values = np.asarray([diagnostic_rows[r["id"]] for r in qu], dtype=np.float64)
                model = baseline.fit_nuisance(train_values, y, train_people, cell, vocabulary(cell), fields)
                probs = baseline.predict_nuisance(model, query_values, query_people, cell, fields)
            else:
                model = baseline.fit(np.stack([r["x"] for r in tr]), y, train_people, cell, vocabulary(cell))
                probs = baseline.predict(model, np.stack([r["x"] for r in qu]), query_people, cell)
            require(probs.shape == (len(qu), 26), "reference output shape")
            predictions.extend({"id": r["id"], "probabilities": p.tolist()} for r,p in zip(qu, probs))
            fitting.append({"held_participant": held, "cell": cell,
                            "training_participants": sorted(set(train_people)),
                            "training_rows": len(tr), "query_rows": len(qu),
                            "hyperparameters": "fixed; no held-person tuning"})
        targets.extend(private)
    return {"arm": arm, "predictions": predictions, "score": score(targets, predictions),
            "fits": fitting, "scientific_qualification": False}


def candidate_worker_contract():
    return {"modes": ["frozen_program", "case_adaptive"],
            "contexts": "one fresh worker per held participant, all six cells",
            "allowed": "31-person training data+labels; held person's opaque ID/cell/fixed EEG",
            "withheld": "held labels; source paths, sample/onset/order, duration, responses and evaluator state",
            "adaptation": "recipe frozen before query; no labels/score feedback; same unlabeled312-trial query batch in both modes",
            "budget": "operator must freeze equal model/tool/CPU/GPU/time/token limits before execution",
            "output": "one26-probability vector per opaque query ID; aggregate all32 folds before trusted score",
            "process_runner_available": False,
            "reason": "qualified separate-process isolation and authenticated intake are not yet established"}
