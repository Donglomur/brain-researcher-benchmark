"""PROSPECTIVE source-free PR191 arithmetic/typed primitives, not task code.

No source reader, bank, oracle imports or import-time execution. Tolerances below
are explicit CANDIDATES pending parent freeze. Source support is supplied by a
trusted reconstruction; this module cannot authenticate a source by itself.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import math
import numpy as np

RAW_ATOL, RAW_RTOL = 1e-5, 1e-6
SIGNAL_ATOL, SIGNAL_RTOL = 1e-7, 1e-7
CENTERED_RELATIVE = 1e-6
RECEIPT_ATOL = 1e-6
CORRELATION_ROUNDOFF = 1e-12  # arithmetic excursion check, never a tie epsilon
SUBJECT = "0010064"
TARGETS = ("R DMN", "Cereb")
INT_MIN, INT_MAX = -(2**63), 2**63-1


def require(ok, message):
    if not ok: raise ValueError(message)


def integer(value, *, csv=False):
    allowed = (str, int, float, Decimal, np.integer, np.floating) if csv else (int, float, Decimal, np.integer, np.floating)
    require(isinstance(value, allowed) and not isinstance(value, (bool, np.bool_)), "integer type")
    try: parsed = Decimal(str(value))
    except InvalidOperation as exc: raise ValueError("integer syntax") from exc
    require(parsed.is_finite() and INT_MIN <= parsed <= INT_MAX, "integer finite/range")
    require(parsed == parsed.to_integral_value(), "integer fractional")
    return int(parsed)


def number(value, *, csv=False):
    allowed = (str, int, float, Decimal, np.integer, np.floating) if csv else (int, float, Decimal, np.integer, np.floating)
    require(isinstance(value, allowed) and not isinstance(value, (bool, np.bool_)), "number type")
    try: result = float(value)
    except (ValueError, OverflowError) as exc: raise ValueError("number syntax/range") from exc
    require(math.isfinite(result), "number finite")
    return result


def finite_json(value, depth=0):
    require(depth <= 64, "JSON depth")
    if value is None or type(value) in (str, bool): return
    if isinstance(value, (int, float, Decimal)):
        number(value); return
    if isinstance(value, list):
        for child in value: finite_json(child, depth+1)
        return
    require(isinstance(value, dict) and all(type(k) is str for k in value), "JSON type/keys")
    for child in value.values(): finite_json(child, depth+1)


def real_array(value, ndim=None):
    # Inspect sequence element types before NumPy can coerce mixed [1, True].
    if not isinstance(value, np.ndarray):
        probe=np.asarray(value, dtype=object)
        require(all(isinstance(x, (int,float,np.integer,np.floating)) and not isinstance(x,(bool,np.bool_))
                    for x in probe.flat), "real array element type")
    arr=np.asarray(value)
    require(arr.dtype.fields is None and arr.dtype.kind in "iuf", "real array dtype")
    require(ndim is None or arr.ndim==ndim, "real array dimensions")
    arr=arr.astype(np.float64)
    require(np.isfinite(arr).all(), "real array finite")
    return arr


def integer_axis(value, expected):
    if not isinstance(value,np.ndarray):
        require(all(not isinstance(x,(bool,np.bool_)) for x in np.asarray(value,dtype=object).flat), "integer axis Boolean")
    arr=np.asarray(value)
    require(arr.ndim==1 and arr.dtype.kind in "iuf", "integer axis type/shape")
    parsed=[integer(x) for x in arr]
    require(len(parsed)==len(expected) and len(set(parsed))==len(parsed) and set(parsed)==set(expected), "integer axis membership")
    return np.asarray([parsed.index(x) for x in expected],dtype=np.int64)


def strings(value, ndim=1):
    arr=np.asarray(value)
    require(arr.ndim==ndim and arr.dtype.kind in "US", "literal string shape/type")
    try: decoded=np.char.decode(arr,"utf-8") if arr.dtype.kind=="S" else arr.astype(str)
    except UnicodeError as exc: raise ValueError("invalid UTF8") from exc
    require(np.all(decoded!=""), "empty literal string")
    return decoded


def center_scaled(value, *, scale=None):
    """Center once, using fsum and positive prescaling for finite arithmetic.

    Computational convention: divide by max absolute input first, then subtract
    fsum(scaled)/N. Exact input constants become literal zero. Centering is not
    repeated after rolling. Explicit shared scale is used for fidelity checks.
    """
    value=real_array(value,1)
    require(len(value)>0, "empty series")
    if np.all(value==value[0]): return np.zeros_like(value)
    scale=float(np.max(np.abs(value))) if scale is None else float(scale)
    require(math.isfinite(scale) and scale>0, "centering scale")
    scaled=value/scale
    return scaled-math.fsum(float(x) for x in scaled)/len(scaled)


def stable_l2(value):
    value=real_array(value,1)
    peak=float(np.max(np.abs(value))) if len(value) else 0.
    if peak==0: return 0.
    result=peak*math.sqrt(math.fsum(float(x/peak)**2 for x in value))
    require(math.isfinite(result), "nonfinite L2")
    return result


def close_array(actual, expected, atol, rtol, name):
    actual,expected=real_array(actual),real_array(expected)
    require(actual.shape==expected.shape, name+": shape")
    require(np.all(np.abs(actual-expected)<=atol+rtol*np.abs(expected)), name+": source precision")
    return actual


def active_mask(active):
    value=np.asarray(active)
    require(value.shape==(2,) and value.dtype.kind=="b", "canonical active mask")
    return value


def signal_fidelity(actual, reference, active):
    actual=close_array(actual,reference,SIGNAL_ATOL,SIGNAL_RTOL,"cleaned series")
    reference=real_array(reference,2);active=active_mask(active)
    require(actual.ndim==2 and actual.shape[1]==2, "two cleaned components")
    for column in range(2):
        if not active[column]: continue
        scale=max(float(np.max(np.abs(actual[:,column]))),float(np.max(np.abs(reference[:,column]))))
        require(scale>0, "active source cannot be constant zero")
        candidate=center_scaled(actual[:,column],scale=scale)
        target=center_scaled(reference[:,column],scale=scale)
        norm=stable_l2(target)
        require(norm>0, "active source cannot be constant")
        require(stable_l2(candidate-target)<=CENTERED_RELATIVE*norm, "centered source fidelity")
    return actual


def canonical_primitives(raw_receipt, timeseries_rows, basis):
    """Join literal source keys; source basis is grader-owned, never submitted.

    This five-artifact proposal uses all39 raw coefficients and only two cleaned
    CSV columns; downstream processing never re-cleans rounded raw receipts.
    """
    require(isinstance(raw_receipt,dict) and {"participant_id","frame_indices","map_ids","map_labels","raw_coefficients"}<=set(raw_receipt), "required raw receipt keys")
    subject=basis["participant_id"]
    require(subject==SUBJECT, "fixed literal subject")
    require(strings(raw_receipt["participant_id"],0).item()==subject, "subject identity")
    expected_frames=list(range(len(basis["cleaned_series"])))
    require(len(expected_frames)>=4, "at least four frames")
    require(list(basis["frame_indices"])==expected_frames, "canonical chronological frames")
    expected_maps=list(range(39))
    require(list(basis["map_ids"])==expected_maps, "all39 source maps")
    frame_order=integer_axis(raw_receipt["frame_indices"],expected_frames)
    map_order=integer_axis(raw_receipt["map_ids"],expected_maps)
    labels=strings(raw_receipt["map_labels"])
    require(labels.shape==(39,) and np.array_equal(labels[map_order],basis["map_labels"]), "literal map labels")
    require(tuple(basis["target_labels"])==TARGETS, "target component order")
    require(all(list(basis["map_labels"]).count(label)==1 for label in TARGETS), "unique target source labels")
    raw=real_array(raw_receipt["raw_coefficients"],2)
    require(raw.shape==(len(expected_frames),39), "raw39 shape")
    raw=close_array(raw[np.ix_(frame_order,map_order)],basis["raw_coefficients"],RAW_ATOL,RAW_RTOL,"raw coefficients")
    require(isinstance(timeseries_rows,list) and len(timeseries_rows)==len(expected_frames), "complete frame rows")
    keyed={}
    for row in timeseries_rows:
        require(isinstance(row,dict) and {"frame_index",*TARGETS}<=set(row), "required series columns")
        key=integer(row["frame_index"],csv=True)
        require(key not in keyed, "duplicate frame")
        keyed[key]=[number(row[label],csv=True) for label in TARGETS]
    require(set(keyed)==set(expected_frames), "complete exact frame keys")
    clean=np.asarray([keyed[k] for k in expected_frames],dtype=np.float64)
    clean=signal_fidelity(clean,basis["cleaned_series"],basis["active"])
    return raw,clean


def strict_alpha(numerator, denominator):
    numerator,denominator=integer(numerator),integer(denominator)
    require(denominator>=4 and 1<=numerator<=denominator, "rank fraction domain")
    return 20*numerator<denominator


def circular_evidence(cleaned, active):
    clean=real_array(cleaned,2);active=active_mask(active)
    require(clean.shape[1]==2 and len(clean)>=4, "complete two-series support")
    n=len(clean);shifts=list(range(1,n))
    inference=dict(method="circular_shift_all",shifted_region=TARGETS[0],shift_direction="positive_np_roll",
                   shifts=shifts,null_r=[None]*(n-1),exceeds=[None]*(n-1),n_exceedances=None,
                   numerator=None,denominator=n,alpha=.05,p_value=None,significant=None,
                   inactive_regions=[name for name,ok in zip(TARGETS,active) if not ok])
    output=dict(subject=SUBJECT,region_a=TARGETS[0],region_b=TARGETS[1],n_timepoints=n,
                status="ok" if active.all() else "inactive_target",r=None,p_value=None,significant=None,inference=inference)
    inference["status"]=output["status"]
    if not active.all(): return output
    x,y=(center_scaled(clean[:,column]) for column in range(2))
    norms=stable_l2(x)*stable_l2(y)
    require(norms>0 and math.isfinite(norms), "active submitted pair has undefined norms")
    def dot(k):
        return math.fsum(float(x[(t-k)%n])*float(y[t]) for t in range(n))
    dots=[dot(k) for k in range(n)]
    rs=[value/norms for value in dots]
    require(all(math.isfinite(v) and abs(v)<=1+CORRELATION_ROUNDOFF for v in rs), "correlation arithmetic")
    rs=[min(1.,max(-1.,v)) for v in rs]
    exceeds=[abs(value)>=abs(dots[0]) for value in dots[1:]]
    count=sum(exceeds);numerator=1+count;p=numerator/n;significant=strict_alpha(numerator,n)
    inference.update(null_r=rs[1:],exceeds=exceeds,n_exceedances=count,numerator=numerator,
                     p_value=p,significant=significant)
    output.update(r=rs[0],p_value=p,significant=significant)
    return output


def same_scalar(actual, expected, name):
    if expected is None: require(actual is None,name+": null required")
    elif type(expected) is bool: require(type(actual) is bool and actual==expected,name+": Boolean exact")
    elif type(expected) is int: require(integer(actual)==expected,name+": integer exact")
    elif type(expected) is str: require(type(actual) is str and actual==expected,name+": literal exact")
    else:
        value=number(actual)
        require(abs(value-expected)<=RECEIPT_ATOL,name+": numeric precision")
        if name in ("r","null_r"): require(-1<=value<=1,name+": correlation domain")
        if name=="p_value": require(0<=value<=1,"p domain")


def validate_report(report, expected):
    """Validate own-series replay, not a second canonical-source p/label target."""
    finite_json(report)
    require(isinstance(report,dict) and set(expected)<=set(report), "required result fields")
    for key in expected:
        if key!="inference":same_scalar(report[key],expected[key],key)
    have,want=report["inference"],expected["inference"]
    require(isinstance(have,dict) and set(want)<=set(have), "required inference fields")
    for key in want:
        if key not in ("shifts","null_r","exceeds","inactive_regions","alpha"):
            same_scalar(have[key],want[key],key)
    require(number(have["alpha"])==.05,"exact alpha")
    require(isinstance(have["inactive_regions"],list) and have["inactive_regions"]==want["inactive_regions"],"inactive target identities")
    require(isinstance(have["shifts"],list), "shift list")
    shifts=[integer(k) for k in have["shifts"]]
    require(len(shifts)==len(want["shifts"]) and len(set(shifts))==len(shifts) and set(shifts)==set(want["shifts"]),"complete unique nonzero shifts")
    for field in ("null_r","exceeds"):
        require(isinstance(have[field],list) and len(have[field])==len(shifts),field+": complete paired support")
        keyed=dict(zip(shifts,have[field]))
        for k,value in zip(want["shifts"],want[field]): same_scalar(keyed[k],value,field)
    return dict(status="accepted",inference_status=expected["status"],n_frames=expected["n_timepoints"])


def validate_submission(raw_receipt, rows, report, basis):
    _,clean=canonical_primitives(raw_receipt,rows,basis)
    return validate_report(report,circular_evidence(clean,basis["active"]))
