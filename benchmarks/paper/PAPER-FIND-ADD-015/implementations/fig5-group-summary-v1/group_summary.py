"""Figure 5 descriptive companions from the complete supplied keyed fit export.

No fitting, input-file loading, cell selection, inference or paper acceptance.
Both coefficient interpretations remain visible; neither is selected here.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
import types

import numpy as np
import scipy
from scipy import stats

GROUPS = ("activated", "suppressed")
ALIGNMENT_BYTES = 8509
ALIGNMENT_SHA256 = "97439fccb04a370de12a5f0555f3cd0916d56dea149959baf0af93ad6d2fab63"
QUANTITIES = ("preceding_slope", "literal_notebook_intercept", "conditional_model_intercept")


class SummaryError(ValueError):
    """The whole supplied panel cannot support the descriptive companion."""


def require(condition, message):
    if not condition:
        raise SummaryError(message)


def load_alignment(path):
    if path is None:
        path = Path(__file__).resolve().parent.parent / "fig5-coefficient-alignment-v1" / "coefficient_alignment.py"
    path = Path(path)
    with path.open("rb") as stream:
        raw = stream.read(ALIGNMENT_BYTES + 1)
    require(len(raw) == ALIGNMENT_BYTES and hashlib.sha256(raw).hexdigest() == ALIGNMENT_SHA256,
            "existing alignment source pin mismatch")
    module = types.ModuleType("_fig5_summary_alignment")
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def describe(values):
    """Use the notebook's unrounded mean and SciPy sample SEM operators."""
    array = np.asarray(values, dtype=np.float64)
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            mean = float(np.mean(array))
            # SciPy's n=1 SEM is undefined. Preserve that state, not a zero SEM.
            sem = float(stats.sem(array, ddof=1, nan_policy="propagate")) if len(values) > 1 else None
            rounded_mean = float(np.round(mean, decimals=2))
            rounded_sem = float(np.round(sem, decimals=2)) if sem is not None else None
    except (FloatingPointError, OverflowError) as exc:
        raise SummaryError("nonfinite descriptive arithmetic; no partial panel") from exc
    require(np.isfinite(mean) and (sem is None or np.isfinite(sem)),
            "nonfinite descriptive arithmetic; no partial panel")
    return {"values_in_supplied_cell_order": values, "cell_count": len(values),
            "mean": mean, "sem": sem,
            "sem_state": "defined" if sem is not None else "undefined_fewer_than_two_cells",
            "notebook_display_rounded_2_decimals": {"mean": rounded_mean, "sem": rounded_sem}}


def summarize_panel(exports, *, limits, alignment_source=None):
    """Describe both whole groups from export_panel(...)["exports"].

    The unchanged pinned diagnostic validates identities and emits both
    intercept branches. Complete coverage is relative to the supplied rosters;
    this function cannot authenticate original cells, animal joins or trials.
    Explicit limits refuse the complete panel instead of subsampling it.
    """
    require(type(limits) is dict and set(limits) == {"max_cells", "max_trial_rows", "max_output_bytes"},
            "exact complete-panel limits required")
    require(all(type(v) is int and v > 0 for v in limits.values()), "positive limits required")
    require(type(exports) is dict and set(exports) == set(GROUPS), "both original groups required")
    for group in GROUPS:
        panel = exports[group]
        require(type(panel) is dict, "group export must be a dictionary")
        for name, bound in (("expected_cell_ids", limits["max_cells"]),
                            ("conditional", limits["max_cells"]), ("random", limits["max_cells"]),
                            ("trial_covariates", limits["max_trial_rows"])):
            require(type(panel.get(name)) is list and 0 < len(panel[name]) <= bound,
                    name + ": complete-panel capacity exceeded or empty")
    diagnostic = load_alignment(alignment_source).diagnose_panel(exports)
    summaries = {}
    for group in GROUPS:
        rows = diagnostic[group]["rows"]
        summaries[group] = {
            "cell_ids": [row["cell_id"] for row in rows],
            "cell_count_relative_to_supplied_roster": len(rows),
            "quantities": {name: describe([row[name] for row in rows]) for name in QUANTITIES},
            "descriptive_unit": "cell_equal_weight_not_trial_or_animal",
        }
    result = {"schema_version": "fig5-complete-group-descriptive-companion/v1",
              "task_id": "PAPER-FIND-ADD-015", "groups": summaries,
              "diagnostic": diagnostic,
              "operators": {"mean": "numpy.mean", "sem": "scipy.stats.sem(ddof=1,nan_policy='propagate')",
                            "display": "numpy.round(decimals=2)", "finite_values_only": True},
              "runtime_record": {"python": platform.python_version(), "numpy": np.__version__,
                                 "scipy": scipy.__version__},
              "alignment_sha256": ALIGNMENT_SHA256,
              "original_cohort_authenticated": False, "historical_runtime_verified": False,
              "branch_selected": None, "animal_uncertainty_established": False,
              "scientific_qualification": False, "reproduction_accepted": None,
              "improvement_accepted": None}
    encoded = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
    require(len(encoded) <= limits["max_output_bytes"], "complete output capacity exceeded; no truncation")
    return result
