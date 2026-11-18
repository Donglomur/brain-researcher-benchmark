"""Precommittable NEURAL-069 reference; generated source is self-contained.

The existing programme entry passes only --public-root and --output-dir, and
the output is an existing empty mounted volume. This harness supports exactly
that interface. Embedded numerical sources are unchanged prepared baseline code.
No scoring, private target access, tuning, or source acquisition occurs here.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import types

import numpy as np

BASELINE_METHOD = 'training_mean'
IO_SOURCE = '"""Bounded inert prediction I/O shared by NEURAL-069/070.\n\nThe caller authenticates the public roster/task manifest and supplies its exact\nordered ID -> (102, V) mapping. This module never opens targets or runs a model.\nOnly after validate_prediction_files returns may the caller load private arrays.\nAll size/digest evidence describes captured bytes, never a later reread.\n"""\nfrom __future__ import annotations\n\nimport ast\nimport hashlib\nimport json\nimport math\nimport os\nfrom pathlib import Path\nimport re\nimport stat\n\nimport numpy as np\n\nMAX_HEADER = 16384\nMAX_JSON = 4 * 1024 * 1024\n_SHA = re.compile(r"[a-f0-9]{64}")\n_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,159}\\.npy")\n\n\nclass IOContractError(ValueError):\n    """Candidate bytes do not satisfy the declared inert-file contract."""\n\n\ndef _need(ok, message):\n    if not ok:\n        raise IOContractError(message)\n\n\ndef _positive_int(value, name):\n    _need(type(value) is int and value > 0, name + " must be a positive integer")\n\n\ndef prediction_name(value):\n    """One ordinary basename; absolute, nested and rerooted paths are forbidden."""\n    _need(type(value) is str and _NAME.fullmatch(value) is not None\n          and ".." not in value, "prediction path must be a safe .npy basename")\n    return value\n\n\ndef _capture(path, max_bytes, *, dir_fd=None):\n    _positive_int(max_bytes, "max_bytes")\n    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=dir_fd)\n    try:\n        before = os.fstat(fd)\n        _need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1\n              and 0 < before.st_size <= max_bytes, "bounded ordinary single-link file required")\n        parts = []\n        remaining = before.st_size + 1\n        while remaining:\n            part = os.read(fd, min(1024 * 1024, remaining))\n            if not part:\n                break\n            parts.append(part)\n            remaining -= len(part)\n        raw = b"".join(parts)\n        after = os.fstat(fd)\n        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink")\n        _need(len(raw) == before.st_size and all(getattr(before, k) == getattr(after, k) for k in fields),\n              "file changed during same-descriptor capture")\n        return raw, hashlib.sha256(raw).hexdigest()\n    finally:\n        os.close(fd)\n\n\ndef capture_regular(path, max_bytes):\n    """Return (bytes, sha256); refuse symlink leaves, devices, FIFOs and growth."""\n    return _capture(path, max_bytes)\n\n\ndef strict_json(raw, *, max_bytes=MAX_JSON, max_depth=32, max_integer_digits=128):\n    """UTF-8 JSON with duplicate, nonfinite, nesting and integer-size guards."""\n    for value, name in ((max_bytes, "max_bytes"), (max_depth, "max_depth"),\n                        (max_integer_digits, "max_integer_digits")):\n        _positive_int(value, name)\n    _need(type(raw) is bytes and 0 < len(raw) <= max_bytes, "bounded JSON bytes required")\n    try:\n        text = raw.decode("utf-8")\n    except UnicodeError as error:\n        raise IOContractError("JSON must be UTF-8") from error\n    depth = 0\n    quoted = escaped = False\n    for character in text:\n        if quoted:\n            if escaped:\n                escaped = False\n            elif character == "\\\\":\n                escaped = True\n            elif character == \'"\':\n                quoted = False\n        elif character == \'"\':\n            quoted = True\n        elif character in "[{":\n            depth += 1\n            _need(depth <= max_depth, "JSON nesting exceeds contract")\n        elif character in "]}":\n            depth -= 1\n    def pairs(items):\n        result = {}\n        for key, value in items:\n            _need(key not in result, "duplicate JSON key")\n            result[key] = value\n        return result\n    def integer(token):\n        _need(len(token.lstrip("-")) <= max_integer_digits, "JSON integer exceeds digit limit")\n        return int(token)\n    def floating(token):\n        value = float(token)\n        _need(math.isfinite(value), "nonfinite JSON number")\n        return value\n    def constant(_):\n        raise IOContractError("nonfinite JSON constant")\n    try:\n        return json.loads(text, object_pairs_hook=pairs, parse_int=integer,\n                          parse_float=floating, parse_constant=constant)\n    except (json.JSONDecodeError, RecursionError) as error:\n        raise IOContractError("malformed JSON") from error\n\n\ndef _shape(value, *, expected_rows=102):\n    _positive_int(expected_rows, "expected_rows")\n    _need(type(value) in (tuple, list) and len(value) == 2\n          and all(type(x) is int and x > 0 for x in value) and value[0] == expected_rows,\n          "array shape must match the fixed expected row count and positive columns")\n    return tuple(value)\n\n\ndef parse_npy(raw, expected_shape, *, expected_rows=102):\n    """Validate header/extent before frombuffer; return a read-only float array.\n\n    Only uncompressed NPY 1/2/3, C order, primitive 32/64-bit IEEE floats are\n    accepted. Endianness is preserved. Object/structured dtypes and pickle are\n    never deserialized. There is no clipping, normalization or missing-value fix.\n    """\n    expected_shape = _shape(expected_shape, expected_rows=expected_rows)\n    _need(type(raw) is bytes and len(raw) >= 10 and raw[:6] == b"\\x93NUMPY", "ordinary NPY bytes required")\n    version = tuple(raw[6:8])\n    _need(version in ((1, 0), (2, 0), (3, 0)), "unsupported NPY version")\n    start = 10 if version == (1, 0) else 12\n    _need(len(raw) >= start, "truncated NPY prefix")\n    header_size = int.from_bytes(raw[8:start], "little")\n    _need(0 < header_size <= MAX_HEADER and start + header_size <= len(raw), "bounded complete NPY header required")\n    header_bytes = raw[start:start + header_size]\n    _need(header_bytes.endswith(b"\\n"), "NPY header newline required")\n    try:\n        header = ast.literal_eval(header_bytes.decode("utf-8" if version == (3, 0) else "latin1").strip())\n    except (SyntaxError, ValueError, UnicodeError, RecursionError, MemoryError) as error:\n        raise IOContractError("malformed primitive NPY header") from error\n    _need(type(header) is dict and set(header) == {"descr", "fortran_order", "shape"}, "exact NPY header fields required")\n    _need(header["fortran_order"] is False, "prediction must use C order")\n    _need(type(header["shape"]) is tuple and header["shape"] == expected_shape\n          and all(type(x) is int for x in header["shape"]), "NPY shape differs from public roster")\n    _need(type(header["descr"]) is str and header["descr"] in\n          ("<f4", ">f4", "=f4", "<f8", ">f8", "=f8"), "only primitive float32/float64 predictions allowed")\n    dtype = np.dtype(header["descr"])\n    offset = start + header_size\n    count = expected_shape[0] * expected_shape[1]\n    _need(len(raw) == offset + count * dtype.itemsize, "NPY data extent differs from exact shape/dtype")\n    array = np.frombuffer(raw, dtype=dtype, count=count, offset=offset).reshape(expected_shape)\n    _need(bool(np.isfinite(array).all()), "every prediction must be finite")\n    return array\n\n\ndef validate_prediction_files(root, records, expected_shapes, *, max_total_bytes):\n    """Admit the complete ordered panel before returning any captured arrays.\n\n    records: [{id, path, bytes, sha256}, ...], exact keys and expected ID order.\n    expected_shapes: insertion-ordered dict from the authenticated public roster.\n    The application validates that roster\'s full 80-case biological support.\n    Return {arrays: ID->read-only ndarray, files: captured descriptors} only after\n    every record succeeds. No private target callback is part of this function.\n    """\n    _positive_int(max_total_bytes, "max_total_bytes")\n    _need(type(expected_shapes) is dict and bool(expected_shapes), "nonempty authenticated public shape mapping required")\n    expected = list(expected_shapes)\n    _need(all(type(k) is str and 0 < len(k) <= 160 for k in expected), "ordinary public case IDs required")\n    shapes = {key: _shape(value) for key, value in expected_shapes.items()}\n    _need(type(records) is list and len(records) == len(expected), "complete prediction file roster required")\n    names = set()\n    total = 0\n    for record, key in zip(records, expected):\n        _need(type(record) is dict and set(record) == {"id", "path", "bytes", "sha256"}\n              and record["id"] == key, "exact prediction record fields and public case order required")\n        name = prediction_name(record["path"])\n        _need(name not in names, "duplicate prediction filename")\n        names.add(name)\n        size = record["bytes"]\n        _positive_int(size, "prediction bytes")\n        _need(size <= 8 * shapes[key][0] * shapes[key][1] + MAX_HEADER + 12, "declared NPY size exceeds public shape cap")\n        _need(type(record["sha256"]) is str and _SHA.fullmatch(record["sha256"]) is not None, "exact lowercase SHA256 required")\n        total += size\n        _need(total <= max_total_bytes, "complete prediction panel exceeds byte budget")\n    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)\n    try:\n        _need(stat.S_ISDIR(os.fstat(root_fd).st_mode), "ordinary candidate directory required")\n        arrays, pins = {}, []\n        for record in records:\n            raw, digest = _capture(record["path"], record["bytes"], dir_fd=root_fd)\n            _need(len(raw) == record["bytes"] and digest == record["sha256"], "captured prediction pin mismatch")\n            arrays[record["id"]] = parse_npy(raw, shapes[record["id"]])\n            pins.append({"id": record["id"], "path": record["path"], "bytes": len(raw), "sha256": digest})\n        return {"arrays": arrays, "files": pins}\n    finally:\n        os.close(root_fd)\n\n\ndef write_json_exclusive(path, value, *, max_bytes=MAX_JSON):\n    """Write fresh bounded JSON; never follow or overwrite an existing leaf."""\n    _positive_int(max_bytes, "max_bytes")\n    try:\n        raw = (json.dumps(value, allow_nan=False, sort_keys=True, indent=2) + "\\n").encode("utf-8")\n    except (ValueError, TypeError, RecursionError) as error:\n        raise IOContractError("output is not finite JSON") from error\n    _need(len(raw) <= max_bytes, "JSON output exceeds byte budget")\n    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)\n    try:\n        _need(stat.S_ISREG(os.fstat(fd).st_mode), "ordinary output required")\n        view = memoryview(raw)\n        while view:\n            count = os.write(fd, view)\n            _need(count > 0, "short output write")\n            view = view[count:]\n        os.fsync(fd)\n    finally:\n        os.close(fd)\n    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}\n'
READOUT_SOURCE = '"""Fixed prospective readout shared by NEURAL069/070; no data or model I/O.\n\nProduction inputs have 1000 training videos, 102 query videos and exactly 100\nfeature columns. Standardization is fitted on training features only (SD ddof=0);\ntraining-constant columns are zero in BOTH partitions. Ridge lambda is exactly\none and the intercept is unpenalized. Response inputs are training repeat means.\nNo cross-validation, feature selection, PCA, or outcome tuning occurs here.\n\nThis is a new benchmark readout, not the published PCA/OLS implementation.\nCaller must bind video order, response provenance and immutable comparator\nfeatures; dimensions alone do not establish equal representation capacity.\n"""\nfrom __future__ import annotations\n\nfrom fractions import Fraction\nimport math\n\nimport numpy as np\n\nRIDGE_LAMBDA = 1.0\nTRAIN_VIDEOS = 1000\nQUERY_VIDEOS = 102\nFEATURES = 100\n\n\nclass ReadoutInputError(ValueError):\n    """Invalid shapes, types or nonfinite float64 inputs."""\n\n\nclass ReadoutNumericalError(ArithmeticError):\n    """Valid inputs whose required arithmetic/output is unrepresentable."""\n\n\ndef _array(value, ndim, name):\n    try:\n        a = np.asarray(value)\n    except (TypeError, ValueError, OverflowError) as exc:\n        raise ReadoutInputError(f"{name}: numeric array required") from exc\n    if a.ndim != ndim or a.dtype.kind not in "fiu":\n        raise ReadoutInputError(f"{name}: real numeric {ndim}D array required")\n    with np.errstate(over="ignore", invalid="ignore"):\n        a = a.astype(np.float64, copy=False)\n    if not np.isfinite(a).all():\n        raise ReadoutInputError(f"{name}: all values must be finite float64")\n    return a\n\n\ndef constant_safe_mean(a, axis=0):\n    """Accurate finite-input mean with exact constants and no overflow sum.\n\n    This helper intentionally preserves nonbinary constants such as 0.1 rather\n    than allowing repeated summation roundoff to invent response variance.\n    """\n    a = np.asarray(a)\n    if a.dtype != np.dtype("float64") or not np.isfinite(a).all():\n        raise ReadoutInputError("constant_safe_mean requires finite float64")\n    if type(axis) is not int or axis < 0 or axis >= a.ndim or a.shape[axis] == 0:\n        raise ReadoutInputError("invalid mean axis")\n    moved = np.moveaxis(a, axis, 0)\n    flat = moved.reshape(moved.shape[0], -1)\n    result = np.empty(flat.shape[1], dtype=np.float64)\n    n = flat.shape[0]\n    for j in range(flat.shape[1]):\n        col = flat[:, j]\n        if np.all(col == col[0]):\n            result[j] = col[0]\n            continue\n        if np.any((col != 0) & (np.abs(col) < np.nextafter(0.0, 1.0) * n)):\n            # Dividing subnormal terms before summing can erase a representable\n            # mean. The rare fallback sums the exact admitted float inputs.\n            result[j] = float(sum(Fraction.from_float(float(v)) for v in col) / n)\n            continue\n        try:\n            result[j] = math.fsum(float(v) / n for v in col)\n        except OverflowError:\n            result[j] = float(sum(Fraction.from_float(float(v)) for v in col) / n)\n    return result.reshape(moved.shape[1:])\n\n\ndef training_repeat_mean(responses, *, strict=True):\n    """[1000, 3, voxels] -> [1000, voxels]; never uses query responses."""\n    if type(strict) is not bool:\n        raise ReadoutInputError("strict must be boolean")\n    a = _array(responses, 3, "training repeated responses")\n    if min(a.shape) < 1 or (strict and a.shape[:2] != (TRAIN_VIDEOS, 3)):\n        raise ReadoutInputError("complete training repeat panel required")\n    return constant_safe_mean(a, axis=1)\n\n\ndef _center_columns(a):\n    """Represent the mean as midpoint + scale * residual_mean, without loss.\n\n    Reconstructing the absolute mean before subtraction can round away small\n    represented variation. Keep this two-part intercept throughout fitting.\n    """\n    midpoint = a.min(axis=0) / 2 + a.max(axis=0) / 2\n    residual = a - midpoint\n    scale = np.max(np.abs(residual), axis=0)\n    scale[scale == 0] = 1.0\n    scaled = residual / scale\n    residual_mean = constant_safe_mean(scaled)\n    centered = scaled - residual_mean\n    constant = np.all(a == a[0:1], axis=0)\n    centered[:, constant] = 0.0\n    mean = midpoint + scale * residual_mean\n    mean[constant] = a[0, constant]\n    if not np.isfinite(centered).all() or not np.isfinite(mean).all():\n        raise ReadoutNumericalError("centered response not representable")\n    return centered, midpoint, scale, residual_mean, mean, constant\n\n\ndef standardize_features(train, query, *, strict=True):\n    """Return scaled train/query plus frozen training mean/SD/constant mask.\n\n    Subtract a safe training midpoint before residual scaling. This preserves\n    small represented differences as well as protecting finite extremes; it is\n    not clipping or a scientific feature transformation beyond z-scoring.\n    """\n    if type(strict) is not bool:\n        raise ReadoutInputError("strict must be boolean")\n    x = _array(train, 2, "training features")\n    q = _array(query, 2, "query features")\n    if x.shape[0] < 2 or q.shape[0] < 1 or x.shape[1] < 1 or x.shape[1] != q.shape[1]:\n        raise ReadoutInputError("matched nonempty feature columns required")\n    if strict and (x.shape != (TRAIN_VIDEOS, FEATURES) or q.shape != (QUERY_VIDEOS, FEATURES)):\n        raise ReadoutInputError("production requires 1000x100 train and 102x100 query")\n    centered, midpoint, scale, residual_mean, mean, constant = _center_columns(x)\n    sd_scaled = np.sqrt(np.mean(centered * centered, axis=0))\n    if np.any((~constant) & (sd_scaled == 0)):\n        raise ReadoutNumericalError("nonconstant feature variation lost in arithmetic")\n    sd = sd_scaled * scale\n    if np.any((~constant) & ((sd == 0) | ~np.isfinite(sd))):\n        raise ReadoutNumericalError("training feature SD not representable")\n    divisor = np.where(constant, 1.0, sd_scaled)\n    z = centered / divisor\n    # Constant training features are ignored even if their query values differ;\n    # do not perform unnecessary extreme division on those discarded columns.\n    zq = np.zeros(q.shape, dtype=np.float64)\n    active = ~constant\n    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):\n        difference = q[:, active] - midpoint[active]\n        zq[:, active] = (difference / scale[active] - residual_mean[active]) / divisor[active]\n    # A query-midpoint subtraction can overflow although its standardized value\n    # is finite. Recover only those rare cells from the admitted float inputs.\n    active_indices = np.flatnonzero(active)\n    for i, k in np.argwhere(~np.isfinite(difference) | ~np.isfinite(zq[:, active])):\n        j = active_indices[k]\n        exact = (((Fraction.from_float(float(q[i, j])) - Fraction.from_float(float(midpoint[j]))) /\n                  Fraction.from_float(float(scale[j])) - Fraction.from_float(float(residual_mean[j]))) /\n                 Fraction.from_float(float(divisor[j])))\n        try:\n            zq[i, j] = float(exact)\n        except OverflowError as exc:\n            raise ReadoutNumericalError("standardized feature value not representable") from exc\n    if not np.isfinite(z).all() or not np.isfinite(zq).all():\n        raise ReadoutNumericalError("standardized feature value not representable")\n    return {"train": z, "query": zq, "mean": mean, "sd_ddof0": sd,\n            "constant_features": constant}\n\n\ndef _predict_rescaled(query, coefficients, response_scale, response_mean, *, residual_mean=None):\n    """Evaluate scaled linear response; rare exact fallback avoids false overflow."""\n    residual_mean = np.zeros_like(response_mean) if residual_mean is None else residual_mean\n    with np.errstate(over="ignore", invalid="ignore"):\n        centered = query @ coefficients\n        restored = centered + residual_mean\n        scaled = restored * response_scale\n        result = scaled + response_mean\n    bad = ~np.isfinite(centered) | ~np.isfinite(restored) | ~np.isfinite(scaled) | ~np.isfinite(result)\n    for i, j in np.argwhere(bad):\n        dot = sum(Fraction.from_float(float(a)) * Fraction.from_float(float(b))\n                  for a, b in zip(query[i], coefficients[:, j]))\n        exact = (dot + Fraction.from_float(float(residual_mean[j]))) * Fraction.from_float(float(response_scale[j])) + Fraction.from_float(float(response_mean[j]))\n        try:\n            value = float(exact)\n        except OverflowError as exc:\n            raise ReadoutNumericalError("predicted response not representable") from exc\n        if not math.isfinite(value):\n            raise ReadoutNumericalError("predicted response not representable")\n        result[i, j] = value\n    return result\n\n\ndef fixed_ridge_readout(train_features, query_features, training_responses, *, strict=True):\n    """Return prediction/training_mean/standardization/support for one ROI.\n\n    training_responses is the repeat-mean [1000, voxels] target. Only temporal\n    features are candidate-controlled in NEURAL070; the wrapper must supply the\n    two fixed operator-owned comparators to separate calls of this same function.\n    strict=False exists solely for explicit generated fixtures.\n    """\n    features = standardize_features(train_features, query_features, strict=strict)\n    y = _array(training_responses, 2, "training response means")\n    if y.shape[0] != features["train"].shape[0] or y.shape[1] < 1:\n        raise ReadoutInputError("response rows must match all training videos")\n    yc, midpoint, scale, residual_mean, mean, constant_response = _center_columns(y)\n    # Recenter the finite standardized design for the unpenalized intercept,\n    # including its tiny floating-point centering residual.\n    zmean = constant_safe_mean(features["train"])\n    z = features["train"] - zmean\n    zq = features["query"] - zmean\n    gram = z.T @ z\n    gram.flat[::gram.shape[0] + 1] += RIDGE_LAMBDA\n    try:\n        coefficients = np.linalg.solve(gram, z.T @ yc)\n    except np.linalg.LinAlgError as exc:\n        raise ReadoutNumericalError("fixed ridge solve failed") from exc\n    if not np.isfinite(coefficients).all():\n        raise ReadoutNumericalError("fixed ridge coefficients not finite")\n    prediction = _predict_rescaled(zq, coefficients, scale, midpoint, residual_mean=residual_mean)\n    return {\n        "prediction": prediction,\n        "training_mean": mean,\n        "standardization": {k: features[k] for k in ("mean", "sd_ddof0", "constant_features")},\n        "support": {"train_videos": y.shape[0], "query_videos": prediction.shape[0],\n                    "features": z.shape[1], "voxels": y.shape[1],\n                    "constant_training_features": int(features["constant_features"].sum()),\n                    "constant_training_responses": int(constant_response.sum())},\n        "ridge_lambda": RIDGE_LAMBDA,\n        "intercept_penalized": False,\n        "production_full_panel": strict,\n    }\n'
SOURCE_SHA256 = {'io_contract': '9de1c25b0c41177dd65186790ee6446b02d3b7184306e7d62cab4f300c03d14f', 'readout': '915a29e9c115ea2502e13c6ec2ca2fb2d4e8f26df774b5fc59cea0503d176477'}
CASES = (('sub-01/lV1v', 200), ('sub-01/rV1v', 170), ('sub-01/lV1d', 184), ('sub-01/rV1d', 173), ('sub-01/lMT', 38), ('sub-01/rMT', 57), ('sub-01/lSTS', 204), ('sub-01/rSTS', 557), ('sub-02/lV1v', 200), ('sub-02/rV1v', 170), ('sub-02/lV1d', 184), ('sub-02/rV1d', 173), ('sub-02/lMT', 38), ('sub-02/rMT', 57), ('sub-02/lSTS', 204), ('sub-02/rSTS', 557), ('sub-03/lV1v', 200), ('sub-03/rV1v', 170), ('sub-03/lV1d', 184), ('sub-03/rV1d', 173), ('sub-03/lMT', 38), ('sub-03/rMT', 57), ('sub-03/lSTS', 204), ('sub-03/rSTS', 557), ('sub-04/lV1v', 200), ('sub-04/rV1v', 170), ('sub-04/lV1d', 184), ('sub-04/rV1d', 173), ('sub-04/lMT', 38), ('sub-04/rMT', 57), ('sub-04/lSTS', 204), ('sub-04/rSTS', 557), ('sub-05/lV1v', 200), ('sub-05/rV1v', 170), ('sub-05/lV1d', 184), ('sub-05/rV1d', 173), ('sub-05/lMT', 38), ('sub-05/rMT', 57), ('sub-05/lSTS', 204), ('sub-05/rSTS', 557), ('sub-06/lV1v', 200), ('sub-06/rV1v', 170), ('sub-06/lV1d', 184), ('sub-06/rV1d', 173), ('sub-06/lMT', 38), ('sub-06/rMT', 57), ('sub-06/lSTS', 204), ('sub-06/rSTS', 557), ('sub-07/lV1v', 200), ('sub-07/rV1v', 170), ('sub-07/lV1d', 184), ('sub-07/rV1d', 173), ('sub-07/lMT', 38), ('sub-07/rMT', 57), ('sub-07/lSTS', 204), ('sub-07/rSTS', 557), ('sub-08/lV1v', 200), ('sub-08/rV1v', 170), ('sub-08/lV1d', 184), ('sub-08/rV1d', 173), ('sub-08/lMT', 38), ('sub-08/rMT', 57), ('sub-08/lSTS', 204), ('sub-08/rSTS', 557), ('sub-09/lV1v', 200), ('sub-09/rV1v', 170), ('sub-09/lV1d', 184), ('sub-09/rV1d', 173), ('sub-09/lMT', 38), ('sub-09/rMT', 57), ('sub-09/lSTS', 204), ('sub-09/rSTS', 557), ('sub-10/lV1v', 200), ('sub-10/rV1v', 170), ('sub-10/lV1d', 184), ('sub-10/rV1d', 173), ('sub-10/lMT', 38), ('sub-10/rMT', 57), ('sub-10/lSTS', 204), ('sub-10/rSTS', 557))
ROSTER_PIN = {"bytes": 1022157, "sha256": "45ce81fde0ec94dcc52b2aee97141f7b956b435f11e87dd26852ea35b0d24880"}
ROIS = ("lV1v", "rV1v", "lV1d", "rV1d", "lMT", "rMT", "lSTS", "rSTS")
SUBJECTS = tuple(f"sub-{i:02d}" for i in range(1, 11))
MAX_OUTPUT_BYTES = 14328960


def need(condition, message):
    if not condition:
        raise ValueError(message)


def dependencies():
    modules = []
    for name, source in (("io_contract", IO_SOURCE), ("readout", READOUT_SOURCE)):
        raw = source.encode("utf-8")
        need(hashlib.sha256(raw).hexdigest() == SOURCE_SHA256[name], "embedded source changed")
        module = types.ModuleType("neural069_reference_" + name)
        exec(compile(source, "<pinned-neural069-" + name + ">", "exec"), module.__dict__)
        modules.append(module)
    return tuple(modules)


def capture_relative(root_fd, relative, byte_cap, contract):
    """Traverse ordinary directories relative to the already-open public root."""
    parts = relative.split("/")
    need(parts and all(p and p not in (".", "..") for p in parts), "ordinary relative public path required")
    fd = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return contract._capture(parts[-1], byte_cap, dir_fd=fd)
    finally:
        os.close(fd)


def admit_roster(raw, digest, contract):
    need(len(raw) == ROSTER_PIN["bytes"] and digest == ROSTER_PIN["sha256"], "exact frozen public roster required")
    roster = contract.strict_json(raw, max_bytes=2000000)
    need(roster.get("schema") == "boldmoments-public-roster-v1", "roster schema")
    need(roster.get("subjects") == list(SUBJECTS), "complete participant order")
    need(roster.get("train_video_ids") == [f"vid{i:04d}" for i in range(1, 1001)], "complete training video order")
    need(roster.get("query_video_ids") == [f"vid{i:04d}" for i in range(1001, 1103)], "complete query video order")
    need(type(roster.get("training_repeats")) is int and roster["training_repeats"] == 3
         and type(roster.get("query_repeats")) is int and roster["query_repeats"] == 10, "unchanged repeat support")
    cases = roster.get("cases")
    need(type(cases) is list and len(cases) == 80, "complete eighty-case panel")
    for case, (case_id, voxels) in zip(cases, CASES):
        subject, roi = case_id.split("/")
        need(case.get("id") == case_id and case.get("subject") == subject and case.get("roi") == roi,
             "exact ordered participant/ROI case")
        need(type(case.get("voxels")) is int and case["voxels"] == voxels, "complete native coordinate extent")
        coordinates = case.get("coordinates")
        need(type(coordinates) is list and len(coordinates) == voxels
             and all(type(c) is list and len(c) == 3 and all(type(v) is int for v in c) for c in coordinates)
             and len({tuple(c) for c in coordinates}) == voxels, "unique complete coordinate identities")
        need(case["training"]["path"] == "public/input/training/" + case_id.replace("/", "_") + ".npy",
             "case-specific training source")
    for split in ("train", "test"):
        need(roster["features"]["layer4"][split]["path"] == f"public/input/features/{split}_layer4.npy",
             "fixed layer4 source")
    return roster


def load_array(root_fd, pin, shape, contract):
    need(type(pin) is dict and set(pin) == {"path", "bytes", "sha256"}, "exact public source descriptor")
    path = pin["path"]
    need(type(path) is str and path.startswith("public/input/"), "public input only")
    need(type(pin["bytes"]) is int and 0 < pin["bytes"] <= 8 * shape[0] * shape[1] + 16396,
         "shape-bounded public source")
    raw, digest = capture_relative(root_fd, path[len("public/"):], pin["bytes"], contract)
    need(len(raw) == pin["bytes"] and digest == pin["sha256"], "captured public input differs from frozen descriptor")
    return contract.parse_npy(raw, shape, expected_rows=shape[0])


def write_exclusive(root_fd, name, raw):
    need(type(name) is str and "/" not in name and name not in ("", ".", ".."), "ordinary output basename")
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=root_fd)
    try:
        need(stat.S_ISREG(os.fstat(fd).st_mode), "ordinary output required")
        view = memoryview(raw)
        while view:
            count = os.write(fd, view)
            need(count > 0, "short output write")
            view = view[count:]
        os.fsync(fd)
    finally:
        os.close(fd)


def serialize_prediction(prediction, shape):
    array = np.asarray(prediction)
    need(array.shape == shape and array.dtype.kind == "f" and array.dtype.itemsize in (4, 8)
         and bool(np.isfinite(array).all()), "complete finite prediction matrix")
    buffer = io.BytesIO()
    np.save(buffer, np.ascontiguousarray(array), allow_pickle=False)
    raw = buffer.getvalue()
    need(len(raw) <= 8 * shape[0] * shape[1] + 16396, "prediction serialization exceeds native-shape bound")
    return raw


def produce(public_fd, output_fd, roster, roster_digest, contract, readout):
    need(BASELINE_METHOD in ("training_mean", "layer4_ridge"), "fixed method required")
    need(os.listdir(output_fd) == [], "output volume must start empty")
    x = q = None
    if BASELINE_METHOD == "layer4_ridge":
        x = load_array(public_fd, roster["features"]["layer4"]["train"], (1000, 100), contract)
        q = load_array(public_fd, roster["features"]["layer4"]["test"], (102, 100), contract)
    records, total = [], 0
    for case in roster["cases"]:
        shape = (102, case["voxels"])
        training = load_array(public_fd, case["training"], (1000, case["voxels"]), contract)
        if BASELINE_METHOD == "training_mean":
            prediction = np.broadcast_to(readout.constant_safe_mean(training.astype(np.float64, copy=False), axis=0), shape)
        else:
            prediction = readout.fixed_ridge_readout(x, q, training)["prediction"]
        raw = serialize_prediction(prediction, shape)
        total += len(raw)
        need(total <= MAX_OUTPUT_BYTES, "complete output byte cap")
        name = case["id"].replace("/", "_") + ".npy"
        write_exclusive(output_fd, name, raw)
        records.append({"id": case["id"], "path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    need(len(records) == 80, "all eighty predictions before final submission")
    submission = {"task_id": "NEURAL-069", "roster_sha256": roster_digest, "predictions": records}
    raw = (json.dumps(submission, allow_nan=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    need(len(raw) <= 100000 and total + len(raw) <= MAX_OUTPUT_BYTES, "submission and complete output byte cap")
    write_exclusive(output_fd, "submission.json", raw)
    return {"status": "predictions_written", "method": BASELINE_METHOD, "cases": len(records), "scoring_performed": False}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--public-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    contract, readout = dependencies()
    public_fd = os.open(args.public_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        output_fd = os.open(args.output_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            raw, digest = capture_relative(public_fd, "input/ROSTER.json", 2000000, contract)
            roster = admit_roster(raw, digest, contract)
            result = produce(public_fd, output_fd, roster, digest, contract, readout)
        finally:
            os.close(output_fd)
    finally:
        os.close(public_fd)
    print(json.dumps(result, sort_keys=True))
    return result


if __name__ == "__main__":
    main()
