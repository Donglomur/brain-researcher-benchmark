"""Standalone MEG training-range-logistic-comparator-v1.
Scientific reference programme; not an AI access-arm result or SOTA claim.
Reads only the public Generic scalar bank and one fold context.
"""
import argparse
import ast
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import sys
import types

sys.dont_write_bytecode = True
REFERENCE = "author-batch-range-logistic-reference-v1"
COMPARATOR = "training-range-logistic-comparator-v1"
PROGRAMME_ARM = 'training-range-logistic-comparator-v1'
SCALER_SOURCE = 'from sklearn.utils.validation import (\n    check_is_fitted,\n    check_random_state,\n    _check_sample_weight,\n    FLOAT_DTYPES,\n)\nfrom sklearn.preprocessing import StandardScaler, RobustScaler\nimport pandas as pd\nimport math\nfrom sklearn.base import BaseEstimator, TransformerMixin\nimport numpy as np\n\nclass MixedSigmoidScaler(TransformerMixin, BaseEstimator):\n    """Scale features using statistics that are robust to outliers.\n    This Scaler removes the median and scales the data according to\n    the quantile range (defaults to IQR: Interquartile Range).\n    The IQR is the range between the 1st quartile (25th quantile)\n    and the 3rd quartile (75th quantile).\n    Centering and scaling happen independently on each feature by\n    computing the relevant statistics on the samples in the training\n    set. Median and interquartile range are then stored to be used on\n    later data using the :meth:`transform` method.\n    Standardization of a dataset is a common requirement for many\n    machine learning estimators. Typically this is done by removing the mean\n    and scaling to unit variance. However, outliers can often influence the\n    sample mean / variance in a negative way. In such cases, the median and\n    the interquartile range often give better results.\n    .. versionadded:: 0.17\n    Read more in the :ref:`User Guide <preprocessing_scaler>`.\n    Parameters\n    ----------\n    quantile_range : tuple (q_min, q_max), 0.0 < q_min < q_max < 100.0, \\\n        default=(25.0, 75.0)\n        Quantile range used to calculate `scale_`. By default this is equal to\n        the IQR, i.e., `q_min` is the first quantile and `q_max` is the third\n        quantile.\n        .. versionadded:: 0.18\n    copy : bool, default=True\n        If `False`, try to avoid a copy and do inplace scaling instead.\n        This is not guaranteed to always work inplace; e.g. if the data is\n        not a NumPy array or scipy.sparse CSR matrix, a copy may still be\n        returned.\n    unit_variance : bool, default=False\n        If `True`, scale data so that normally distributed features have a\n        variance of 1. In general, if the difference between the x-values of\n        `q_max` and `q_min` for a standard normal distribution is greater\n        than 1, the dataset will be scaled down. If less than 1, the dataset\n        will be scaled up.\n        .. versionadded:: 0.24\n    Attributes\n    ----------\n    center_ : array of floats\n        The median value for each feature in the training set.\n    scale_ : array of floats\n        The (scaled) interquartile range for each feature in the training set.\n        .. versionadded:: 0.17\n           *scale_* attribute.\n    n_features_in_ : int\n        Number of features seen during :term:`fit`.\n        .. versionadded:: 0.24\n    feature_names_in_ : ndarray of shape (`n_features_in_`,)\n        Names of features seen during :term:`fit`. Defined only when `X`\n        has feature names that are all strings.\n        .. versionadded:: 1.0\n    See Also\n    --------\n    robust_scale : Equivalent function without the estimator API.\n    sklearn.decomposition.PCA : Further removes the linear correlation across\n        features with \'whiten=True\'.\n    Notes\n    -----\n    For a comparison of the different scalers, transformers, and normalizers,\n    see :ref:`examples/preprocessing/plot_all_scaling.py\n    <sphx_glr_auto_examples_preprocessing_plot_all_scaling.py>`.\n    https://en.wikipedia.org/wiki/Median\n    https://en.wikipedia.org/wiki/Interquartile_range\n    Examples\n    --------\n    >>> from sklearn.preprocessing import RobustScaler\n    >>> X = [[ 1., -2.,  2.],\n    ...      [ -2.,  1.,  3.],\n    ...      [ 4.,  1., -2.]]\n    >>> transformer = RobustScaler().fit(X)\n    >>> transformer\n    RobustScaler()\n    >>> transformer.transform(X)\n    array([[ 0. , -2. ,  0. ],\n           [-1. ,  0. ,  0.4],\n           [ 1. ,  0. , -1.6]])\n    """\n\n    _parameter_constraints: dict = {\n         "quantile_range": [tuple],\n         "copy": ["boolean"],\n        "unit_variance": ["boolean"]\n    }\n\n    def __init__(\n        self,\n        *,\n        quantile_range=(25.0, 75.0),\n        copy = True,\n        unit_variance=False\n    ):\n        self.quantile_range = quantile_range\n        self.copy = copy\n        self.unit_variance = unit_variance\n\n    def fit(self, X, y=None):\n        """Compute the median and quantiles to be used for scaling.\n        Parameters\n        ----------\n        X : {array-like, sparse matrix} of shape (n_samples, n_features)\n            The data used to compute the median and quantiles\n            used for later scaling along the features axis.\n        y : Ignored\n            Not used, present here for API consistency by convention.\n        Returns\n        -------\n        self : object\n            Fitted scaler.\n        """\n        # self._validate_params()\n\n        # at fit, convert sparse matrices to csc for optimized computation of\n        # the quantiles\n        X = self._validate_data(\n            X,\n            accept_sparse="csc",\n            dtype=FLOAT_DTYPES,\n            force_all_finite="allow-nan",\n        )\n\n        q_min, q_max = self.quantile_range\n        if not 0 <= q_min <= q_max <= 100:\n            raise ValueError("Invalid quantile range: %s" % str(self.quantile_range))\n            \n        self.IQR_ = np.nanpercentile(X, self.quantile_range, axis=0)\n        self.IQR_diffs_ = self.IQR_[1,:] - self.IQR_[0,:]\n        self.mean_ = np.nanmean(X, axis=0)\n        self.sd_ = np.nanstd(X, axis=0)\n        self.median_ = np.nanmedian(X, axis=0)\n\n        return self\n\n\n    def transform(self, X):\n        """Center and scale the data.\n        Parameters\n        ----------\n        X : {array-like, sparse matrix} of shape (n_samples, n_features)\n            The data used to scale along the specified axis.\n        Returns\n        -------\n        X_tr : {ndarray, sparse matrix} of shape (n_samples, n_features)\n            Transformed array.\n        """\n        check_is_fitted(self)\n        X = self._validate_data(\n            X,\n            accept_sparse=("csr", "csc"),\n            copy=self.copy,\n            dtype=FLOAT_DTYPES,\n            reset=False,\n            force_all_finite="allow-nan",\n        )\n\n        X_transformed = np.zeros(X.shape)\n\n        # Iterate over each feature column\n        for i in range(X_transformed.shape[1]):\n            # catch for if the IQR difference is zero, in which case we apply standard logistic transformation using mean and SD\n            if self.IQR_diffs_[i] == 0:\n                scale = 1\n                X_i = 1/(1 + math.e**(- ( (X[:,i] - self.mean_[i]) / self.sd_[i] ) ))\n            # otherwise, set the scaling factor to the IQR/1.35\n            else: \n                IQR = self.IQR_diffs_[i]\n                # Center by removing the median, standarize by dividing by scale value\n                X_i = 1/(1 + math.e**(- ( (X[:,i] - self.median_[i]) / IQR/1.35 ) ))\n            \n            # Scale to unit variance [0,1] if specified\n            if self.unit_variance:\n                # Find the min value in this feature\n                X_i_min = np.nanmin(X_i)\n                # Find the range of values in this feature\n                X_i_diff = np.ptp(X_i)\n\n                # If the range is 0, return X_i_diff since the scaling above would already set all values to 0.5\n                if X_i_diff == 0:\n                    X_transformed[:,i] = X_i\n                # Otherwise, subtract the minimum and divide by the range\n                else:\n                    X_transformed[:,i] = (X_i - X_i_min) / X_i_diff\n            else: \n                X_transformed[:,i] = X_i\n\n        return(X_transformed)\n\n'
SCALER_SHA256 = 'a3b64f75e492f6e8e44bd67f07dd6a52f3a4aaf36f014ed127b441144a23e918'
METHOD_SOURCE = 'def finite_matrix(X):\n    X = np.asarray(X, dtype=float)\n    require(X.ndim == 2 and X.shape[1] == 1 and 1 <= len(X) <= 188\n            and bool(np.isfinite(X).all()), "finite one-feature endpoint matrix")\n    return X\n\ndef admit_training(X):\n    X = finite_matrix(X)\n    require(len(X) >= 2 and bool(np.all(np.nanstd(X, axis=0) > 0)),\n            "constant-training undefined author scaler refused")\n    return X\n\nclass TrainingRangeSigmoidScaler(TransformerMixin, BaseEstimator):\n    """Separate comparator: author sigmoid, final range fitted on training only.\n\n    Values outside the training sigmoid range are deliberately not clipped.\n    The author zero-range convention (return sigmoid values) is preserved.\n    """\n    def fit(self, X, y=None):\n        X = admit_training(X)\n        self.author_ = MixedSigmoidScaler(unit_variance=False).fit(X)\n        Z = finite_matrix(self.author_.transform(X))\n        self.min_ = np.nanmin(Z, axis=0)\n        self.range_ = np.ptp(Z, axis=0)\n        return self\n\n    def transform(self, X):\n        require(hasattr(self, "author_"), "training-range scaler not fitted")\n        Z = finite_matrix(self.author_.transform(finite_matrix(X)))\n        return finite_matrix(np.where(self.range_ == 0, Z,\n                             (Z - self.min_) / np.where(self.range_ == 0, 1, self.range_)))\n\ndef make_scaler(arm):\n    require(arm in ARMS, "named scaler arm")\n    return MixedSigmoidScaler(unit_variance=True) if arm == REFERENCE else TrainingRangeSigmoidScaler()\n\ndef make_model():\n    # All unlisted parameters retain sklearn 1.5.0 defaults, including tol/max_iter/intercept.\n    return LogisticRegression(penalty="l1", C=1, solver="liblinear",\n                              class_weight="balanced", random_state=127)\n\ndef object_probability(classes, probability):\n    classes = list(classes); probability = np.asarray(probability)\n    require(len(classes) == 2 and set(classes) == set(LABELS) and probability.ndim == 2\n            and probability.shape[1] == 2 and bool(np.isfinite(probability).all())\n            and bool(((probability >= 0) & (probability <= 1)).all())\n            and bool(np.allclose(probability.sum(axis=1), 1, rtol=0, atol=1e-12)),\n            "label-oriented probability matrix")\n    return probability[:, classes.index("object")]\n'
METHOD_SHA256 = '56542b7dcf9972358344ed0b2b472504f2ffb14c8a8b95f35e7c80ddf95730ec'
CONTRACT_SOURCE = 'def require(value, message):\n    if not value:\n        raise ValueError(message)\n\ndef canonical(value):\n    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()\n\ndef digest(value):\n    return hashlib.sha256(canonical(value)).hexdigest()\n\ndef fields(value, names, name):\n    require(type(value) is dict and set(value) == set(names), name + " fields")\n\ndef sha(value):\n    require(type(value) is str and HEX.fullmatch(value) is not None, "SHA256 identity")\n    return value\n\ndef binding(value):\n    fields(value, ("bytes", "sha256"), "source binding")\n    require(type(value["bytes"]) is int and value["bytes"] > 0, "positive source bytes")\n    sha(value["sha256"])\n\ndef checked_context(context):\n    fields(context, ("schema", "input_mode", "panel_sha256", "source_binding", "fold", "rows",\n                     "training", "queries", "context_sha256"), "Generic context")\n    require(context["schema"] == CONTEXT_SCHEMA and context["input_mode"] == MODE, "Generic context mode")\n    require(sha(context["context_sha256"]) == digest({k: v for k, v in context.items() if k != "context_sha256"}), "context identity")\n    sha(context["panel_sha256"]); binding(context["source_binding"])\n    require(type(context["fold"]) is int and 0 <= context["fold"] < 10, "fold0..9")\n    rows = context["rows"]\n    require(type(rows) is list and len(rows) == 188, "188 public scalar rows")\n    identities, groups = set(), {}\n    for row in rows:\n        fields(row, ("id", "group_id", "scalar_sha256"), "public scalar row")\n        identifier = sha(row["id"]); sha(row["group_id"]); sha(row["scalar_sha256"])\n        require(identifier not in identities, "unique public row")\n        identities.add(identifier); groups.setdefault(row["group_id"], set()).add(identifier)\n    require(rows == sorted(rows, key=lambda r: r["id"]) and len(groups) == 94\n            and all(len(v) == 2 for v in groups.values()), "opaque order and94paired groups")\n    train = {}\n    require(type(context["training"]) is list, "ordered training rows")\n    for row in context["training"]:\n        fields(row, ("id", "label"), "training row")\n        require(row["id"] in identities and row["id"] not in train and row["label"] in PAIR, "unique labeled training row")\n        train[row["id"]] = row["label"]\n    query = context["queries"]\n    require(type(query) is list and query == sorted(set(query)) and query, "unique ordered held queries")\n    require(set(train).isdisjoint(query) and set(train) | set(query) == identities and train, "exact training/held partition")\n    for members in groups.values():\n        require(members <= set(train) or members <= set(query), "no participant across training/held")\n        if members <= set(train):\n            require({train[i] for i in members} == set(PAIR), "paired face/object training labels")\n    return context\n'
CONTRACT_SHA256 = 'e8f07f95a1a22e4bfdbdc1792b73300b83891ca509c7e3a059f5c1cbb98c3f9e'

def load_checked_input(directory):
    """Read only the two public files; no original bank or reference access."""
    root = Path(directory)
    require(root.is_absolute() and root.is_dir() and not root.is_symlink(),
            "ordinary absolute public input directory")
    require(set(os.listdir(root)) == {"FEATURES.npy", "CONTEXT.json"},
            "exact two-file public fold input")
    context_bytes = bounded_file(root / "CONTEXT.json", 262144)
    context = strict_json(context_bytes)
    _contract.checked_context(context)
    require(len(context["queries"]) in (18, 20), "frozen9-or10-participant held fold")
    array_bytes = bounded_file(root / "FEATURES.npy", 4096)
    # Admit the shape before any array allocation. A bounded file alone does
    # not prevent np.load from allocating a huge shape declared by its header.
    require(array_bytes[:8] == b"\x93NUMPY\x01\x00" and len(array_bytes) >= 10,
            "fixed NumPy-v1 public scalar encoding")
    header_size = struct.unpack("<H", array_bytes[8:10])[0]
    require(0 < header_size <= 1024 and 10 + header_size + 188 * 8 == len(array_bytes),
            "bounded header and exact188-scalar payload extent")
    header = array_bytes[10:10 + header_size]
    require(header.endswith(b"\n"), "complete NPY header")
    metadata = ast.literal_eval(header.decode("latin1"))
    require(type(metadata) is dict and set(metadata) == {"descr", "fortran_order", "shape"}
            and metadata["descr"] == "<f8" and metadata["fortran_order"] is False
            and type(metadata["shape"]) is tuple and metadata["shape"] == (188,)
            and type(metadata["shape"][0]) is int,
            "admit exact nonobject188-scalar shape before allocation")
    values = np.frombuffer(array_bytes, dtype="<f8", count=188, offset=10 + header_size).copy()
    require(type(values) is np.ndarray and values.shape == (188,)
            and values.dtype.str == "<f8" and bool(np.isfinite(values).all()),
            "188 finite little-endian float64 public scalar values")
    positions = {}
    for index, row in enumerate(context["rows"]):
        scalar = struct.pack("<d", float(values[index]))
        require(hashlib.sha256(scalar).hexdigest() == row["scalar_sha256"],
                "each public scalar matches its opaque row commitment")
        positions[row["id"]] = index
    # The training list, unlike the opaque bank order, preserves source fit order.
    train = [positions[row["id"]] for row in context["training"]]
    queries = [positions[identifier] for identifier in context["queries"]]
    labels = np.asarray([row["label"] for row in context["training"]])
    return context, values[train].reshape(-1, 1), labels, values[queries].reshape(-1, 1)


def predict(context, training, labels, query):
    """One fit; transform the complete held batch exactly once."""
    training = _method.admit_training(training)
    query = _method.finite_matrix(query)
    scaler = _method.make_scaler(PROGRAMME_ARM)
    scaler.fit(training)
    train_x = _method.finite_matrix(scaler.transform(training))
    query_x = _method.finite_matrix(scaler.transform(query))
    model = _method.make_model()
    model.fit(train_x, labels)
    probabilities = _method.object_probability(model.classes_, model.predict_proba(query_x))
    return {"schema": "meg-generic-classification-response/v1",
            "input_mode": "generic_feature_classification_v1",
            "context_sha256": context["context_sha256"],
            "probabilities": {identifier: float(probabilities[i])
                              for i, identifier in enumerate(context["queries"])}}


def bounded_file(path, cap):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and 0 < before.st_size <= cap, "bounded ordinary public file")
        raw = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
    current = path.stat(follow_symlinks=False)
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    require(len(raw) == before.st_size and all(getattr(before, k) == getattr(after, k)
                == getattr(current, k) for k in fields), "stable complete public input")
    return raw


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate context JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: require(False, "finite JSON"))


def require(value, message):
    if not value:
        raise ValueError(message)


def initialize():
    """Exact source snippets and compatible pinned scientific packages."""
    global np, _contract, _method
    require(sys.version_info[:2] == (3, 11), "declared Python3.11 runtime")
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                 "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS"):
        os.environ[name] = "1"
    versions = {"numpy": "1.26.3", "pandas": "1.5.3", "scipy": "1.12.0",
                "sklearn": "1.5.0", "joblib": "1.5.3", "threadpoolctl": "3.6.0"}
    modules = {name: importlib.import_module(name) for name in versions}
    for name, wanted in versions.items():
        require(modules[name].__version__ == wanted, "declared package version: " + name)
    np = modules["numpy"]
    from sklearn.base import BaseEstimator, TransformerMixin
    from sklearn.linear_model import LogisticRegression
    for source, expected in ((SCALER_SOURCE, SCALER_SHA256),
                             (METHOD_SOURCE, METHOD_SHA256),
                             (CONTRACT_SOURCE, CONTRACT_SHA256)):
        require(hashlib.sha256(source.encode()).hexdigest() == expected,
                "embedded source identity")
    author = types.ModuleType("meg_initial_author_scaler")
    exec(compile(SCALER_SOURCE, "<exact-author-scaler>", "exec"), author.__dict__)
    _method = types.ModuleType("meg_selected_reference_helpers")
    _method.__dict__.update(np=np, BaseEstimator=BaseEstimator,
                           TransformerMixin=TransformerMixin, LogisticRegression=LogisticRegression,
                           MixedSigmoidScaler=author.MixedSigmoidScaler, require=require,
                           LABELS=("face", "object"), REFERENCE=REFERENCE, COMPARATOR=COMPARATOR,
                           ARMS=(REFERENCE, COMPARATOR))
    exec(compile(METHOD_SOURCE, "<exact-fresh-reference-helpers>", "exec"), _method.__dict__)
    _contract = types.ModuleType("meg_public_context_contract")
    _contract.__dict__.update(hashlib=hashlib, json=json, re=re,
                             HEX=re.compile(r"[0-9a-f]{64}"), PAIR=("face", "object"),
                             MODE="generic_feature_classification_v1",
                             CONTEXT_SCHEMA="meg-generic-classification-context/v1")
    exec(compile(CONTRACT_SOURCE, "<exact-public-context-helpers>", "exec"), _contract.__dict__)
    return modules["threadpoolctl"].threadpool_limits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    limit_threads = initialize()
    with limit_threads(limits=1):
        context, training, labels, query = load_checked_input(args.input)
        result = predict(context, training, labels, query)
    raw = (json.dumps(result, sort_keys=True, separators=(",", ":"),
                      allow_nan=False) + "\n").encode()
    require(len(raw) <= 65536, "bounded complete probability response")
    output = Path(args.output)
    require(output.is_absolute() and output.parent.is_dir() and not output.parent.is_symlink(),
            "existing ordinary absolute output parent")
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
