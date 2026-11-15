"""Fixed, independent stdlib comparator; no protected reference imports.

Exact binary64-to-rational position means followed by a prospective 100-digit
Decimal approximation. This is a competent numerical baseline, not a proof of
correct rounding, MATLAB parity, population inference or novel performance.
"""
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

SHAPE = (4, 62, 2, 7, 28, 15)
WORDS = 1458240
PRECISION = 100
SERIES_TERMS = 96

def group(values):
    if len(values) != 15 or any(math.isinf(v) or (not math.isnan(v) and abs(v)>1000) for v in values):
        raise ValueError('complete finite-domain original position group required')
    finite = [Fraction.from_float(v) for v in values if not math.isnan(v)]
    return sum(finite, Fraction()) / len(finite) if finite else None

def contrast(a, b, ln10):
    if a is None or b is None:
        return None
    delta = b-a  # exact subtraction precedes Decimal conversion
    if delta == 0:
        return Decimal(0)
    t = (Decimal(abs(delta.numerator))/Decimal(delta.denominator))*ln10/10
    if t <= Decimal('0.5'):
        # expm1(t) by positive terms avoids cancellation for subnormal-scale
        # inputs. Fixed degree, no tuning or retry against private outputs.
        term = t
        numerator = t
        for k in range(2, SERIES_TERMS+1):
            term = term*t/k
            numerator += term
        value = numerator/(2+numerator)
    else:
        r = (-t).exp()
        value = (1-r)/(1+r)
    return -value if delta < 0 else value

def calculate(raw):
    if type(raw) is not bytes or len(raw) != WORDS*8:
        raise ValueError('complete original binary64 payload required')
    values = struct.unpack('<1458240d', raw)
    def at(condition, channel, window, frequency, time):
        start = (((((condition*62+channel)*2+window)*7+frequency)*28+time)*15)
        return group(values[start:start+15])
    answer = []
    with localcontext() as ctx:
        ctx.prec = PRECISION
        ctx.rounding = ROUND_HALF_EVEN
        ctx.Emin, ctx.Emax = -999999, 999999
        ln10 = Decimal(10).ln()
        for pair in range(2):
            for window in range(2):
                for channel in range(62):
                    frequencies = []
                    for frequency in range(7):
                        points = []
                        for time in range(28):
                            point = contrast(at(pair*2,channel,window,frequency,time),
                                             at(pair*2+1,channel,window,frequency,time),ln10)
                            if point is not None:
                                points.append(point)
                        if points:
                            frequencies.append(sum(points,Decimal(0))/len(points))
                    answer.append(float(sum(frequencies,Decimal(0))/len(frequencies))
                                  if frequencies else float('nan'))
    if len(answer) != 248 or any(math.isinf(v) for v in answer):
        raise ValueError('complete finite-or-undefined endpoint required')
    return struct.pack('<248d',*answer)+bytes(int(math.isnan(v)) for v in answer)

def main():
    if sys.version_info[:3] != (3,12,16):
        raise ValueError('fixed official candidate Python required')
    manifest = json.loads(Path('/input/INPUT.json').read_text())
    if (manifest['profile']!='original_scientific_operands' or
        manifest['shape']!=list(SHAPE) or manifest['dtype']!='little-endian-binary64' or
        manifest['axis_order']!=['condition','channel','window','frequency','time','stored_position'] or
        manifest['conditions']!=['NT.pin.all','NT.pout.all','T.pin.all','T.pout.all'] or
        manifest['source_frequency_indices']!=list(range(8,15)) or
        manifest['source_time_indices']!=[list(range(53,81)),list(range(119,147))] or
        manifest['stored_positions']!=list(range(15))):
        raise ValueError('fixed source operand layout required')
    raw = Path('/input/values.f64').read_bytes()
    if manifest['values']!={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}:
        raise ValueError('input manifest must authenticate raw operands')
    body=calculate(raw)
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()

if __name__=='__main__':
    main()
