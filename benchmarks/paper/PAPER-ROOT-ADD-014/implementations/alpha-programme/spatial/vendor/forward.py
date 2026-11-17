"""Pure GS/OG forward arithmetic; no fitting, file I/O, or native parity claim.

Source: analyzePRFdog.m (bounds 423-430, reported parameters 911-916),
modeldogcss.m (75-111), makegaussian2d.m (pixel coordinates), and amppow.m.
Frozen branch: N=1, h=1, SR=infinity (GS); GR=0 (OG). For GS,
SS=1/sqrt(1-log2(1+GR)), GS=1/(1-GR). Both Gaussian integrals use
2*pi*S**2, NOT 2*pi*(S*SS)**2. The infinite surround is a uniform field
within the supplied aperture; its response follows each frame's signed sum.

Input is rows x columns x frames, square in this paper (100 x 100 x 75).
Small square fixtures are allowed. One-based row/column parameters and MATLAB
column-major pixel flattening are explicit. Float64 evaluation is independent
source arithmetic, not MATLAB optimizer or bitwise reproduction. The SS
denominator and combined center-minus-surround kernel use log1p/expm1
identities to avoid cancellation near GR=1; this is a transparent numerical
improvement over the source's separate large products. S=0, GR=1,
and unrepresentable arithmetic return an explicit unsupported disposition;
this is a prospective guard, not a source result or dropped electrode.
"""
import math

import numpy as np


def _real_array(value, name):
    a = np.asarray(value)
    if a.dtype.kind not in "fiu" or a.dtype.itemsize > 8:
        raise ValueError(name + " must contain primitive real numbers")
    with np.errstate(over="raise", invalid="raise"):
        try:
            a = a.astype(np.float64, copy=False)
        except FloatingPointError as exc:
            raise ValueError(name + " cannot be represented in float64") from exc
    if not np.isfinite(a).all():
        raise ValueError(name + " must be finite")
    return a


def _unsupported(reason):
    return {"status": "unsupported", "reason": reason,
            "prospective_guard": True, "prediction": None, "geometry": None}


def evaluate(stimulus, parameters, *, model="GS", allow_negative_gain=False,
             stimulus_width_deg=16.6):
    """Evaluate one [row,column,S,G,GR] row, returning predictions + geometry.

    Invalid schema/out-of-source-bounds arguments raise ValueError. Valid bound
    endpoints with undefined source arithmetic return status='unsupported'.
    No normalization, clipping, stimulus binarization, HRF, or intercept is added.
    Negative G is admitted only under the explicitly requested sign-free branch.
    """
    a = _real_array(stimulus, "stimulus")
    p = _real_array(parameters, "parameters")
    if a.ndim != 3 or a.shape[0] != a.shape[1] or min(a.shape) < 1:
        raise ValueError("stimulus must be nonempty square rows x columns x frames")
    if p.shape != (5,):
        raise ValueError("parameters must be [row,column,S,G,GR]")
    if model not in ("GS", "OG") or type(allow_negative_gain) is not bool:
        raise ValueError("model/allow_negative_gain policy")
    width = _real_array(stimulus_width_deg, "stimulus_width_deg")
    if width.shape != () or width <= 0:
        raise ValueError("stimulus_width_deg must be positive scalar")
    r, c, s, g, gr = map(float, p)
    res = a.shape[0]
    lower, upper = 1-res/2, 1.5*res
    if not (lower <= r <= upper and lower <= c <= upper):
        raise ValueError("center outside source forcebounds=2/default boundsecc")
    if s < 0 or not 0 <= gr <= 1 or (g < 0 and not allow_negative_gain):
        raise ValueError("source S/G/GR bounds")
    if model == "OG" and gr != 0:
        raise ValueError("OG requires GR=0; no silent parameter repair")
    if s == 0:
        return _unsupported("zero_S_source_normalization_undefined")
    if gr == 1:
        return _unsupported("unit_GR_source_gain_and_width_undefined")
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise",
                         under="ignore"):
            # For SR=infinity the source SS iteration is already at this limit.
            delta = 1-gr
            # 1-log2(1+GR) = -log1p(-(1-GR)/2)/log(2).
            # The direct expression rounds to zero at nextafter(1,0).
            ss = 1 / np.sqrt(-np.log1p(-delta/2)/np.log(2.0))
            gs = 1 / delta
            physical_sigma = np.float64(s)*ss
            denominator = 2*np.pi*np.float64(s)**2
            if physical_sigma == 0 or denominator == 0:
                return _unsupported("source_width_or_normalization_underflow")
            rows, cols = np.meshgrid(np.arange(1,res+1,dtype=float),
                                     np.arange(1,res+1,dtype=float),indexing="ij")
            exponent = (-0.5*((rows-r)/physical_sigma)**2
                        -0.5*((cols-c)/physical_sigma)**2)
            # MATLAB stimulus rows are frames; each column is vflatten(image).
            design = a.reshape((res*res, a.shape[2]), order="F").T
            # (exp(exponent)-GR)/(1-GR) = 1+expm1(exponent)/delta.
            # Combining before the signed stimulus projection avoids subtracting
            # huge nearly equal center/surround responses. amppow(z,1)=z.
            # Away from GR=1 use exp directly so the OG/small-GR positive
            # far tail is not rounded away by 1+expm1(large negative).
            if gr <= .5:
                normalized = (np.exp(exponent)-gr)/delta
            else:
                normalized = 1+np.expm1(exponent)/delta
            kernel = normalized*(g/denominator)
            prediction = design @ kernel.reshape(-1,order="F")
            deg_per_pixel = np.float64(width)/res
            x = (c-(res+1)/2)*deg_per_pixel
            y = ((res+1)/2-r)*deg_per_pixel
            geometry = {"row_1based":r,"column_1based":c,
                        "x_deg":float(x),"y_deg":float(y),
                        "eccentricity_deg":float(np.hypot(x,y)),
                        "polar_angle_deg":float(np.degrees(np.arctan2(y,x)) % 360),
                        "reported_size_pixels":s,
                        "reported_size_deg":float(s*deg_per_pixel),
                        "physical_center_sigma_pixels":float(physical_sigma),
                        "physical_center_sigma_deg":float(physical_sigma*deg_per_pixel),
                        "sigma_scale":float(ss),"gain_scale":float(gs),
                        "gain":g,"gain_ratio":gr,"exponent":1,
                        "hrf":"identity","surround_sigma":"infinity" if gr else "OG"}
    except (FloatingPointError, OverflowError, ZeroDivisionError):
        return _unsupported("source_arithmetic_not_representable_float64")
    numeric = [v for v in geometry.values() if isinstance(v,(int,float))]
    if not np.isfinite(prediction).all() or not all(math.isfinite(v) for v in numeric):
        return _unsupported("source_arithmetic_not_representable_float64")
    return {"status":"defined","reason":None,"prospective_guard":False,
            "prediction":prediction,"geometry":geometry}
