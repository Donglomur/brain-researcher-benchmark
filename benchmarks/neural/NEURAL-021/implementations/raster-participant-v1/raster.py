"""Exact N021 text/layout to metadata-free PNG; no general SVG interpretation.

The SVG stays in trusted operator code. PNG is the sole observation payload.
This does not enforce filesystem/no-tools isolation or establish display readability.
PNG framing/filter checks adapt N095 count-viewer-v1 and N007 whole-night-viewer-v1.
Pillow is imported only when render_svg is called, never by the PNG validator.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import io
import math
import os
from pathlib import Path
import re
import stat
import struct
import xml.etree.ElementTree as ET
import zlib

MAX_WIDTH, MAX_HEIGHT = 6365, 2420
MAX_PIXELS = MAX_WIDTH * MAX_HEIGHT
MAX_SVG = 524288
MAX_RAW = MAX_HEIGHT * (MAX_WIDTH + 1)
MAX_PNG = MAX_RAW + 5 * ((MAX_RAW + 65534) // 65535) + 6 + 57
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
FONT_BYTES = 340240
FONT_SHA256 = '602ec86b8948cfcd956482fe64f94c36c867770149ef2f791d4613f443bcecb3'
FONT_SIZE = 13
FONT_PATH = Path(__file__).absolute().parent / 'assets' / 'DejaVuSansMono.ttf'
NAMESPACE = '{http://www.w3.org/2000/svg}'
HEADER_TEXT = (
    'Each cell = exact spike count in one 20 ms half-open interval; units U01..U65 preserve source column order.',
    'Columns show interval start in ms from released onset. Bin k = [-220+20k, -200+20k), k=0..34.',
    'Response j=0..29: velocity x/y in m/s over [-100+20j, -80+20j); no additional unit conversion.',
    'History for response j consists of count columns j..j+5. Full batch context is available; retrospective task.',
    'Source onset uses future acceleration. Extended perturbation trajectory may include voluntary correction.',
)
TRAINING_HEADER = 'TRAINING LABELS ONLY: bin j | target interval ms | x m/s | y m/s'
DECIMAL = re.compile(r'0|[1-9][0-9]*\Z')
NUMBER = re.compile(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:e[+-][0-9]+)?\Z')


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def _integer(text):
    need(type(text) is str and len(text) <= 10 and DECIMAL.fullmatch(text), 'canonical integer coordinate')
    return int(text)


def parse_svg(svg_text):
    """Operator-only canonical layout. Never expose its numerical/text rows."""
    need(type(svg_text) is str and 0 < len(svg_text) <= MAX_SVG, 'bounded SVG text')
    try:
        raw = svg_text.encode('ascii')
    except UnicodeEncodeError as error:
        raise ValueError('original ASCII observation vocabulary required') from error
    need(len(raw) <= MAX_SVG and '<!' not in svg_text and '<?' not in svg_text
         and '&' not in svg_text, 'no declarations, entities, comments or processing instructions')
    # ElementTree discards namespace declarations. The fixed producer emits
    # exactly this one root declaration; reject hidden declarations lexically.
    need(svg_text.startswith('<svg xmlns="http://www.w3.org/2000/svg" ')
         and svg_text.count('xmlns') == 1, 'one canonical root namespace only')
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as error:
        raise ValueError('well-formed original SVG required') from error
    need(root.tag == NAMESPACE+'svg' and set(root.attrib) == {'width', 'height', 'viewBox'}
         and not root.text and not root.tail and len(root) == 2, 'exact original SVG root')
    width, height = _integer(root.get('width')), _integer(root.get('height'))
    need(1300 <= width <= MAX_WIDTH and 302 <= height <= MAX_HEIGHT
         and root.get('viewBox') == f'0 0 {width} {height}', 'original unscaled canvas and viewBox')
    rect, group = root
    need(rect.tag == NAMESPACE+'rect' and rect.attrib == {'width':'100%', 'height':'100%', 'fill':'white'}
         and not rect.text and not rect.tail and not len(rect), 'exact white background')
    need(group.tag == NAMESPACE+'g' and group.attrib == {'font-family':'monospace', 'font-size':'13', 'fill':'#111'}
         and not group.text and not group.tail and 11 <= len(group) <= 2500, 'exact original text group')
    texts = []
    for node in group:
        need(node.tag == NAMESPACE+'text' and not len(node) and not node.tail
             and set(node.attrib) in ({'x','y'}, {'x','y','data-unit','data-bin'}), 'flat original text only')
        value = node.text
        need(type(value) is str and 0 < len(value) <= 200
             and all(32 <= ord(char) <= 126 for char in value), 'bounded literal ASCII display text')
        row = {'x':_integer(node.get('x')), 'y':_integer(node.get('y')), 'text':value}
        if 'data-unit' in node.attrib:
            row.update(unit=_integer(node.get('data-unit')), bin=_integer(node.get('data-bin')))
        texts.append(row)
    header = re.fullmatch(r'([tq][0-9]{4}) \| (active|perturbation \(source: passive\)) \| NEURAL-021', texts[0]['text'])
    need(header is not None, 'original bounded trial/condition header')
    viewport = re.fullmatch(r'View: unit indices \[([0-9]+),([0-9]+)\), count-bin indices \[([0-9]+),([0-9]+)\)\.', texts[6]['text'])
    need(viewport is not None, 'explicit original viewport label')
    u0, u1, b0, b1 = map(_integer, viewport.groups())
    need(0 <= u0 < u1 <= 65 and 0 <= b0 < b1 <= 35, 'original half-open viewport')
    nu, nb = u1-u0, b1-b0
    prefix_count = 7 + 2*nb + nu*(1+nb)
    training = len(texts) == prefix_count + 31
    need(len(texts) in (prefix_count, prefix_count+31), 'complete exact layout text count')
    need(header[1].startswith('t') == training, 'calibration labels match original trial type')
    need(not training or (u0,u1,b0,b1) == (0,65,0,35), 'calibration crops are not an allowed observation')
    need(height == 280 + nu*22 + (710 if training else 0), 'original unscaled canvas height')

    def expect(index, x, y, text, kind, unit=None, bin_index=None):
        row = texts[index]
        expected = {'x':x, 'y':y, 'text':text}
        if unit is not None:
            expected.update(unit=unit, bin=bin_index)
        need(row == expected, 'original text, axes, order and coordinates required')
        row['kind'] = kind

    expect(0,20,24,header[0],'header')
    for index, value in enumerate(HEADER_TEXT, 1):
        expect(index,20,24+index*22,value,'header')
    expect(6,20,156,f'View: unit indices [{u0},{u1}), count-bin indices [{b0},{b1}).','header')
    counts = []
    offset = 7+2*nb
    for local_u, unit in enumerate(range(u0,u1)):
        for local_b, bin_index in enumerate(range(b0,b1)):
            row = texts[offset + local_u*(nb+1)+1+local_b]
            need(re.fullmatch(r'0|[1-9][0-9]{0,18}', row['text']) is not None
                 and int(row['text']) <= 2**63-1, 'exact nonnegative int64 count text')
            counts.append(row['text'])
    cell_width = max(46, max(map(len,counts))*9+8)
    need(width == max(1300,100+nb*cell_width), 'original count-dependent canvas width')
    for local_b, bin_index in enumerate(range(b0,b1)):
        x = 92 + local_b*cell_width
        expect(7+2*local_b,x,184,f'k{bin_index:02d}','column_bin')
        expect(8+2*local_b,x,204,f'{-220+20*bin_index:+d}','column_ms')
    for local_u, unit in enumerate(range(u0,u1)):
        y = 230 + local_u*22
        expect(offset+local_u*(nb+1),20,y,f'U{unit+1:02d}','unit')
        for local_b, bin_index in enumerate(range(b0,b1)):
            index = offset+local_u*(nb+1)+1+local_b
            value = texts[index]['text']
            expect(index,92+local_b*cell_width,y,value,'count',unit,bin_index)
    if training:
        y = 260+nu*22
        expect(prefix_count,20,y,TRAINING_HEADER,'training_header')
        for j in range(30):
            index = prefix_count+j+1
            value = texts[index]['text']
            prefix = f'{j:02d} | [{-100+20*j:+d},{-80+20*j:+d}) | '
            need(value.startswith(prefix), 'original target row and interval')
            pair = value[len(prefix):].split(' | ')
            need(len(pair) == 2 and all(len(token) <= 32 and NUMBER.fullmatch(token)
                 and math.isfinite(float(token)) and abs(float(token)) <= 1e6 for token in pair),
                 'literal finite original calibration values')
            expect(index,20,y+(j+1)*22,value,'training_value')
    return {'width':width, 'height':height, 'texts':texts, 'cell_width':cell_width,
            'viewport':{'unit_start':u0,'unit_stop':u1,'bin_start':b0,'bin_stop':b1},
            'training':training, 'svg_sha256':sha(raw)}


def _font_bytes():
    need(all(not path.is_symlink() for path in (FONT_PATH,*FONT_PATH.parents)), 'ordinary bundled font path')
    fd = os.open(FONT_PATH,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == FONT_BYTES,
             'exact ordinary bundled font extent')
        body = stream.read(FONT_BYTES+1)
        after = os.fstat(stream.fileno())
    identity = lambda value: tuple(getattr(value,key) for key in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns'))
    need(identity(before) == identity(after) == identity(FONT_PATH.stat()) and len(body) == FONT_BYTES
         and sha(body) == FONT_SHA256, 'unchanged bundled font required; no fallback')
    return body


@lru_cache(maxsize=1)
def _font_bundle():
    # Loading from authenticated bytes avoids a second path-based font read.
    body = _font_bytes()
    from PIL import ImageFont, __version__
    font = ImageFont.truetype(io.BytesIO(body),size=FONT_SIZE,layout_engine=ImageFont.Layout.BASIC)
    profile = {'schema':'neural021_pinned_raster_profile_v1','font_bytes':FONT_BYTES,
               'font_sha256':FONT_SHA256,'font_size_px':FONT_SIZE,'layout_engine':'BASIC',
               'pixel_mode':'L','foreground':17,'background':255,'resizing':'none',
               'pillow_version':str(__version__),'freetype_version':str(ImageFont.core.freetype2_version),
               'zlib_version':zlib.ZLIB_VERSION,'zlib_runtime_version':zlib.ZLIB_RUNTIME_VERSION,
               'qualification':'Raster bytes only; consumer display, readability and isolation are not established.'}
    return font, profile


def _chunk(name, body):
    return struct.pack('>I',len(body))+name+body+struct.pack('>I',zlib.crc32(name+body)&0xffffffff)


def _stored_zlib(raw):
    """Explicit stored blocks make the encoder's maximum size a construction bound."""
    need(type(raw) is bytes and len(raw) <= MAX_RAW, 'bounded stored scanlines')
    chunks = [raw[index:index+65535] for index in range(0,len(raw),65535)] or [b'']
    parts = [b'\x78\x01']
    for index, block in enumerate(chunks):
        size = len(block)
        parts.append(bytes([index == len(chunks)-1])+struct.pack('<HH',size,size^65535)+block)
    parts.append(struct.pack('>I',zlib.adler32(raw)&0xffffffff))
    return b''.join(parts)


def _encode_png(pixels, width, height):
    need(type(width) is int and type(height) is int and 1 <= width <= MAX_WIDTH
         and 1 <= height <= MAX_HEIGHT and type(pixels) is bytes and len(pixels) == width*height,
         'bounded exact grayscale raster')
    scan = b''.join(b'\0'+pixels[row*width:(row+1)*width] for row in range(height))
    stored_bound = len(scan)+5*((len(scan)+65534)//65535)+6
    compressed = zlib.compress(scan,level=6)
    if len(compressed) > stored_bound:
        compressed = _stored_zlib(scan)
    need(len(compressed) <= stored_bound, 'constructed zlib size bound')
    header = struct.pack('>IIBBBBB',width,height,8,0,0,0,0)
    body = PNG_SIGNATURE+_chunk(b'IHDR',header)+_chunk(b'IDAT',compressed)+_chunk(b'IEND',b'')
    need(len(body) <= MAX_PNG, 'bounded grayscale PNG')
    return body


def _decode_png(body, expected_width=None, expected_height=None):
    need(type(body) is bytes and 57 < len(body) <= MAX_PNG and body[:8] == PNG_SIGNATURE,
         'bounded PNG signature')
    offset, chunks = 8, []
    for expected in (b'IHDR',b'IDAT',b'IEND'):
        need(offset+12 <= len(body), 'complete PNG chunk')
        length = struct.unpack('>I',body[offset:offset+4])[0]
        need(length <= MAX_PNG and offset+length+12 <= len(body), 'bounded PNG chunk extent')
        name = body[offset+4:offset+8]
        data = body[offset+8:offset+8+length]
        crc = struct.unpack('>I',body[offset+8+length:offset+12+length])[0]
        need(name == expected and crc == zlib.crc32(name+data)&0xffffffff, 'exact PNG chunks and CRCs')
        chunks.append(data);offset += length+12
    need(offset == len(body) and chunks[2] == b'' and len(chunks[0]) == 13,
         'metadata-free single PNG, no trailing bytes')
    width,height,depth,color,compression,filter_method,interlace = struct.unpack('>IIBBBBB',chunks[0])
    need(1 <= width <= MAX_WIDTH and 1 <= height <= MAX_HEIGHT
         and (depth,color,compression,filter_method,interlace) == (8,0,0,0,0),
         'bounded grayscale8 unscaled PNG dimensions')
    for actual, expected in ((width,expected_width),(height,expected_height)):
        need(expected is None or (type(expected) is int and actual == expected), 'source/PNG dimensions match')
    raw_size = height*(width+1)
    decoder = zlib.decompressobj(wbits=15)
    try:
        scan = decoder.decompress(chunks[1],raw_size+1)
    except zlib.error as error:
        raise ValueError('invalid PNG compression') from error
    need(len(scan) == raw_size and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,
         'one complete bounded PNG scanline stream')
    need(all(scan[row*(width+1)] == 0 for row in range(height)), 'exact filter0 scanlines')
    pixels = b''.join(scan[row*(width+1)+1:(row+1)*(width+1)] for row in range(height))
    metadata = {'width':width,'height':height,'pixels_sha256':sha(pixels),'png_sha256':sha(body),
                'bytes':len(body),'mode':'L','chunks':['IHDR','IDAT','IEND']}
    return pixels, metadata


def validate_png(body, expected_width=None, expected_height=None):
    """Pure stdlib: reject auxiliary data, animation, trailing content and bombs."""
    return _decode_png(body,expected_width,expected_height)[1]


def render_svg(svg_text):
    """Rasterize one exact original observation; keep SVG and profile operator-side."""
    layout = parse_svg(svg_text)
    font, profile = _font_bundle()
    width, height = layout['width'],layout['height']
    # Check every glyph bound before drawing; no clipping, fitting or fallback.
    for row in layout['texts']:
        left,top,right,bottom = font.getbbox(row['text'],anchor='ls')
        x,y = row['x'],row['y']
        need(right > left and bottom > top and 0 <= x+left < x+right <= width
             and 0 <= y+top < y+bottom <= height, 'literal glyph ink fits original canvas')
        if row['kind'] == 'count':
            need(0 <= left < right <= layout['cell_width'] and -18 <= top < bottom <= 4,
                 'count glyph ink fits original cell slot')
    from PIL import Image, ImageDraw
    image = Image.new('L',(width,height),255)
    try:
        draw = ImageDraw.Draw(image)
        for row in layout['texts']:
            draw.text((row['x'],row['y']),row['text'],font=font,fill=17,anchor='ls',stroke_width=0)
        pixels = image.tobytes()
    finally:
        image.close()
    png = _encode_png(pixels,width,height)
    metadata = validate_png(png,width,height)
    need(metadata['pixels_sha256'] == sha(pixels), 'encoded pixels equal the drawn raster')
    return {'png':png,'width':width,'height':height,'pixels_sha256':metadata['pixels_sha256'],
            'svg_sha256':layout['svg_sha256'],'profile':dict(profile)}
