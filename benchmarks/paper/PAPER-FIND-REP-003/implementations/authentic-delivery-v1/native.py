"""Optional SciPy adapters. The standard-library grader also accepts JSON."""
from __future__ import annotations
import math
from collections import Counter
from pathlib import Path

from contract import DATA_SHA, SESSIONS, ContractError, digest, index_trials, require


def extract(path):
    require(Path(path).stat().st_size == 9351260 and digest(path) == DATA_SHA, "native data pin mismatch")
    try:
        from scipy.io import loadmat
    except ImportError as error:
        raise ContractError("SciPy is required for native MAT preparation; nothing was installed") from error
    native = loadmat(path, simplify_cells=True)
    require("optoData" in native and isinstance(native["optoData"], list), "optoData struct array missing")
    rows = []
    for trial in native["optoData"]:
        row = dict(mouse=trial["animalID"], session=trial["date"], trial_number=trial["trialNumber"])
        for field in ("success", "optoProblem", "optoTrial", "wrongGrabFirst", "grabTimeC", "liftTimeC"):
            value = trial[field]
            if field in ("grabTimeC", "liftTimeC") and isinstance(value, float) and math.isnan(value):
                value = None
            row[field] = value
        rows.append(row)
    keyed = index_trials(rows)
    require(len(keyed) == 3304, "all 3304 native trials required")
    require(Counter(k[:2] for k in keyed) == SESSIONS, "complete native eight-session roster required")
    # The immutable file pin authenticates trial identities beyond these roster summaries.
    return rows


def read_submission(path):
    """Read a MATLAB struct named submission using the documented JSON field names."""
    require(Path(path).stat().st_size <= 32 * 1024 * 1024, "MAT submission exceeds 32 MiB")
    try:
        import numpy as np
        from scipy.io import loadmat
    except ImportError as error:
        raise ContractError("SciPy is required only for MATLAB submission ingestion") from error
    def convert(value):
        if isinstance(value, dict):
            return {key: convert(item) for key, item in value.items()}
        if isinstance(value, np.ndarray):
            return convert(value.tolist())
        if isinstance(value, (tuple, list)):
            return [convert(item) for item in value]
        if isinstance(value, np.generic):
            return convert(value.item())
        return value
    native = loadmat(path, simplify_cells=True)
    require(set(k for k in native if not k.startswith("__")) == {"submission"}, "MAT must contain only submission")
    value = convert(native["submission"])
    require(type(value) is dict and type(value.get("trials")) is list, "submission must be a struct with trials struct array")
    for row in value["trials"]:
        # MATLAB has no JSON null; NaN is permitted only for excluded contacts.
        if isinstance(row.get("contact_seconds"), float) and math.isnan(row["contact_seconds"]):
            row["contact_seconds"] = None
        # MATLAB commonly represents integer scalar metadata as double.
        for field in ("trial_number", "selected"):
            item = row.get(field)
            if type(item) is float and math.isfinite(item) and item.is_integer():
                row[field] = int(item)
    for hist in value.get("histograms", {}).values():
        for field in ("selected_trials", "outside_display_window"):
            item = hist.get(field)
            if type(item) is float and math.isfinite(item) and item.is_integer():
                hist[field] = int(item)
        if type(hist.get("counts")) is list:
            hist["counts"] = [int(x) if type(x) is float and math.isfinite(x) and x.is_integer() else x for x in hist["counts"]]
    return value
