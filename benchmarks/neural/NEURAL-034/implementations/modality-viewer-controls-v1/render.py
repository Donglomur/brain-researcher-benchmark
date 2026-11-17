"""Fixed observation projections for the existing NEURAL-034 raster viewer.

The operator supplies one condition and an already projected record. The
combined condition delegates to the original renderer without changing its
pixels. Single-modality conditions reject the excluded array, leave its lanes
blank, and draw the included samples using the original pixel geometry.

Only the authenticated base renderer and raster primitives passed by the
caller are used. This module performs no imports, file access or resampling.
"""

CONDITIONS = (
    'combined_calcium_behavior_v1',
    'calcium_only_v1',
    'behavior_only_v1',
)


def render(record, gain, raster, base, condition):
    """Return a PNG and included-calcium clipping flags for one observation."""
    base.need(type(condition) is str and condition in CONDITIONS,
              'Exact declared observation condition')
    if condition == 'combined_calcium_behavior_v1':
        return base.render(record, gain, raster)

    base.need(type(record) is dict, 'Exact projected observation record')
    role = record.get('role')
    base.need(type(role) is str and role in ('training', 'query'),
              'Exact observation role')
    included = 'windows' if condition == 'calcium_only_v1' else 'behavior'
    fields = {'role', 'index', included}
    if role == 'training':
        fields.add('label')
    base.need(set(record) == fields,
              'Exact included-modality fields; excluded observations forbidden')
    index = record['index']
    base.need(type(index) is int and 0 <= index < (120 if role == 'training' else 20),
              'Observation index within the complete active fold')
    base.need(type(gain) in (int, float) and base.math.isfinite(gain)
              and 2**-20 <= gain <= 2**60,
              'Finite display gain within declared range')
    base.need((base.WIDTH, base.HEIGHT, base.LEFT, base.RIGHT) == (1400, 820, 180, 1300),
              'Original canvas and horizontal extent')

    title = f'QUERY {index:02d} - LABEL HIDDEN'
    if role == 'training':
        label = record['label']
        base.need(type(label) is int and label in (0, 1), 'Exact training label A or B')
        title = f'TRAINING {index:03d} - CONTEXT ' + ('A' if label == 0 else 'B')

    if included == 'windows':
        traces = record['windows']
        base.need(len(traces) == 300 and all(len(row) == 12 for row in traces),
                  'Complete 300-sample twelve-cell calcium observation')
        base.need(all(base.math.isfinite(float(value)) for row in traces for value in row),
                  'Finite included fluorescence')
    else:
        behavior = record['behavior']
        base.need(len(behavior) == 300 and all(float(value) in (0., 1.) for value in behavior),
                  'Complete 300-sample binary behavior observation')

    canvas = raster.Canvas()
    left, right = base.LEFT, base.RIGHT
    blue, black, red, grid = base.BLUE, base.BLACK, base.RED, base.GRID
    modality = 'CALCIUM ONLY' if included == 'windows' else 'BEHAVIOR ONLY'
    canvas.text(28, 18, f'NEURAL-034 {modality} VIEWER')
    canvas.text(28, 49, title)
    clipped = []

    if included == 'windows':
        canvas.text(28, 80, f'ALL 12 SELECTED CELLS / 300 SAMPLES / 10 HZ / GAIN {gain:.6g} UNITS PER DIV', scale=1)
        canvas.text(28, 102, 'NO ADDED FILTER OR NORMALIZATION / POSITIVE UP / SAME GAIN FOR EVERY CELL', scale=1)
        for cell in range(12):
            middle = 153 + cell*43
            canvas.text(28, middle-6, f'CELL {cell+1:02d}', scale=1)
            for division in (-2, -1, 0, 1, 2):
                y = middle-division*8
                canvas.line(left, y, right, y, black if division == 0 else grid)
            for tick in range(7):
                x = left+round((right-left)*tick/6)
                canvas.line(x, middle-16, x, middle+16, grid)
            previous = None
            outside = False
            for sample in range(300):
                value = float(traces[sample][cell])
                outside |= abs(value) > 2*gain
                point = (base.x_for(sample), value)
                if previous is not None:
                    base.segment(canvas, *previous, *point, gain, middle)
                elif not outside:
                    canvas.pixel(point[0], middle-round(value/gain*8), blue)
                previous = point
            if outside:
                clipped.append(cell+1)
                canvas.text(99, middle-6, 'CLIPPED', red, scale=1)
        canvas.text(left, 701, 'BEHAVIOR UNAVAILABLE IN THIS CONDITION', scale=1)
    else:
        canvas.text(28, 80, 'BINARY BEHAVIOR PROXY / 300 SAMPLES / 10 HZ / DISPLAY GAIN DOES NOT ALTER BINARY STATES', scale=1)
        canvas.text(28, 102, 'NO ADDED FILTER OR NORMALIZATION / CALCIUM IS NOT PROVIDED', scale=1)
        canvas.text(left, 400, 'CALCIUM UNAVAILABLE IN THIS CONDITION', scale=1)
        middle = 704
        canvas.text(28, 692, 'BEHAVIOR', scale=1)
        canvas.text(28, 707, 'BINARY PROXY', scale=1)
        canvas.line(left, middle-12, right, middle-12, grid)
        canvas.line(left, middle+12, right, middle+12, grid)
        canvas.text(155, middle-17, '1', scale=1)
        canvas.text(155, middle+7, '0', scale=1)
        previous = None
        for sample, value in enumerate(behavior):
            x, y = base.x_for(sample), middle+12-round(float(value)*24)
            if previous is None:
                canvas.pixel(x, y, black)
            else:
                canvas.line(previous[0], previous[1], x, previous[1], black)
                canvas.line(x, previous[1], x, y, black)
            previous = x, y

    for tick in range(7):
        canvas.text(left+round((right-left)*tick/6)-5, 732, str(tick*5), scale=1)
    canvas.text(440, 752, 'TIME WITHIN WINDOW (SECONDS) / SUPPORT [0,30)', scale=1)
    if included == 'windows':
        canvas.text(28, 775, 'SAMPLE CENTERS 0.05..29.95 S / AUTHOR-PROCESSED FLUORESCENCE UNITS / BEHAVIOR UNAVAILABLE', scale=1)
        canvas.text(28, 795, 'CLIPPED LANES REQUIRE A LARGER GAIN / DISPLAY DOES NOT PROVE NEURAL CONTRIBUTION', scale=1)
    else:
        canvas.text(28, 775, 'SAMPLE CENTERS 0.05..29.95 S / BEHAVIOR POLARITY UNRESOLVED / CALCIUM UNAVAILABLE', scale=1)
        canvas.text(28, 795, 'BEHAVIOR-ONLY PREDICTION DOES NOT ESTABLISH A NEURAL CONTRIBUTION', scale=1)
    return base.png(canvas.pixels), clipped
