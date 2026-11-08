"""Independent full-session reference; numerical entry points are future sandbox work.

No imports of numerical libraries, data reads, fits or model deserialization occur
at module import. This source is not an activation/qualification authority.
"""
import hashlib
import json
import math
import re

SCHEMA = "neural060-independent-reference-v1"
DESIGN_SHA256 = "206992a77c2470587fec83c84b2b4362c753b0d9f697a1e7d1923e5d5a82a471"
FAMILIES = ("linear", "trees", "fourier")
ROLES = ("nuisance", "joint")
ALPHAS = (0.01, 0.1, 1.0, 10.0, 100.0)
TREE_GRID = ((20, 2), (20, 10), (None, 2), (None, 10))
FOURIER_GRID = ((256, 1.0), (256, 10.0), (1024, 1.0), (1024, 10.0))
ID = re.compile(r"[0-9a-f]{32}\Z")
FIELDS = (("history_speed", 50), ("history_position", 50),
          ("history_offsets", 50), ("target_offsets", 50),
          ("stimulus_block", 12))
ROW_FIELDS = {"case_id", "session_id", *(name for name, _ in FIELDS),
              "stimulus_latency_s"}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("utf-8")


def identity(role, session_ordinal):
    need(type(role) is str and role in ROLES, "Exact nuisance or joint reference role")
    need(type(session_ordinal) is int and 1 <= session_ordinal <= 29,
         "Original sorted source-session ordinal 1..29")


def tree_seed(session_ordinal):
    identity("nuisance", session_ordinal)
    raw = encoded(["neural060-reference-v1", 20261107, session_ordinal, "extra_trees"])
    return int.from_bytes(hashlib.sha256(raw).digest()[:4], "big")


def fourier_seed(session_ordinal, block, column):
    identity("nuisance", session_ordinal)
    need(block in ("nuisance", "neural") and type(column) is int and 0 <= column < 512,
         "Frozen Fourier block and column")
    raw = encoded(["neural060-fourier-v1", 20261107, session_ordinal, block, column])
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def configurations():
    """Fresh metadata in the exact prospective family/grid order."""
    return {
        "linear": [{"alpha": a} for a in ALPHAS],
        "trees": [{"max_depth": d, "min_samples_leaf": n} for d, n in TREE_GRID],
        "fourier": [{"width": d, "alpha": a} for d, a in FOURIER_GRID],
    }


def training_plan(role, session_ordinal):
    identity(role, session_ordinal)
    rows = []
    for family, grid in configurations().items():
        for i, config in enumerate(grid):
            rows.append({"phase": "validation_fit", "family": family,
                         "config_ordinal": i, "config": config})
    rows.extend({"phase": "winner_refit", "family": f} for f in FAMILIES)
    need(len(rows) == 16, "Thirteen validation fits and three refits")
    return rows


def finite(value, label):
    try:
        ok = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        ok = False
    need(ok, "Finite binary64 " + label + "; no bool")
    return float(value)


def row_metadata(rows, labelled, expected_session=None):
    """Full strict row admission, no NumPy or fitting side effect."""
    need(type(labelled) is bool and type(rows) is list and len(rows) > 0,
         "Nonempty complete split rows")
    want = ROW_FIELDS | ({"wheel_speed"} if labelled else set())
    ids, session = [], expected_session
    for row in rows:
        need(type(row) is dict and set(row) == want,
             "Exact labelled fitting or unlabelled inference row fields")
        need(all(type(row[k]) is str and ID.fullmatch(row[k]) for k in ("case_id", "session_id")),
             "Opaque32hex reference identity")
        if session is None:
            session = row["session_id"]
        need(row["session_id"] == session, "Single original session per reference")
        ids.append(row["case_id"])
        for name, n in FIELDS:
            need(type(row[name]) is list and len(row[name]) == n, "Exact " + name + " geometry")
            for value in row[name]:
                finite(value, name)
        need(all(v >= 0 for v in row["history_speed"]), "Absolute historical speed")
        need(row["history_position"][-1] == 0, "Position translated by last history value")
        need(all(-1 <= v < 0 for v in row["history_offsets"])
             and all(0 <= v < 1 for v in row["target_offsets"]), "Original half-open offsets")
        need(all(a < b for a, b in zip(row["history_offsets"], row["history_offsets"][1:]))
             and all(a < b for a, b in zip(row["target_offsets"], row["target_offsets"][1:])),
             "Chronological actual sample offsets")
        sb = row["stimulus_block"]
        need(all(v in (0, 1) for v in sb) and sum(sb[:9]) == 1 and sum(sb[9:]) == 1,
             "Original nine-way stimulus and three-way prior one-hot codes")
        need(finite(row["stimulus_latency_s"], "stimulus latency") > 0,
             "Stimulus precedes movement")
        if labelled:
            need(type(row["wheel_speed"]) is list and len(row["wheel_speed"]) == 50,
                 "All50 fitting target samples")
            need(all(finite(v, "training target") >= 0 for v in row["wheel_speed"]),
                 "Absolute training target speed")
    need(len(set(ids)) == len(ids), "No duplicate split case")
    return {"session_id": session, "case_ids": ids, "case_count": len(ids)}


def select(records):
    """Validation-only, complete-grid admission and deterministic selection."""
    need(type(records) is list and len(records) == 13, "All13 required validation results")
    expected = training_plan("nuisance", 1)[:13]
    selected, by_family = {}, {}
    for observed, plan in zip(records, expected):
        need(type(observed) is dict and set(observed) == {"family", "config_ordinal", "config", "validation_mse"},
             "Exact validation record")
        need(observed["family"] == plan["family"]
             and type(observed["config_ordinal"]) is int
             and observed["config_ordinal"] == plan["config_ordinal"]
             and encoded(observed["config"]) == encoded(plan["config"]),
             "Original complete grid and configuration order")
        loss = finite(observed["validation_mse"], "validation loss")
        need(loss >= 0, "Nonnegative validation MSE")
        by_family.setdefault(observed["family"], []).append(dict(observed, validation_mse=loss))
    for family in FAMILIES:
        selected[family] = min(by_family[family], key=lambda r: (r["validation_mse"], r["config_ordinal"]))
    strongest = min(FAMILIES, key=lambda f: (selected[f]["validation_mse"], FAMILIES.index(f)))
    return selected, strongest


def _np():
    import numpy
    return numpy


def _matrix(rows, role, counts, unit_count=None):
    np = _np()
    values = [[value for name, _ in FIELDS for value in row[name]] + [row["stimulus_latency_s"]]
              for row in rows]
    nuisance = np.asarray(values, dtype=np.float64)
    need(nuisance.shape == (len(rows), 213) and np.isfinite(nuisance).all(), "Finite213 nuisance columns")
    if role == "nuisance":
        need(counts is None and unit_count in (None, 0), "Nuisance never receives a neural operand")
        return nuisance, 0
    need(isinstance(counts, np.ndarray) and counts.ndim == 3
         and counts.shape[0] == len(rows) and counts.shape[1] == 50 and counts.shape[2] > 0
         and counts.dtype.kind == "u" and counts.dtype.itemsize == 4,
         "Complete uint32 [case,50,all-native-unit] counts")
    units = int(counts.shape[2])
    need(unit_count in (None, units), "One unchanged original unit axis")
    neural = np.log1p(counts.astype(np.float64).reshape(len(rows), 50 * units, order="C"))
    need(np.isfinite(neural).all(), "Finite lossless-input log1p reference transform")
    return np.concatenate((nuisance, neural), axis=1), units


def _normalizer(x):
    np = _np()
    with np.errstate(over="raise", invalid="raise"):
        mu, scale = x.mean(axis=0), x.std(axis=0)
    need(np.isfinite(mu).all() and np.isfinite(scale).all(), "Finite fitted-only normalizer")
    scale[scale == 0] = 1.0
    return mu, scale


def _fourier(z, width, session_ordinal):
    np = _np()
    need(type(width) is int and width in (256, 1024), "Frozen Fourier width")
    pairs = width // 2
    theta = np.zeros((len(z), pairs), dtype=np.float64)
    blocks = [("nuisance", 0, 213)]
    if z.shape[1] > 213:
        blocks.append(("neural", 213, z.shape[1]))
    for column in range(pairs):
        for block, start, stop in blocks:
            rng = np.random.Generator(np.random.PCG64(fourier_seed(session_ordinal, block, column)))
            length = stop - start
            for a in range(start, stop, 4096):
                b = min(a + 4096, stop)
                weights = rng.standard_normal(b - a)
                theta[:, column] += (z[:, a:b] @ weights) / math.sqrt(length)
    return np.concatenate((np.cos(theta), np.sin(theta)), axis=1) / math.sqrt(pairs)


def _fit(family, config, x, y, session_ordinal):
    """Concrete three-family fitting, used only inside a future sandbox."""
    np = _np()
    if family == "trees":
        from sklearn.ensemble import ExtraTreesRegressor
        estimator = ExtraTreesRegressor(n_estimators=512, criterion="squared_error", bootstrap=False,
            max_features=1.0, n_jobs=1, max_depth=config["max_depth"],
            min_samples_leaf=config["min_samples_leaf"], random_state=tree_seed(session_ordinal))
        estimator.fit(x, y)
        return {"family": family, "estimator": estimator}
    mu, scale = _normalizer(x)
    z = (x - mu) / scale
    center = y.mean(axis=0)
    if family == "linear":
        representation, divisor = z, x.shape[1]
    else:
        need(family == "fourier", "No extra reference family")
        representation, divisor = _fourier(z, config["width"], session_ordinal), 1
    kernel = representation @ representation.T / divisor
    coef = np.linalg.solve(kernel + config["alpha"] * np.eye(len(x)), y - center)
    need(np.isfinite(coef).all(), "Finite fitted reference coefficients")
    return {"family": family, "mu": mu, "scale": scale, "center": center,
            "representation": representation, "divisor": divisor, "coef": coef,
            "width": config.get("width"), "session_ordinal": session_ordinal}


def _predict(model, x):
    if model["family"] == "trees":
        return model["estimator"].predict(x)
    z = (x - model["mu"]) / model["scale"]
    representation = z if model["family"] == "linear" else _fourier(z, model["width"], model["session_ordinal"])
    return representation @ model["representation"].T / model["divisor"] @ model["coef"] + model["center"]


def _begin(journal, plan, progress):
    row = dict(plan, status="entered")
    journal.append(row)
    if progress is not None:
        progress(journal)
    return row


def _complete(row, journal, progress):
    need(row["status"] == "entered", "One completion for entered reference operation")
    row["status"] = "completed"
    if progress is not None:
        progress(journal)


def work_disposition(journal, expected=16):
    need(type(journal) is list and type(expected) is int and expected > 0,
         "Reference journal and expected work")
    completed = sum(r.get("status") == "completed" for r in journal)
    failed = sum(r.get("status") == "failed" for r in journal)
    incomplete = sum(r.get("status") == "entered" for r in journal)
    need(len(journal) == completed + failed + incomplete <= expected, "Disjoint reference work states")
    return {"expected": expected, "entered": len(journal), "completed": completed,
            "entered_failed": failed, "entered_incomplete": incomplete,
            "unentered": expected - len(journal), "last": None if not journal else dict(journal[-1])}


def fit_session(role, session_ordinal, train_rows, val_rows, train_counts=None, val_counts=None, journal=None, progress=None):
    """Select on original train/validation only; refit all three family winners."""
    identity(role, session_ordinal)
    log = [] if journal is None else journal
    need(type(log) is list and not log, "Fresh caller-owned reference journal")
    need(progress is None or callable(progress), "Trusted metadata-only progress observer")
    train_meta = row_metadata(train_rows, True)
    val_meta = row_metadata(val_rows, True, train_meta["session_id"])
    need(set(train_meta["case_ids"]).isdisjoint(val_meta["case_ids"]), "Disjoint official fitting splits")
    x_train, units = _matrix(train_rows, role, train_counts)
    x_val, _ = _matrix(val_rows, role, val_counts, units)
    np = _np()
    y_train = np.asarray([r["wheel_speed"] for r in train_rows], dtype=np.float64)
    y_val = np.asarray([r["wheel_speed"] for r in val_rows], dtype=np.float64)
    plan, records, models = training_plan(role, session_ordinal), [], {}
    current = None
    try:
        for item in plan[:13]:
            current = _begin(log, item, progress)
            model = _fit(item["family"], item["config"], x_train, y_train, session_ordinal)
            prediction = _predict(model, x_val)
            need(prediction.shape == y_val.shape and np.isfinite(prediction).all(), "Complete finite validation prediction")
            with np.errstate(over="raise", invalid="raise"):
                loss = float(np.mean((prediction - y_val) ** 2))
            need(math.isfinite(loss) and loss >= 0, "Finite validation trajectory MSE")
            records.append({"family": item["family"], "config_ordinal": item["config_ordinal"],
                            "config": dict(item["config"]), "validation_mse": loss})
            current["validation_mse"] = loss
            _complete(current, log, progress)
            del model, prediction
        selected, strongest = select(records)
        x_all = np.concatenate((x_train, x_val), axis=0)
        y_all = np.concatenate((y_train, y_val), axis=0)
        for item in plan[13:]:
            family = item["family"]
            current = _begin(log, dict(item, config=dict(selected[family]["config"])), progress)
            models[family] = _fit(family, selected[family]["config"], x_all, y_all, session_ordinal)
            _complete(current, log, progress)
        bundle = {"schema": SCHEMA, "design_sha256": DESIGN_SHA256, "role": role,
            "session_ordinal": session_ordinal, "session_id": train_meta["session_id"],
            "unit_count": units, "fit_case_ids": train_meta["case_ids"] + val_meta["case_ids"],
            "models": models, "selected": selected, "strongest_family": strongest}
        report = {"schema": SCHEMA + "/selection", "design_sha256": DESIGN_SHA256,
            "role": role, "session_ordinal": session_ordinal, "session_id": train_meta["session_id"],
            "unit_count": units, "train_cases": train_meta["case_count"], "validation_cases": val_meta["case_count"],
            "validation": records, "selected": selected, "strongest_family": strongest,
            "tree_seed": tree_seed(session_ordinal), "fourier_seed_rule": "design-v2-per-session-block-column",
            "training_shift": 0, "test_exposed": False, "work": work_disposition(log),
            "reference_competence_qualified": False}
        return bundle, report
    except BaseException as error:
        if log and log[-1]["status"] == "entered":
            log[-1]["status"] = "failed"
            log[-1]["error_type"] = type(error).__name__
        raise


def bundle_metadata(bundle):
    need(type(bundle) is dict and set(bundle) == {"schema", "design_sha256", "role", "session_ordinal", "session_id",
         "unit_count", "fit_case_ids", "models", "selected", "strongest_family"}, "Exact sealed reference bundle")
    need(bundle["schema"] == SCHEMA and bundle["design_sha256"] == DESIGN_SHA256, "Exact reference design identity")
    identity(bundle["role"], bundle["session_ordinal"])
    need(type(bundle["session_id"]) is str and ID.fullmatch(bundle["session_id"]), "Sealed original session identity")
    units = bundle["unit_count"]
    need(type(units) is int and (units == 0 if bundle["role"] == "nuisance" else units > 0), "Sealed original unit count")
    ids = bundle["fit_case_ids"]
    need(type(ids) is list and len(ids) > 1 and len(set(ids)) == len(ids)
         and all(type(x) is str and ID.fullmatch(x) for x in ids), "Sealed fitting identities")
    need(type(bundle["models"]) is dict and set(bundle["models"]) == set(FAMILIES)
         and type(bundle["selected"]) is dict and set(bundle["selected"]) == set(FAMILIES)
         and bundle["strongest_family"] in FAMILIES, "All three sealed family winners")
    for f in FAMILIES:
        record = bundle["selected"][f]
        need(type(record) is dict and record.get("family") == f and type(record.get("config_ordinal")) is int,
             "Exact selected family identity")
        grid = configurations()[f]
        i = record["config_ordinal"]
        need(0 <= i < len(grid) and encoded(record.get("config")) == encoded(grid[i]), "Selected fixed grid member")
        need(finite(record.get("validation_mse"), "sealed validation loss") >= 0, "Valid sealed selection loss")
        need(type(bundle["models"][f]) is dict and bundle["models"][f].get("family") == f, "Model family join")
    strongest = min(FAMILIES, key=lambda f: (bundle["selected"][f]["validation_mse"], FAMILIES.index(f)))
    need(bundle["strongest_family"] == strongest, "Strongest family remains validation-selected")


def predict_session(bundle, test_rows, test_counts=None, journal=None, progress=None):
    """Prediction only: no labels, fitting, arm flag, source mutation or test selection."""
    bundle_metadata(bundle)
    log = [] if journal is None else journal
    need(type(log) is list and not log, "Fresh prediction journal")
    need(progress is None or callable(progress), "Trusted metadata-only prediction observer")
    meta = row_metadata(test_rows, False, bundle["session_id"])
    need(set(meta["case_ids"]).isdisjoint(bundle["fit_case_ids"]), "No fitting case presented as test")
    x, _ = _matrix(test_rows, bundle["role"], test_counts, bundle["unit_count"])
    np = _np()
    result = {}
    try:
        for family in FAMILIES:
            current = _begin(log, {"phase": "inference", "family": family}, progress)
            prediction = _predict(bundle["models"][family], x)
            need(prediction.shape == (len(test_rows), 50) and np.isfinite(prediction).all(),
                 "Every test row has50 finite predictions in every family")
            result[family] = prediction.tolist()
            _complete(current, log, progress)
    except BaseException as error:
        if log and log[-1]["status"] == "entered":
            log[-1]["status"] = "failed"
            log[-1]["error_type"] = type(error).__name__
        raise
    return result, {"schema": SCHEMA + "/inference", "design_sha256": DESIGN_SHA256,
        "role": bundle["role"], "session_ordinal": bundle["session_ordinal"], "session_id": bundle["session_id"],
        "case_ids": meta["case_ids"], "strongest_family": bundle["strongest_family"],
        "selected": bundle["selected"], "fits_during_inference": 0,
        "work": work_disposition(log, 3),
        "reference_competence_qualified": False}
