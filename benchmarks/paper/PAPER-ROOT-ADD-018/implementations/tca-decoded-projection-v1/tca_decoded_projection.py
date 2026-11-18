"""Project complete decoded S/SU fields into the existing OFC TCA transform.

This module does not open MAT files, authenticate source bytes, fit a model or
write results.  Its supported input is the structured-array representation from
scipy.io.loadmat(struct_as_record=True, squeeze_me=False).  Decoding itself must
be independently admitted and bounded before this operator-only projection.
"""
import math
import re

import numpy as np

EVENTS = ("COFF", "SON", "SOFF", "Rew", "Opt")


class ProjectionError(ValueError):
    """Unsupported source representation; never permission to drop a session."""


def _need(condition, message):
    if not condition:
        raise ProjectionError(message)


def _struct(value, label):
    _need(isinstance(value, np.ndarray) and value.dtype.names is not None,
          label + " must be an unsqueezed MATLAB scalar struct")
    _need(value.shape == (1, 1), label + " must have shape (1, 1)")
    return value[0, 0]


def _field(record, name, label):
    _need(name in record.dtype.names, label + " missing " + name)
    return record[name]


class _CopyBudget:
    def __init__(self, maximum):
        _need(type(maximum) is int and maximum > 0,
              "positive operator-selected max_projected_elements required")
        self.maximum = maximum
        self.used = 0
        self.dtypes = {}

    def numeric(self, value, label, *, logical=False):
        _need(isinstance(value, np.ndarray) and value.ndim == 2,
              label + " must retain its two MATLAB dimensions")
        allowed = "iufb" if logical else "iuf"
        _need(value.dtype.kind in allowed, label + " must be primitive real numeric")
        _need(value.dtype.itemsize <= 8,
              label + " extended precision requires a separately qualified projection")
        _need(self.used + value.size <= self.maximum,
              "projected-element budget exceeded; no partial session returned")
        self.used += value.size
        self.dtypes[label] = value.dtype.str
        return value


def _vector(value, label, budget, *, logical=False):
    a = budget.numeric(value, label, logical=logical)
    _need(a.size > 0 and 1 in a.shape, label + " must be a nonempty MATLAB vector")
    # MATLAB linear indexing is column-major. For either row or column vectors
    # this preserves original trial order rather than sorting observations.
    return [int(x) if a.dtype.kind in "iub" else float(x)
            for x in a.ravel(order="F")]


def _cluster(value, label, budget):
    a = budget.numeric(value, label)
    _need(a.shape == (1, 1), label + " must be a scalar")
    x = a[0, 0].item()
    if isinstance(x, float):
        _need(math.isfinite(x) and x >= 0 and x.is_integer(),
              label + " must be a finite nonnegative integral identifier")
    else:
        _need(x >= 0, label + " must be nonnegative")
    # Never route an integer identifier through binary64; uint64 labels above
    # 2**53 otherwise lose identity during an apparently harmless conversion.
    return int(x)


def project_decoded(decoded, *, identity, source_binding,
                    max_projected_elements):
    """Return one full session plus projection provenance, without source I/O.

    identity must supply session_id, animal_id and Expert/Naive cohort. No
    animal/session identity is guessed from filenames. source_binding carries
    an externally verified SHA256 and decoder identifier; this function checks
    syntax only and explicitly does not authenticate either assertion.

    max_projected_elements bounds copied primitive elements, not the memory
    already used by the external decoder or the Python list representation.
    All five event matrices retain every trial and every column, including
    violations and columns outside the TCA crop. NaN/Inf values are retained
    for the existing transform's explicit missing/nonfinite policy.
    """
    _need(type(identity) is dict and set(identity) ==
          {"session_id", "animal_id", "cohort"}, "explicit exact identity fields required")
    _need(all(type(x) is str and bool(x) for x in identity.values()),
          "nonempty identity strings required")
    _need(identity["cohort"] in ("Expert", "Naive"), "unsupported cohort")
    _need(type(source_binding) is dict and set(source_binding) ==
          {"source_sha256", "decoder_id"}, "exact external source binding required")
    _need(type(source_binding["source_sha256"]) is str and
          re.fullmatch(r"[0-9a-f]{64}", source_binding["source_sha256"]),
          "source SHA256 syntax required")
    _need(type(source_binding["decoder_id"]) is str and source_binding["decoder_id"],
          "external decoder identifier required")
    _need(type(decoded) is dict and "S" in decoded and "SU" in decoded,
          "decoded S and SU required")
    budget = _CopyBudget(max_projected_elements)
    s = _struct(decoded["S"], "S")
    blocks = _vector(_field(s, "Block", "S"), "S.Block", budget)
    _need(all(x in (1, 2, 3) for x in blocks), "unmapped source block")
    units = decoded["SU"]
    _need(isinstance(units, np.ndarray) and units.ndim == 2 and
          units.dtype.names is not None, "SU must be an unsqueezed struct vector")
    _need(units.size == 0 or 1 in units.shape,
          "nonvector SU requires original MATLAB length/indexing resolution")
    rows = list(units.ravel(order="F"))
    projected_units = []
    for i, unit in enumerate(rows):
        label = "SU[" + str(i + 1) + "]"
        projected_units.append({"cluster_id": _cluster(
            _field(unit, "cluster_id", label), label + ".cluster_id", budget)})
    ids = [x["cluster_id"] for x in projected_units]
    _need(len(ids) == len(set(ids)), "duplicate within-session cluster identifiers")
    transitions = sum(a != b for a, b in zip(blocks, blocks[1:]))
    excluded = len(rows) < 5 or transitions < 4
    session = {**identity, "S": {"Block": blocks}, "SU": projected_units}
    if not excluded:
        vios = _vector(_field(s, "vios", "S"), "S.vios", budget, logical=True)
        _need(len(vios) == len(blocks) and all(x in (0, 1) for x in vios),
              "complete source Block/vios trial join required")
        session["S"]["vios"] = vios
        xvec = _struct(_field(rows[0], "xvec", "SU[1]"), "SU[1].xvec")
        axis = _vector(_field(xvec, "COFF", "SU[1].xvec"),
                       "SU[1].xvec.COFF", budget)
        projected_units[0]["xvec"] = {"COFF": axis}
        for i, unit in enumerate(rows):
            label = "SU[" + str(i + 1) + "]"
            hmat = _struct(_field(unit, "hmat", label), label + ".hmat")
            matrices = {}
            for event in EVENTS:
                a = budget.numeric(_field(hmat, event, label + ".hmat"),
                                   label + ".hmat." + event)
                _need(a.shape[0] == len(blocks) and a.shape[1] > 0,
                      "complete uncropped source trial axis required for " + label + ".hmat." + event)
                # .tolist() preserves both dimensions, signed zero, finite
                # floating values and NaN/Inf; no squeeze/crop/imputation.
                matrices[event] = a.tolist()
            projected_units[i]["hmat"] = matrices
    return {
        "schema": "ofc-complete-decoded-tca-projection/v1",
        "session": session,
        "source_binding": dict(source_binding),
        "source_authentication": "external_not_verified_by_projection",
        "decoder_native_equivalence": False,
        "whole_task_complete": False,
        "projection": {
            "source_units": len(rows), "source_trials": len(blocks),
            "source_block_transitions": transitions,
            "source_excluded": excluded,
            "source_exclusion": {"fewer_than_five_units": len(rows) < 5,
                                 "fewer_than_four_transitions": transitions < 4},
            "event_order": list(EVENTS) if not excluded else [],
            "axis_source": "SU[1].xvec.COFF" if not excluded else None,
            "copied_elements": budget.used,
            "source_dtypes": budget.dtypes,
        },
    }
