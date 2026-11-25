"""Decode Pala source volts into millivolts without changing source rows.

This component repairs the source unit boundary only. It neither selects the
Figure 3 cohort nor defines its unresolved segment mapping or discrepancy score.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from typing import Mapping

import numpy as np
from scipy.io import loadmat

SOURCE_MD5 = "dc333d3d03b79460f2ec1d36122206c8"
SOURCE_URL = "https://zenodo.org/api/records/1304771/files/data.mat/content"
SOURCE_UNIT = "V"
OUTPUT_UNIT = "mV"
VOLTS_TO_MILLIVOLTS = 1000.0
FIELDS = (
    "Trial_MembranePotential", "Trial_MembranePotential_SamplingRate",
    "Trial_Type", "Cell_Type", "Mouse_Name", "Cell_Counter",
)


class SourceContractError(ValueError):
    """Source shape, identity, or units cannot be preserved safely."""


@dataclass(frozen=True)
class Trial:
    # These fields also satisfy the existing evaluator's trial interface.
    trial_id: str
    mouse_id: str
    cell_id: str
    cell_type: str
    trial_type: str
    sampling_hz: int
    voltage_mv: np.ndarray


@dataclass(frozen=True)
class SourceRecording:
    trials: tuple[Trial, ...]
    receipt: dict


def _text(value, name):
    if not isinstance(value, (str, np.str_)) or not value.strip():
        raise SourceContractError(f"{name} must be a nonempty source string")
    return str(value)  # Do not strip or otherwise normalize biological identities.


def decode_pala_volts(data: Mapping) -> tuple[Trial, ...]:
    """Decode a scipy simplify_cells Pala struct; input voltage is always volts.

    The unit follows the deposited analysis helper, not amplitude inference.
    This low-level function is also usable for generated source-format controls;
    it cannot authenticate a caller-supplied dict. Use load_pala for source data.
    """
    if not isinstance(data, Mapping) or any(name not in data for name in FIELDS):
        raise SourceContractError("expected the six aligned Pala source fields")
    try:
        columns = {name: np.asarray(data[name]) for name in FIELDS}
    except (TypeError, ValueError) as exc:
        raise SourceContractError("source fields must be aligned vectors") from exc
    voltage = columns[FIELDS[0]]
    if voltage.ndim != 1 or voltage.dtype != object or not len(voltage):
        raise SourceContractError("voltage must be a nonempty 1D MATLAB cell vector")
    n_trials = len(voltage)
    if any(column.ndim != 1 or len(column) != n_trials for column in columns.values()):
        raise SourceContractError("source fields must have one identical trial axis")

    trials = []
    for row in range(n_trials):
        fs = columns[FIELDS[1]][row]
        counter = columns[FIELDS[5]][row]
        for value, name in ((fs, "sampling rate"), (counter, "cell counter")):
            if (isinstance(value, (bool, np.bool_)) or
                    not isinstance(value, (int, float, np.integer, np.floating)) or
                    not np.isfinite(value)):
                raise SourceContractError(f"{name} must be a finite source number")
        if fs != 20000 or counter != int(counter):
            raise SourceContractError("expected 20 kHz and an integer cell counter")
        mouse = _text(columns[FIELDS[4]][row], "mouse identity")
        cell_type = _text(columns[FIELDS[3]][row], "cell type")
        trial_type = _text(columns[FIELDS[2]][row], "trial type")
        trace = np.asarray(voltage[row])
        if (trace.ndim not in (1, 2) or
                (trace.ndim == 2 and min(trace.shape) != 1) or
                trace.size < 2 or trace.dtype.kind not in "fiu"):
            raise SourceContractError("each voltage cell must be a real numeric row/column vector")
        if not np.isfinite(trace).all():
            raise SourceContractError("source voltage contains nonfinite samples; no rows are omitted")
        # The source helper multiplies by 1000 for mV and thresholds at -0.03 V.
        # Allocate a new array: never mutate the deposited source or caller arrays.
        with np.errstate(over="ignore", invalid="ignore"):
            voltage_mv = trace.reshape(-1).astype(np.float64) * VOLTS_TO_MILLIVOLTS
        if not np.isfinite(voltage_mv).all():
            raise SourceContractError("volts-to-millivolts conversion overflowed")
        voltage_mv.setflags(write=False)
        trials.append(Trial(
            f"pala-row-{row + 1:06d}", mouse, f"{mouse}_{int(counter)}",
            cell_type, trial_type, int(fs), voltage_mv,
        ))
    return tuple(trials)


def _source_state(handle):
    info = os.fstat(handle.fileno())
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def load_pala(path: str | Path) -> SourceRecording:
    """Authenticate the original data.mat, then decode source volts exactly once.

    No checksum bypass, download, cohort selection, trimming, or fitting occurs.
    MAT v7.3 support and the actual source payload schema remain unqualified.
    """
    md5, sha256 = hashlib.md5(), hashlib.sha256()
    with Path(path).open("rb") as handle:
        source_state = _source_state(handle)
        byte_count = 0
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            byte_count += len(block)
            md5.update(block)
            sha256.update(block)
        if md5.hexdigest() != SOURCE_MD5:
            raise SourceContractError("data.mat differs from the source-recorded MD5")
        if _source_state(handle) != source_state:
            raise SourceContractError("source changed during authentication")
        handle.seek(0)
        try:
            content = loadmat(handle, simplify_cells=True)
        except (NotImplementedError, ValueError) as exc:
            raise SourceContractError("MAT format/schema is unsupported; no cohort was prepared") from exc
        if _source_state(handle) != source_state:
            raise SourceContractError("source changed during MAT decoding")
    if "data" not in content:
        raise SourceContractError("missing source MATLAB data struct")
    trials = decode_pala_volts(content["data"])
    return SourceRecording(trials, {
        "source_url": SOURCE_URL, "source_md5": md5.hexdigest(),
        "source_sha256": sha256.hexdigest(), "source_bytes": byte_count,
        "source_voltage_unit": SOURCE_UNIT, "output_voltage_unit": OUTPUT_UNIT,
        "voltage_multiplier": VOLTS_TO_MILLIVOLTS, "source_rows": len(trials),
        "source_row_order_preserved": True, "cohort_selection_applied": False,
    })
