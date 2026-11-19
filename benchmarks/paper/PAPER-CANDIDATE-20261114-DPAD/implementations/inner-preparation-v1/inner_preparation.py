"""DPAD source-default inner-CV preparation for finite continuous arrays.

Inputs are *already prepared outer-training observations*, in original row and
channel order. This operator component neither prepares raw recordings nor
selects the historical outer folds. See README.md for the source boundary.
"""
from dataclasses import dataclass
from collections.abc import Mapping

import numpy as np


@dataclass(frozen=True)
class Scaling:
    remove_y_mean: bool
    zscore_y: bool
    remove_z_mean: bool
    zscore_z: bool

    def __post_init__(self):
        if any(type(v) is not bool for v in vars(self).values()):
            raise ValueError("scaling choices must be explicit booleans")


@dataclass(frozen=True)
class PreparedInnerFold:
    number: int
    train_indices: tuple
    selection_indices: tuple
    train_sample_ids: tuple
    selection_sample_ids: tuple
    channel_layout: dict
    y_train: np.ndarray
    z_train: np.ndarray
    y_selection_raw: np.ndarray
    z_selection_raw: np.ndarray
    y_selection_scaled: np.ndarray
    z_selection_scaled: np.ndarray
    y_mean: np.ndarray
    y_std: np.ndarray
    z_mean: np.ndarray
    z_std: np.ndarray


def _matrix(value, label):
    if (not isinstance(value, np.ndarray) or value.dtype != np.dtype("float64")
            or value.ndim != 2 or not value.shape[1]):
        raise ValueError(f"{label} must be a nonempty-width float64 matrix")
    if not np.all(np.isfinite(value)):
        raise ValueError(f"{label} contains missing or nonfinite observations")
    return value


def _layout(value, ny, nz):
    if not isinstance(value, Mapping) or set(value) != {"neural", "behavior"}:
        raise ValueError("both ordered channel layouts are required")
    out = {}
    for role, width in (("neural", ny), ("behavior", nz)):
        rows = value[role]
        if not isinstance(rows, (list, tuple)) or len(rows) != width:
            raise ValueError(f"{role} channel count does not match the array")
        items = []
        for row in rows:
            if (not isinstance(row, Mapping) or set(row) != {"id", "unit"}
                    or any(not isinstance(row[k], str) or not row[k] for k in row)):
                raise ValueError("every channel needs a nonempty identity and unit")
            items.append({"id": row["id"], "unit": row["unit"]})
        if len({r["id"] for r in items}) != width:
            raise ValueError(f"duplicate {role} channel identity")
        out[role] = items
    if not 77 <= ny <= 99 or nz != 4:
        raise ValueError("the DPAD source-panel width is 77–99 neural and 4 behavior channels")
    if [r["id"] for r in out["behavior"]] != [
            "position_x", "position_y", "velocity_x", "velocity_y"]:
        raise ValueError("behavior columns must retain their declared position/velocity order")
    return out


def source_inner_indices(n_samples):
    """The current author's unshuffled genCVFoldInds(N, 2) default.

    A ceiling-sized first selection block leaves the tail for the second. This
    is the caller reached by iCVF2 with CVFoldInds=None, not the different
    floor/remainder helper, and not a claim about historical outer-fold identity.
    """
    if type(n_samples) is not int or n_samples < 4:
        raise ValueError("two inner folds need at least two training rows each")
    cut = (n_samples + 1) // 2
    first = tuple(range(cut))
    second = tuple(range(cut, n_samples))
    return ((second, first), (first, second))


def _learn(train, remove_mean, zscore):
    mean = np.zeros(train.shape[1], dtype=np.float64)
    std = np.ones(train.shape[1], dtype=np.float64)
    if remove_mean or zscore:
        # The selected finite profile has no masked observations. Keep the
        # source masked-array arithmetic and its sample (not population) SD.
        finite = np.ma.array(train, mask=np.zeros(train.shape, dtype=bool))
        mean = np.array(np.ma.mean(finite, axis=0))
        if zscore:
            std = np.array(np.ma.std(finite, axis=0, ddof=1))
    if not np.all(np.isfinite(mean)) or not np.all(np.isfinite(std)):
        raise ValueError("normalization is not finite")
    return mean, std


def _apply(values, mean, std):
    result = values.copy()
    result -= mean
    positive = std > 0
    result[:, positive] /= std[positive]
    if not np.all(np.isfinite(result)):
        raise ValueError("scaled values are not finite")
    return result


def iter_inner_preparation(y, z, sample_ids, channel_layout, *, scaling):
    """Yield the two operator-side inner folds in source order.

    Every array is time by channel. Only inner-training rows determine the
    transforms. Raw selection arrays are retained separately from transformed
    arrays, as in prepareTrainingAndTestData. There is no outer-test argument.
    These objects are operator/reference material, not a participant packet.
    """
    if not isinstance(scaling, Scaling):
        raise ValueError("an explicit Scaling configuration is required")
    y = _matrix(y, "neural")
    z = _matrix(z, "behavior")
    if y.shape[0] != z.shape[0]:
        raise ValueError("neural and behavior row counts differ")
    if (not isinstance(sample_ids, (tuple, list)) or len(sample_ids) != y.shape[0]
            or any(not isinstance(s, str) or not s for s in sample_ids)
            or len(set(sample_ids)) != len(sample_ids)):
        raise ValueError("unique ordered sample identities must cover every row")
    ids = tuple(sample_ids)
    layout = _layout(channel_layout, y.shape[1], z.shape[1])
    for number, (train, selection) in enumerate(source_inner_indices(y.shape[0]), 1):
        yt, zt = y[list(train), :], z[list(train), :]
        ys, zs = y[list(selection), :], z[list(selection), :]
        ym, ysd = _learn(yt, scaling.remove_y_mean, scaling.zscore_y)
        zm, zsd = _learn(zt, scaling.remove_z_mean, scaling.zscore_z)
        yield PreparedInnerFold(
            number, train, selection, tuple(ids[i] for i in train),
            tuple(ids[i] for i in selection),
            {k: [dict(v) for v in rows] for k, rows in layout.items()},
            _apply(yt, ym, ysd), _apply(zt, zm, zsd), ys, zs,
            _apply(ys, ym, ysd), _apply(zs, zm, zsd), ym, ysd, zm, zsd)
