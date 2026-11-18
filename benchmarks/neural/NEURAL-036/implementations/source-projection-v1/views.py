"""Role-specific NEURAL-036 projection from a trusted operator array mapping.

This is a field-access boundary, not a process or filesystem sandbox. Do not
give the participant the input mapping or an operator process reference.
"""
import numpy as np

ARMS = ("joint", "history", "reverse", "shift")
ROLES = ("train", "query")


def _field(arrays, name, shape, binary=False):
    value = arrays[name]
    if (type(value) is not np.ndarray or value.shape != shape or
            value.dtype.kind != "f" or value.dtype.itemsize != 8 or
            not np.isfinite(value).all()):
        raise ValueError("invalid " + name + " array")
    if binary and not np.isin(value, (0, 1)).all():
        raise ValueError("history must contain the binary released proxy")
    return value


def project_view(arrays, role, arm):
    """Copy only selected fields; queries never look up target or persistence.

    Session cell axes are retained separately. No normalization, fitting, cell
    selection, additional target-derived metadata, or cross-session stacking is
    performed. Copies keep caller-owned arrays isolated from later output edits.
    """
    if role not in ROLES or arm not in ARMS:
        raise ValueError("unknown role or arm")
    result = {"history": _field(arrays, "history", (5, 300), binary=True).copy()}
    if arm != "history":
        name = "shifted" if arm == "shift" else "neural"
        value = arrays[name]
        if (type(value) is not np.ndarray or value.ndim != 3 or
                value.shape[:2] != (5, 300) or value.shape[2] < 1 or
                value.dtype.kind != "f" or value.dtype.itemsize != 8 or
                not np.isfinite(value).all()):
            raise ValueError("invalid selected neural array")
        result["neural"] = (value[:, ::-1, :] if arm == "reverse" else value).copy()
    if role == "train":
        target = _field(arrays, "target", (5,))
        if not ((0 <= target).all() and (target <= 1).all()):
            raise ValueError("training proxy fraction outside [0,1]")
        result["target"] = target.copy()
    return result
