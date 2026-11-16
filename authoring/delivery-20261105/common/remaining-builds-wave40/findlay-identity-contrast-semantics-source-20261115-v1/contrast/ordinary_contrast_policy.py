"""Source-derived ordinary contrast mapping and narrow scalar policies; no I/O."""
from types import MappingProxyType
import math
import struct

DEFINITIONS = MappingProxyType({'Cortical.SWA.Rebound': ('Cortical.SWA', 'Early.REC.NREM', 'Late.BSL.NREM'), 'SPW.Rate.Rebound': ('SPW.Rate', 'Early.REC.NREM', 'Late.BSL.NREM'), 'SPW.Amplitude.Rebound': ('SPW.Amplitude', 'Early.REC.NREM', 'Late.BSL.NREM'), 'Ripple.Rate.Rebound': ('Ripple.Rate', 'Early.REC.NREM', 'Late.BSL.NREM'), 'Ripple.Frequency.Rebound': ('Ripple.Frequency', 'Early.REC.NREM', 'Late.BSL.NREM'), 'DSPK.Amplitude.Rebound': ('DSPK.Amplitude', 'Early.REC.NREM', 'Late.BSL.NREM'), 'Cortical.SWA.REC.Decline': ('Cortical.SWA', 'Early.REC.NREM', 'Late.REC.NREM'), 'SPW.Rate.REC.Decline': ('SPW.Rate', 'Early.REC.NREM', 'Late.REC.NREM'), 'SPW.Amplitude.REC.Decline': ('SPW.Amplitude', 'Early.REC.NREM', 'Late.REC.NREM'), 'Ripple.Rate.REC.Decline': ('Ripple.Rate', 'Early.REC.NREM', 'Late.REC.NREM'), 'Ripple.Frequency.REC.Decline': ('Ripple.Frequency', 'Early.REC.NREM', 'Late.REC.NREM'), 'DSPK.Amplitude.REC.Decline': ('DSPK.Amplitude', 'Early.REC.NREM', 'Late.REC.NREM'), 'Cortical.SWA.Surge': ('Cortical.SWA', 'Early.REC.NREM', 'Early.BSL.NREM'), 'SPW.Rate.Surge': ('SPW.Rate', 'Early.REC.NREM', 'Early.BSL.NREM'), 'SPW.Amplitude.Surge': ('SPW.Amplitude', 'Early.REC.NREM', 'Early.BSL.NREM'), 'Ripple.Rate.Surge': ('Ripple.Rate', 'Early.REC.NREM', 'Early.BSL.NREM'), 'Ripple.Duration.Surge': ('Ripple.Duration', 'Early.REC.NREM', 'Early.BSL.NREM'), 'Ripple.Frequency.Surge': ('Ripple.Frequency', 'Early.REC.NREM', 'Early.BSL.NREM'), 'DSPK.Amplitude.Surge': ('DSPK.Amplitude', 'Early.REC.NREM', 'Early.BSL.NREM'), 'DSPK.Rate.Surge': ('DSPK.Rate', 'Early.REC.NREM', 'Early.BSL.NREM'), 'Cortical.SWA.BSL.Decline': ('Cortical.SWA', 'Early.BSL.NREM', 'Late.BSL.NREM'), 'SPW.Rate.BSL.Decline': ('SPW.Rate', 'Early.BSL.NREM', 'Late.BSL.NREM'), 'SPW.Amplitude.BSL.Decline': ('SPW.Amplitude', 'Early.BSL.NREM', 'Late.BSL.NREM'), 'Ripple.Rate.BSL.Decline': ('Ripple.Rate', 'Early.BSL.NREM', 'Late.BSL.NREM'), 'Ripple.Frequency.BSL.Decline': ('Ripple.Frequency', 'Early.BSL.NREM', 'Late.BSL.NREM'), 'DSPK.Amplitude.BSL.Decline': ('DSPK.Amplitude', 'Early.BSL.NREM', 'Late.BSL.NREM'), 'DSPK.Rate.BSL.Decline': ('DSPK.Rate', 'Early.BSL.NREM', 'Late.BSL.NREM')})
EXCLUDED_COLUMNS = frozenset(['Cortical.SWA.BSL.Decline', 'Cortical.SWA.Rebound', 'DSPK.Amplitude.BSL.Decline', 'DSPK.Amplitude.Rebound', 'DSPK.Rate.BSL.Decline', 'Ripple.Frequency.BSL.Decline', 'Ripple.Frequency.Rebound', 'Ripple.Rate.BSL.Decline', 'Ripple.Rate.Rebound', 'SPW.Amplitude.BSL.Decline', 'SPW.Amplitude.Rebound', 'SPW.Rate.BSL.Decline', 'SPW.Rate.Rebound'])

EXCLUSION_IDENTITY = None

def configure_private_policy(policy):
    global EXCLUSION_IDENTITY
    value = policy["ordinary_exclusion"]
    if frozenset(value["columns"]) != EXCLUDED_COLUMNS:
        raise ValueError("Unchanged thirteen exclusion columns required")
    EXCLUSION_IDENTITY = (value["subject"], value["experiment"])

def expected_export_exclusion_status(subject, experiment, column, stored_value):
    if EXCLUSION_IDENTITY is None:
        raise ValueError("Admitted private exclusion identity required")
    if column not in DEFINITIONS:
        raise ValueError("Unknown source-bound ordinary contrast")
    if (subject, experiment) != EXCLUSION_IDENTITY or column not in EXCLUDED_COLUMNS:
        return None
    absent = stored_value is None or (type(stored_value) is float and math.isnan(stored_value))
    return "expected_export_exclusion" if absent else "export_exclusion_mismatch"

def subtract_source_dtype(column, minuend, subtrahend, source_dtype, target_dtype):
    """No tolerance: source-declared same-dtype IEEE subtraction on decoded scalars.

    Caller must bind the authentic footer schemas and check unique source keys.
    This helper never handles missing/source-excluded cells as zero values.
    """
    if column not in DEFINITIONS:
        raise ValueError("Unknown source-bound ordinary contrast")
    expected = "float32" if DEFINITIONS[column][0] == "Cortical.SWA" else "float64"
    if (source_dtype, target_dtype) != (expected, expected):
        raise ValueError("Verified source/target dtype required")
    if any(type(x) is not float or not math.isfinite(x) for x in (minuend, subtrahend)):
        raise ValueError("Finite decoded floating operands required")
    if expected == "float32":
        def f32(x):
            try:
                return struct.unpack("!f", struct.pack("!f", x))[0]
            except (OverflowError, struct.error) as exc:
                raise ValueError("Binary32 overflow") from exc
        if f32(minuend) != minuend or f32(subtrahend) != subtrahend:
            raise ValueError("Operands must be exact decoded binary32 values")
        result = f32(minuend - subtrahend)
    else:
        result = minuend - subtrahend
    if not math.isfinite(result):
        raise ValueError("Nonfinite subtraction")
    return result
