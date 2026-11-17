"""Fixed RGB display of all selected calcium samples and aligned behavior.

Canvas/font/line primitives are authenticated from the existing EEG renderer.
Input values are never normalized, filtered, interpolated or returned to callers.
PNG compression is lossless in these raster pixels, not in the original arrays.
"""
from fractions import Fraction
import math
import struct
import zlib

WIDTH, HEIGHT = 1400, 820
LEFT, RIGHT = 180, 1300
BLUE, BLACK, RED, GRID = (20,75,170), (25,35,48), (170,35,35), (220,225,232)


def need(ok, message):
    if not ok:
        raise ValueError(message)


def x_for(index):
    # Original converter's sample centers: 0.05, 0.15, ..., 29.95 seconds.
    return LEFT + round((2 * index + 1) * (RIGHT - LEFT) / 600)


def segment(canvas, x0, y0, x1, y1, gain, middle):
    """Geometrically clip the original segment to the two-division lane."""
    low, high = -2 * gain, 2 * gain
    if (y0 > high and y1 > high) or (y0 < low and y1 < low):
        return
    a, b = y0, y1
    if y0 < low or y0 > high:
        y0 = max(low, min(high, y0))
        fraction = (Fraction(y0)-Fraction(a))/(Fraction(b)-Fraction(a))
        x0 += float(fraction)*(x1-x0)
    if y1 < low or y1 > high:
        y1 = max(low, min(high, y1))
        fraction = (Fraction(y1)-Fraction(y0))/(Fraction(b)-Fraction(y0))
        x1 = x0 + float(fraction)*(x1-x0)
    canvas.line(round(x0), middle-round(y0/gain*8),
                round(x1), middle-round(y1/gain*8), BLUE)


def png(pixels):
    need(len(pixels) == WIDTH*HEIGHT*3, 'Exact RGB extent')
    scan = b''.join(b'\0'+pixels[y*WIDTH*3:(y+1)*WIDTH*3] for y in range(HEIGHT))
    compressor = zlib.compressobj(9, zlib.DEFLATED, 15, 8, zlib.Z_DEFAULT_STRATEGY)
    compressed = compressor.compress(scan) + compressor.flush()
    def chunk(kind, body):
        return struct.pack('>I',len(body))+kind+body+struct.pack('>I',zlib.crc32(kind+body))
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',WIDTH,HEIGHT,8,2,0,0,0))
            +chunk(b'IDAT',compressed)+chunk(b'IEND',b''))


def render(record, gain, raster):
    need(type(gain) in (int,float) and math.isfinite(gain) and 2**-20 <= gain <= 2**60,
         'Finite display gain within declared range')
    traces, behavior = record['windows'], record['behavior']
    need(len(traces)==300 and all(len(row)==12 for row in traces) and len(behavior)==300,
         'Complete 300-sample twelve-cell observation')
    need(all(math.isfinite(float(v)) for row in traces for v in row)
         and all(float(v) in (0.,1.) for v in behavior), 'Finite fluorescence and binary behavior')
    canvas = raster.Canvas()
    role, index = record['role'], record['index']
    title = f'QUERY {index:02d} - LABEL HIDDEN'
    if role == 'training':
        need(record['label'] in (0,1), 'Training label A or B')
        title = f'TRAINING {index:03d} - CONTEXT '+('A' if record['label']==0 else 'B')
    canvas.text(28,18,'NEURAL-034 PROCESSED CALCIUM AND BEHAVIOR VIEWER')
    canvas.text(28,49,title)
    canvas.text(28,80,f'ALL 12 SELECTED CELLS / 300 SAMPLES / 10 HZ / GAIN {gain:.6g} UNITS PER DIV',scale=1)
    canvas.text(28,102,'NO ADDED FILTER OR NORMALIZATION / POSITIVE UP / SAME GAIN FOR EVERY CELL',scale=1)
    clipped = []
    for cell in range(12):
        middle = 153 + cell*43
        canvas.text(28,middle-6,f'CELL {cell+1:02d}',scale=1)
        for division in (-2,-1,0,1,2):
            y=middle-division*8
            canvas.line(LEFT,y,RIGHT,y,BLACK if division==0 else GRID)
        for tick in range(7):
            x=LEFT+round((RIGHT-LEFT)*tick/6)
            canvas.line(x,middle-16,x,middle+16,GRID)
        previous=None
        outside=False
        for sample in range(300):
            value=float(traces[sample][cell])
            outside |= abs(value)>2*gain
            point=(x_for(sample),value)
            if previous is not None:
                segment(canvas,*previous,*point,gain,middle)
            elif not outside:
                canvas.pixel(point[0],middle-round(value/gain*8),BLUE)
            previous=point
        if outside:
            clipped.append(cell+1)
            canvas.text(99,middle-6,'CLIPPED',RED,scale=1)
    middle=704
    canvas.text(28,692,'BEHAVIOR',scale=1)
    canvas.text(28,707,'BINARY PROXY',scale=1)
    canvas.line(LEFT,middle-12,RIGHT,middle-12,GRID)
    canvas.line(LEFT,middle+12,RIGHT,middle+12,GRID)
    canvas.text(155,middle-17,'1',scale=1)
    canvas.text(155,middle+7,'0',scale=1)
    previous=None
    for sample,value in enumerate(behavior):
        x,y=x_for(sample),middle+12-round(float(value)*24)
        if previous is None:
            canvas.pixel(x,y,BLACK)
        else:
            # Step display retains the released binary state at each sample.
            canvas.line(previous[0],previous[1],x,previous[1],BLACK)
            canvas.line(x,previous[1],x,y,BLACK)
        previous=x,y
    for tick in range(7):
        canvas.text(LEFT+round((RIGHT-LEFT)*tick/6)-5,732,str(tick*5),scale=1)
    canvas.text(440,752,'TIME WITHIN WINDOW (SECONDS) / SUPPORT [0,30)',scale=1)
    canvas.text(28,775,'SAMPLE CENTERS 0.05..29.95 S / AUTHOR-PROCESSED FLUORESCENCE UNITS / BEHAVIOR POLARITY UNRESOLVED',scale=1)
    canvas.text(28,795,'CLIPPED LANES REQUIRE A LARGER GAIN / DISPLAY DOES NOT PROVE NEURAL CONTRIBUTION',scale=1)
    return png(canvas.pixels),clipped
