"""Exact train/query boundaries for an independently admitted source provider.

The caller is trusted operator infrastructure. A reader sees only explicit
requested row IDs; candidate workers receive the returned packet, never a reader,
global arrays, source paths, screening responses or protected grading targets.
Actual OS isolation and source admission are separate required qualifications.
"""
from .strict import need, digest, sha
from .programme import CONFIGS
from .splits import training_permutation
from .units import require_hz


def _array(a, shape, name, *, boolean=False, finite=True):
    import numpy as np
    need(isinstance(a, np.ndarray) and a.shape == tuple(shape), "shape", name+": exact admitted shape required")
    need(a.dtype == np.dtype(bool) if boolean else a.dtype.kind == "f" and a.dtype.itemsize == 8,
         "dtype", name+": bool support or float64 numeric array required")
    need(a.flags.c_contiguous, "layout", name+": contiguous prepared array required")
    if finite:
        need(np.isfinite(a).all(), "finite", name+": finite supplied values required")
    return a


def _dimensions(case, dimensions):
    need(case in CONFIGS and type(dimensions) is dict and set(dimensions) == {
        "configuration", "cells", "time_windows", "feature_ids", "feature_groups", "admission_digest", "response_units"},
        "admission", "Exact admitted case dimensions required")
    need(dimensions["configuration"] == case, "admission", "Dimension/case mismatch")
    from .strict import natural
    natural(dimensions["cells"], "complete admitted cell count")
    natural(dimensions["time_windows"], "complete native time support")
    need(type(dimensions["feature_ids"]) is list and len(set(dimensions["feature_ids"])) == 20
         and len(dimensions["feature_ids"]) == 20
         and all(type(x) is str and x for x in dimensions["feature_ids"])
         and dimensions["feature_groups"] == ["shape"]*10+["appearance"]*10,
         "features", "Exact admitted twenty source coordinates required")
    sha(dimensions["admission_digest"])
    require_hz(dimensions["response_units"])
    return dimensions["cells"], dimensions["time_windows"]


def prepare_training_packet(view, case, control, read_rows, dimensions):
    """Read permitted rows only; response permutation never reaches outer queries.

    read_rows(kind, configuration, row_ids) is an operator-owned prepared source
    reader. Kind is features/time/static/time_support/static_support. It returns
    exactly the given order. Raw-to-window preparation must already be admitted.
    """
    import numpy as np
    cells, times = _dimensions(case, dimensions)
    need(type(control) is int and -1 <= control < 20 and callable(read_rows), "packet", "Exact control/reader required")
    training = view["training"]
    rows = [r for r in training if r["configuration"] == case]
    need(rows and not ({r["group_id"] for r in rows} & {r["group_id"] for r in view["queries"]}),
         "leakage", "No global query identity may enter a fit packet")
    ids = [r["row_id"] for r in rows]
    mapping = {r["row_id"]: r["row_id"] for r in training} if control == -1 else training_permutation(
        training, view["fold"], view["regime"], control)
    response_ids = [mapping[i] for i in ids]
    allowed = set(ids)
    need(set(response_ids) == allowed, "leakage", "Complete same-configuration training correspondence required")
    groups = [r["group_id"] for r in rows]
    folds = [view["inner_folds"][g] for g in groups]
    packet = {"schema": "paper020_training_packet_v1", "configuration": case,
              "regime": view["regime"], "outer_fold": view["fold"], "control": control,
              "row_ids": ids, "response_row_ids": response_ids, "group_ids": groups,
              "inner_folds": folds, "familiarity": np.asarray([r["stratum"] == "familiar" for r in rows], dtype=np.int64),
              "dimensions": dimensions, "view_digest": digest({"rows": rows, "groups": groups,
                  "inner_folds": folds, "outer_assignment": view["assignment_digest"],
                  "response_row_ids": response_ids, "regime": view["regime"], "control": control})}
    packet["features"] = _array(read_rows("features", case, ids), (len(ids), 20), "training features")
    for kind, shape in (("time", (len(ids), cells, times)), ("static", (len(ids), cells))):
        packet[kind] = _array(read_rows(kind, case, response_ids), shape, kind, finite=False)
        packet[kind+"_support"] = _array(read_rows(kind+"_support", case, response_ids), shape,
                                          kind+" support", boolean=True)
        need(np.isfinite(packet[kind][packet[kind+"_support"]]).all(), "support", "Declared target support must be finite")
    return packet


def fit_reference_packet(packet):
    """Fit the entire nested portfolio with no query-feature argument or reader."""
    from .references import select_fit_reference, freeze_reference
    expected = {"schema", "configuration", "regime", "outer_fold", "control", "row_ids", "response_row_ids",
                "group_ids", "inner_folds", "familiarity", "dimensions", "view_digest", "features",
                "time", "static", "time_support", "static_support"}
    need(type(packet) is dict and set(packet) == expected and packet["schema"] == "paper020_training_packet_v1",
         "packet", "Training-only exact packet required; query fields forbidden")
    cells, times = _dimensions(packet["configuration"], packet["dimensions"])
    n = len(packet["row_ids"])
    need(n > 0 and len(set(packet["row_ids"])) == n and set(packet["response_row_ids"]) == set(packet["row_ids"]),
         "identity", "Complete unique training-row correspondence required")
    _array(packet["features"], (n, 20), "training features")
    for k, s in (("time", (n, cells, times)), ("static", (n, cells))):
        _array(packet[k], s, k, finite=False)
        _array(packet[k+"_support"], s, k+" support", boolean=True)
    sha(packet["view_digest"])
    artifact = select_fit_reference(packet["features"], packet["time"], packet["static"], packet["familiarity"],
        packet["group_ids"], packet["inner_folds"], regime=packet["regime"],
        time_support=packet["time_support"], static_support=packet["static_support"])
    serialized = freeze_reference(artifact)
    import hashlib
    return {"model": serialized, "model_digest": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
            "view_digest": packet["view_digest"], "configuration": packet["configuration"],
            "admission_digest": packet["dimensions"]["admission_digest"],
            "response_units": packet["dimensions"]["response_units"], "qualified": False}


def predict_reference_packet(sealed, query, *, observed_fit_digest):
    """Pure read-only inference after the external all-configuration fit seal."""
    import hashlib
    from .references import thaw_reference, predict_reference
    need(type(sealed) is dict and set(sealed) == {"model", "model_digest", "view_digest", "configuration", "admission_digest", "response_units", "qualified"},
         "seal", "Exact source-frozen model artifact required")
    sha(observed_fit_digest)
    before = hashlib.sha256(sealed["model"].encode("utf-8")).hexdigest()
    need(before == sealed["model_digest"] == observed_fit_digest, "seal", "Changed or unobserved fit artifact")
    need(type(query) is dict and set(query) == {"configuration", "row_ids", "features", "familiarity", "dimensions"}
         and query["configuration"] == sealed["configuration"], "packet", "Query features only; no response fields")
    cells, times = _dimensions(query["configuration"], query["dimensions"])
    need(query["dimensions"]["admission_digest"] == sealed["admission_digest"], "admission", "Source admission changed")
    require_hz(sealed["response_units"])
    need(query["dimensions"]["response_units"] == sealed["response_units"], "units", "Fit/query response units or provenance changed")
    n = len(query["row_ids"])
    need(n > 0 and len(set(query["row_ids"])) == n, "identity", "Unique nonempty query row IDs required")
    _array(query["features"], (n, 20), "query features")
    prediction = predict_reference(thaw_reference(sealed["model"]), query["features"], query["familiarity"])
    for kind, shape in (("time", (n, cells, times)), ("static", (n, cells))):
        _array(prediction[kind], shape, kind+" predictions")
    need(before == hashlib.sha256(sealed["model"].encode("utf-8")).hexdigest(), "seal", "Model mutation during inference")
    return {"row_ids": list(query["row_ids"]), **prediction, "model_digest": before,
            "response_units": sealed["response_units"]}


def prediction_expectations(admission, contract, closed_fit_seals):
    """Independent source/group/fit-derived complete output schemas, no targets.

    The operator constructs these after all actual fit receipts close. Neither
    candidate dimensions nor submitted row orders determine the expected schema.
    """
    from .admission import validate_admission
    from .splits import make_outer_assignment, fold_view
    from .programme import ACTORS, REGIMES
    validate_admission(admission, contract)
    expected_seals = {(a,r,f,c) for a in ACTORS for r in REGIMES for f in range(6) for c in range(-1,20)}
    need(type(closed_fit_seals) is dict and set(closed_fit_seals) == expected_seals,
         "coverage", "All observed and null complete-fit seals required")
    assignment = make_outer_assignment(admission["rows"])
    expected = {}
    for regime in REGIMES:
        for fold in range(6):
            view = fold_view(admission["rows"], assignment, fold, regime)
            for actor in ACTORS:
                for control in range(-1,20):
                    seal = closed_fit_seals[(actor,regime,fold,control)]
                    need(type(seal) is dict and set(seal) == {"fit_models","fit_receipts"}
                         and set(seal["fit_models"]) == set(CONFIGS) and set(seal["fit_receipts"]) == set(CONFIGS),
                         "seal", "All fourteen independent closed models required")
                    for case in CONFIGS:
                        model, receipt = seal["fit_models"][case], seal["fit_receipts"][case]
                        sha(model); sha(receipt)
                        ids = [r["row_id"] for r in view["queries"] if r["configuration"] == case]
                        header = admission["cases"][case]
                        expected[(actor,regime,fold,control,case)] = {
                            "row_ids":ids,"time_shape":[len(ids),len(header["cell_ids"]),len(header["time_bins"])],
                            "static_shape":[len(ids),len(header["cell_ids"])],"model_digest":model,"fit_receipt_digest":receipt,
                            "response_units":header["response_units"]}
    return expected
