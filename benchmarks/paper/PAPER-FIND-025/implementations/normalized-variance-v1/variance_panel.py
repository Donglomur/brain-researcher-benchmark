"""Source-scoped matrix arithmetic, not paper reproduction or data preparation.

The operator supplies independently adjudicated covariances and rank/support
identities. A candidate supplies bases only. No fitting, file loading, MATLAB
execution, source repair, label access or claim of provenance occurs here.
"""
from hashlib import sha256
import json
from math import isfinite

import numpy as np

SOURCE_COMMIT = "0038351ee773c2aee8758b3d74b0c9bf2991f543"
MAX_UNITS = 1024
MAX_PAYLOAD_BYTES = 4 * 1024 * 1024
MAX_ABS_VALUE = 1e100
# These are roundoff checks on matrix validity, not reproduction tolerances.
ROUNDOFF_FACTOR = 128
EPOCHS = ("stationary", "moving", "delay", "response")
# Output, submitted basis, operator covariance, *denominator* rank.
# The two cross-epoch entries deliberately do not use the basis rank.
BRANCHES = (
    ("null_prep", "null", "stationary", "d_prep"),
    ("null_move", "null", "moving", "d_prep"),
    ("potent_move", "potent", "moving", "d_move"),
    ("potent_prep", "potent", "stationary", "d_move"),
    ("null_delay", "null", "delay", "d_prep"),
    ("null_resp", "null", "response", "d_move"),
    ("potent_delay", "potent", "delay", "d_prep"),
    ("potent_resp", "potent", "response", "d_move"),
)


class OperatorError(ValueError):
    """Invalid operator operands: reject the complete panel."""


class CandidateError(ValueError):
    """Invalid submitted basis artifact: reject the complete artifact."""


def _exact(value, fields, error, name):
    if type(value) is not dict or set(value) != set(fields):
        raise error(name + ": exact fields required")


def _text(value, error, name):
    if type(value) is not str or not 0 < len(value) <= 512 or value.strip() != value:
        raise error(name + ": nonempty bounded text required")


def _units(value, error):
    if type(value) is not list or not 0 < len(value) <= MAX_UNITS:
        raise error("complete bounded unit list required; never truncate support")
    for item in value:
        _text(item, error, "unit ID")
    if len(set(value)) != len(value):
        raise error("unit IDs must be unique and ordered")


def _matrix(value, rows, columns, error, name):
    if type(value) is not list or len(value) != rows:
        raise error(name + ": complete row dimension required")
    for row in value:
        if type(row) is not list or len(row) != columns:
            raise error(name + ": complete column dimension required")
        if any(type(x) not in (int, float) or abs(x) > MAX_ABS_VALUE or
               not isfinite(x) for x in row):
            raise error(name + ": finite bounded real numbers required")
    return np.asarray(value, dtype=np.float64)


def _operator(value):
    _exact(value, ("schema", "source_commit", "unit_ids", "d_prep", "d_move",
                   "covariances", "support_ids", "preparation_id"),
           OperatorError, "operator")
    if value["schema"] != "find025_covariance_operands_v1" or value["source_commit"] != SOURCE_COMMIT:
        raise OperatorError("operator schema or released-code identity differs")
    _units(value["unit_ids"], OperatorError)
    _text(value["preparation_id"], OperatorError, "preparation ID")
    n = len(value["unit_ids"])
    for field in ("d_prep", "d_move"):
        rank = value[field]
        if type(rank) is not int or not 1 <= rank <= n:
            raise OperatorError("each supplied source rank must be an integer in [1,n]")
    if value["d_prep"] + value["d_move"] > n:
        raise OperatorError("orthogonal basis dimensions exceed the common unit space")
    _exact(value["covariances"], EPOCHS, OperatorError, "covariances")
    _exact(value["support_ids"], EPOCHS, OperatorError, "support IDs")
    matrices, spectra = {}, {}
    for epoch in EPOCHS:
        _text(value["support_ids"][epoch], OperatorError, epoch + " support ID")
        matrix = _matrix(value["covariances"][epoch], n, n, OperatorError, epoch)
        # Do not average, repair or otherwise change an operator covariance.
        if not np.array_equal(matrix, matrix.T):
            raise OperatorError(epoch + ": exactly symmetric covariance required")
        try:
            spectrum = np.linalg.eigvalsh(matrix)[::-1]
        except np.linalg.LinAlgError as exc:
            raise OperatorError(epoch + ": eigensolver failed") from exc
        if not np.isfinite(spectrum).all():
            raise OperatorError(epoch + ": nonfinite covariance spectrum")
        scale = float(np.max(np.abs(spectrum)))
        tolerance = ROUNDOFF_FACTOR * n * np.finfo(np.float64).eps * scale
        if float(spectrum[-1]) < -tolerance:
            raise OperatorError(epoch + ": covariance is materially indefinite")
        # Roundoff-sized eigenvalues are retained, never clipped or discarded.
        matrices[epoch], spectra[epoch] = matrix, spectrum
    return matrices, spectra


def _unique(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise CandidateError("duplicate JSON key")
        obj[key] = value
    return obj


def _nonfinite(_):
    raise CandidateError("nonfinite JSON constant")


def _candidate(body, expected_sha256, operator):
    if type(body) is not bytes or len(body) > MAX_PAYLOAD_BYTES:
        raise CandidateError("bounded byte artifact required; never truncate support")
    if (type(expected_sha256) is not str or len(expected_sha256) != 64 or
            any(x not in "0123456789abcdef" for x in expected_sha256)):
        raise OperatorError("operator must supply an exact lowercase SHA256")
    if sha256(body).hexdigest() != expected_sha256:
        raise CandidateError("candidate artifact SHA256 differs")
    try:
        value = json.loads(body.decode("utf-8"), object_pairs_hook=_unique,
                           parse_constant=_nonfinite)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise CandidateError("invalid strict UTF8 JSON basis artifact") from exc
    _exact(value, ("schema", "unit_ids", "null_basis", "potent_basis"),
           CandidateError, "candidate")
    if value["schema"] != "find025_subspace_bases_v1":
        raise CandidateError("candidate basis schema differs")
    _units(value["unit_ids"], CandidateError)
    if value["unit_ids"] != operator["unit_ids"]:
        raise CandidateError("candidate unit IDs/order differ from operator support")
    n = len(operator["unit_ids"])
    null = _matrix(value["null_basis"], n, operator["d_prep"], CandidateError, "null basis")
    potent = _matrix(value["potent_basis"], n, operator["d_move"], CandidateError, "potent basis")
    # Joint orthonormality verifies each basis and their mutual orthogonality.
    joined = np.concatenate((null, potent), axis=1)
    gram = joined.T @ joined
    tolerance = ROUNDOFF_FACTOR * n * np.finfo(np.float64).eps
    if (not np.isfinite(gram).all() or
            float(np.max(np.abs(gram - np.eye(gram.shape[0])))) > tolerance):
        raise CandidateError("candidate bases are not jointly orthonormal")
    return {"null": null, "potent": potent}


def evaluate_panel(operator, candidate_body, expected_sha256):
    """Compute all eight ratios on common operator covariances, without fitting.

    Caller must independently establish authentic preparation, support, source
    dispatch and rank selection. Returned operands are operator-only evidence,
    not safe participant feedback or a protected target-isolation boundary.
    """
    matrices, spectra = _operator(operator)
    bases = _candidate(candidate_body, expected_sha256, operator)
    results = []
    for name, basis_name, epoch, rank_field in BRANCHES:
        q, matrix = bases[basis_name], matrices[epoch]
        count = operator[rank_field]
        numerator = float(np.sum(q * (matrix @ q), dtype=np.float64))
        denominator = float(np.sum(spectra[epoch][:count], dtype=np.float64))
        value, reason = None, None
        if not isfinite(numerator) or not isfinite(denominator):
            reason = "nonfinite_matrix_arithmetic"
        elif denominator <= 0:
            reason = "nonpositive_normalizing_variance"
        elif numerator < 0:
            reason = "negative_projected_variance"
        else:
            value = numerator / denominator
            if not isfinite(value):
                value, reason = None, "nonfinite_ratio"
        results.append({"output": name, "epoch": epoch, "basis": basis_name,
                        "denominator_rank": count, "status": "undefined" if reason else "computed",
                        "numerator": numerator if isfinite(numerator) else None,
                        "denominator": denominator if isfinite(denominator) else None,
                        "value": value, "reason": reason})
    return {"schema": "find025_normalized_variance_panel_v1", "results": results,
            "candidate_sha256": expected_sha256, "source_commit": SOURCE_COMMIT,
            "scope": "arithmetic_on_operator_adjudicated_covariances_only",
            "authentic_preparation_verified": False, "paper_pass": None,
            "scientifically_qualified": False, "readiness_promoted": False}
