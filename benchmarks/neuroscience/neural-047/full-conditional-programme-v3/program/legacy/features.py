"""Public fixed reference feature map; no label or future access."""
import math
from .delivery_io import need, exact
ARMS=("N","B","NB")
MAX_FRAMES=1000000
def finite(x):
    return type(x) in (int,float) and math.isfinite(x)

def summaries(view, arm):
    """Declared trailing summaries for one matched logistic reference family."""
    need(arm in ARMS, 'Fixed arm')
    channels = {'N': ('saav_history',), 'B': ('velocity', 'dv'),
                'NB': ('velocity', 'dv', 'saav_history')}[arm]
    exact(view, ['time_offset_seconds', *channels])
    times = view['time_offset_seconds']; result = []
    need(type(times) is list and 2 <= len(times) <= MAX_FRAMES and
         all(finite(t) and -4.8 <= t <= 0 for t in times) and times[-1] == 0 and
         all(a < b for a, b in zip(times, times[1:])), 'Past-only strictly ordered physical histories')
    n = len(times); tm = math.fsum(times) / n
    denominator = math.fsum((t - tm) ** 2 for t in times)
    need(denominator > 0 and math.isfinite(denominator), 'Representable time variation')
    for channel in channels:
        values = view[channel]
        need(type(values) is list and len(values) == n and all(finite(v) for v in values),
             'Every observed channel is finite and aligned')
        try:
            mean = math.fsum(values) / n
            centered = [v - mean for v in values]
            variance = math.fsum(v * v for v in centered) / n
            slope = math.fsum((t - tm) * v for t, v in zip(times, centered)) / denominator
            result.extend([values[-1], mean, math.sqrt(variance), min(values), max(values), slope])
        except (OverflowError, ValueError) as error:
            raise ValueError('Unrepresentable declared summaries') from error
    need(all(finite(x) for x in result), 'Finite declared summaries')
    return result
