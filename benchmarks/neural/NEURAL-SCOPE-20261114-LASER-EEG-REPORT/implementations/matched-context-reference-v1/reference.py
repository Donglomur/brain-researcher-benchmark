"""Fixed ten-example context reference for the registered laser EEG assay.

Only the projected context and ten labeled ratings enter the fit. The upstream
packet producer remains responsible for authentic complete EEG preparation.
No target loader, source-bank access, tuning, persistent fit, or model API.
"""
import hashlib
import json
import math
import re
import statistics

TASK_ID = "NEURAL-SCOPE-20261114-LASER-EEG-REPORT"
REFERENCE_ID = "lep-ten-example-energy-context-ridge-v1"
LAMBDA = 1.0
MAX_PACKET_BYTES = 384 * 1024 * 1024
_CASE_FIELDS = {
    "id", "channels", "coordinate_system", "samples_001uv", "valid_mask",
    "context", "delivered_energy_j", "stimulated_side", "calibration_category",
    "quantization",
}
_CATEGORIES = ("stimulated_side", "calibration_category", "device", "reference",
               "rating_protocol")


class ContractError(ValueError):
    pass


def _need(ok, message):
    if not ok:
        raise ContractError(message)


def _exact(value, fields, name):
    _need(type(value) is dict and set(value) == set(fields), name + ": exact fields")


def _pin(value):
    _need(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value), "SHA-256 required")
    return value


def _id(value):
    _need(type(value) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value),
          "opaque packet identity required")
    return value


def _number(value, *, lower=None, upper=None):
    _need(type(value) in (int, float), "finite numeric operand required; Boolean refused")
    try:
        value = float(value)
    except (ValueError, OverflowError):
        raise ContractError("numeric range refused") from None
    _need(math.isfinite(value), "finite numeric operand required")
    _need(lower is None or value >= lower, "numeric operand below domain")
    _need(upper is None or value <= upper, "numeric operand above domain")
    return value


def _text(value, maximum):
    _need(type(value) is str and 0 < len(value) <= maximum, "context text required")
    return value


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _decode(raw):
    _need(type(raw) is bytes and len(raw) <= MAX_PACKET_BYTES,
          "complete byte packet required; never truncate")
    def unique(items):
        result = {}
        for key, value in items:
            _need(key not in result, "duplicate JSON field")
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=unique,
                          parse_constant=lambda _: _need(False, "nonfinite JSON literal"))
    except (ValueError, UnicodeError, RecursionError) as error:
        raise ContractError("invalid packet JSON") from error


def _context(case, *, labeled):
    _exact(case, _CASE_FIELDS | ({"rating"} if labeled else set()), "labeled case" if labeled else "query")
    _id(case["id"])
    _exact(case["context"], ("device", "reference", "rating_protocol"), "context")
    context = case["context"]
    _need(context["device"] in ("BioSemi", "ANT", "BrainProducts"), "known device")
    result = {"device": context["device"],
              "reference": _text(context["reference"], 256),
              "rating_protocol": _text(context["rating_protocol"], 2048),
              "stimulated_side": _text(case["stimulated_side"], 128)}
    energy = case["delivered_energy_j"]
    category = case["calibration_category"]
    result["energy"] = None if energy is None else _number(energy, lower=0)
    # A documented rating-calibration category is categorical context, never Joules.
    result["calibration_category"] = None if category is None else _number(category, lower=0, upper=10)
    rating = _number(case["rating"], lower=0, upper=10) if labeled else None
    return result, rating


def _project(raw, expected_packet_sha256, protocol_sha256, representation_sha256):
    for value in (expected_packet_sha256, protocol_sha256, representation_sha256):
        _pin(value)
    _need(type(raw) is bytes and hashlib.sha256(raw).hexdigest() == expected_packet_sha256,
          "packet differs from independently frozen owner manifest")
    doc = _decode(raw)
    _exact(doc, ("schema", "task_id", "fold_id", "protocol_sha256", "representation_sha256",
                 "documentation", "signal_grid", "training_support", "calibration", "query"), "packet")
    _need(doc["schema"] == "lep-query-packet-v1" and doc["task_id"] == TASK_ID, "query packet identity")
    _id(doc["fold_id"])
    _need(doc["protocol_sha256"] == protocol_sha256
          and doc["representation_sha256"] == representation_sha256, "frozen policy identity")
    _need(type(doc["training_support"]) is list and len(doc["training_support"]) == 8,
          "exactly eight training supports")
    _need(type(doc["calibration"]) is list and len(doc["calibration"]) == 2,
          "exactly two chronological calibration cases")
    labeled = doc["training_support"] + doc["calibration"]
    projected = [_context(case, labeled=True) for case in labeled]
    query, _ = _context(doc["query"], labeled=False)
    ids = [case["id"] for case in labeled] + [doc["query"]["id"]]
    _need(len(set(ids)) == 11, "support/calibration/query identities must be distinct")
    # Neural arrays, coordinates, masks, documentation and grid are deliberately
    # not projected. Their source validity belongs to the pinned packet producer.
    return doc, [item[0] for item in projected], [item[1] for item in projected], query


def _design(contexts, query):
    """Fit feature vocabulary, imputation and population scales on ten rows only."""
    observed = [row["energy"] for row in contexts if row["energy"] is not None]
    energy_mean = math.fsum(value / len(observed) for value in observed) if observed else 0.0
    vocab = {field: sorted({row[field] for row in contexts if row[field] is not None})
             for field in _CATEGORIES}
    names = ["delivered_energy_j", "delivered_energy_missing"]
    for field in _CATEGORIES:
        names.extend(field + ":" + repr(value) for value in vocab[field])
        names.extend((field + ":missing", field + ":unseen"))

    def row_values(row):
        # With no observed training energy there is no identifiable energy slope.
        energy = row["energy"] if observed and row["energy"] is not None else energy_mean
        values = [energy, float(row["energy"] is None)]
        for field in _CATEGORIES:
            value = row[field]
            values.extend(float(value == category) for category in vocab[field])
            values.extend((float(value is None), float(value is not None and value not in vocab[field])))
        return values

    x = [row_values(row) for row in contexts]
    q = row_values(query)
    means = [math.fsum(row[j] / 10 for row in x) for j in range(len(names))]
    scales = []
    for j, mean in enumerate(means):
        std = math.hypot(*(row[j] - mean for row in x)) / math.sqrt(10)
        scales.append(std if std > 0 else 1.0)
    _need(all(math.isfinite(value) for value in means + scales), "fit statistics exceed finite numeric range")
    z = [[(value - mean) / scale for value, mean, scale in zip(row, means, scales)] for row in x]
    zq = [(value - mean) / scale for value, mean, scale in zip(q, means, scales)]
    _need(all(math.isfinite(value) for row in z + [zq] for value in row), "design exceeds finite numeric range")
    return z, zq, {"feature_names": names, "feature_means": means, "feature_scales": scales,
                   "energy_imputation_j": energy_mean if observed else None,
                   "training_observed_energy": len(observed), "training_examples": 10,
                   "category_vocabulary": vocab}


def _solve_positive_definite(matrix, rhs):
    """Cholesky solve; ridge makes this ten-by-ten dual system positive definite."""
    n = len(rhs)
    lower = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            residual = matrix[i][j] - math.fsum(lower[i][k] * lower[j][k] for k in range(j))
            if i == j:
                _need(math.isfinite(residual) and residual > 0, "ridge system is numerically invalid")
                lower[i][j] = math.sqrt(residual)
            else:
                lower[i][j] = residual / lower[j][j]
    intermediate, solution = [0.0] * n, [0.0] * n
    for i in range(n):
        intermediate[i] = (rhs[i] - math.fsum(lower[i][j] * intermediate[j] for j in range(i))) / lower[i][i]
    for i in reversed(range(n)):
        solution[i] = (intermediate[i] - math.fsum(lower[j][i] * solution[j] for j in range(i + 1, n))) / lower[i][i]
    return solution


def predict_packet(raw, *, expected_packet_sha256, protocol_sha256, representation_sha256):
    """Return a context-only prediction and owner-private, target-free fit audit.

    Expected hashes must come from the owner, never from a candidate. No fitted
    object is retained across calls. This is a fixed reference, not an executor.
    """
    doc, contexts, ratings, query = _project(raw, expected_packet_sha256, protocol_sha256,
                                           representation_sha256)
    try:
        z, zq, fit = _design(contexts, query)
        center = math.fsum(ratings) / 10
        gram = [[math.fsum(a * b for a, b in zip(z[i], z[j])) + (LAMBDA if i == j else 0.0)
                 for j in range(10)] for i in range(10)]
        dual = _solve_positive_definite(gram, [rating - center for rating in ratings])
        beta = [math.fsum(z[i][j] * dual[i] for i in range(10)) for j in range(len(zq))]
        estimate = center + math.fsum(a * b for a, b in zip(zq, beta))
        _need(math.isfinite(estimate), "ridge prediction exceeds finite numeric range")
    except (OverflowError, ZeroDivisionError) as error:
        raise ContractError("numerical reference refused; never substitute a favorable fallback") from error
    # Fixed projection of predictions, not targets. It cannot increase absolute
    # error against any target in the registered [0,10] domain.
    bounded = min(10.0, max(0.0, estimate))
    return {"prediction": {"query_id": doc["query"]["id"], "median": bounded},
            "support_calibration_median": statistics.median(ratings),
            "calibration_median": statistics.median(ratings[-2:]),
            "audit": {"reference_id": REFERENCE_ID, "packet_sha256": expected_packet_sha256,
                      "fold_id": doc["fold_id"], "lambda": LAMBDA, "fit": fit,
                      "training_support_sha256": hashlib.sha256(encode(doc["training_support"])).hexdigest(),
                      "unbounded_prediction": estimate, "prediction_projected": estimate != bounded,
                      "query_energy_observed": query["energy"] is not None,
                      "all_eleven_energies_observed": all(row["energy"] is not None for row in contexts + [query]),
                      "query_unseen_categories": [field for field in _CATEGORIES
                           if query[field] is not None and query[field] not in fit["category_vocabulary"][field]]}}


def build_comparator(packet_bodies, *, packet_sha256_by_id, protocol_sha256,
                     representation_sha256, selection_receipt_sha256):
    """Build the existing scorer's trusted comparator from every frozen packet.

    packet_bodies yields (opaque_query_id, raw_bytes). The owner's expected map
    comes from complete packet preparation, not candidate output. Missing, extra,
    duplicate or changed packets abort. No target/rating ledger is accepted here.
    Complete assay coverage is subsequently checked by the retained scorer.
    """
    for value in (protocol_sha256, representation_sha256, selection_receipt_sha256):
        _pin(value)
    _need(type(packet_sha256_by_id) is dict and len(packet_sha256_by_id) >= 678,
          "full assay manifest needs at least one query per 678 nominal people")
    expected = dict(packet_sha256_by_id)
    for query_id, digest in expected.items():
        _id(query_id)
        _pin(digest)
    results, folds = {}, {}
    missing_energy, projected_count = 0, 0
    for item in packet_bodies:
        _need(type(item) in (tuple, list) and len(item) == 2, "(query ID, packet bytes) required")
        query_id, raw = item
        _id(query_id)
        _need(query_id in expected and query_id not in results, "unknown or duplicate query packet")
        result = predict_packet(raw, expected_packet_sha256=expected[query_id],
                                protocol_sha256=protocol_sha256, representation_sha256=representation_sha256)
        _need(result["prediction"]["query_id"] == query_id, "manifest/query identity mismatch")
        # The eight training support cases must stay identical within an outer fold.
        support_hash = result["audit"]["training_support_sha256"]
        fold = result["audit"]["fold_id"]
        _need(fold not in folds or folds[fold] == support_hash, "training supports changed within fold")
        folds[fold] = support_hash
        results[query_id] = {"prediction": result["prediction"],
                             "support_calibration_median": result["support_calibration_median"],
                             "calibration_median": result["calibration_median"]}
        missing_energy += not result["audit"]["all_eleven_energies_observed"]
        projected_count += result["audit"]["prediction_projected"]
    _need(set(results) == set(expected), "incomplete packet stream; no comparator produced")
    _need(len(folds) == 9, "complete nine-fold reference required")
    envelope = {"schema": "lep-predictions-v1", "task_id": TASK_ID,
                "protocol_sha256": protocol_sha256, "representation_sha256": representation_sha256,
                "predictions": [results[key]["prediction"] for key in sorted(results)]}
    comparator = {"schema": "lep-comparator-v1", "reference_id": REFERENCE_ID,
                  "information": "energy_context_only", "selection_receipt_sha256": selection_receipt_sha256,
                  "prediction": envelope}
    controls = {name: {**envelope, "predictions": [{"query_id": key, "median": results[key][name]}
                 for key in sorted(results)]} for name in ("support_calibration_median", "calibration_median")}
    receipt = {"schema": "lep-matched-context-reference-receipt-v1", "task_id": TASK_ID,
               "reference_id": REFERENCE_ID, "protocol_sha256": protocol_sha256,
               "representation_sha256": representation_sha256,
               "selection_receipt_sha256": selection_receipt_sha256,
               "packet_manifest_sha256": hashlib.sha256(encode(expected)).hexdigest(),
               "comparator_sha256": hashlib.sha256(encode(comparator)).hexdigest(),
               "query_packets": len(results), "folds": 9,
               "queries_with_any_missing_energy": missing_energy,
               "projected_predictions": projected_count,
               "qualification": "software_reference_only; authentic competence and neural increment unestablished"}
    return comparator, controls, receipt
