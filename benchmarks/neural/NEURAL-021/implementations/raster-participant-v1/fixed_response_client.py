"""Fixed zero-response PNG pipe control, not an AI or image-readability test.

Only PNG validation is imported; Pillow and operator data are not loaded.
Decoded bytes must be sent through an actual image channel by a future model
connector. This control checks framing and image structure without displaying it.
"""
import argparse
import base64
import json
from pathlib import Path
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import raster

MAX_RESPONSE = 22*1024**2
MAX_PNG = 15406963
MAX_BASE64 = 4*((MAX_PNG+2)//3)


def read_exact(size):
    out = bytearray()
    while len(out) < size:
        body = sys.stdin.buffer.read(size-len(out))
        if not body:
            raise ValueError('unexpected operator EOF')
        out.extend(body)
    return bytes(out)


def receive():
    size = struct.unpack('!I',read_exact(4))[0]
    if not 0 < size <= MAX_RESPONSE:
        raise ValueError('operator frame cap')
    def unique(rows):
        value = {}
        for key,item in rows:
            if key in value:
                raise ValueError('duplicate response field')
            value[key] = item
        return value
    return json.loads(read_exact(size).decode('utf-8'),object_pairs_hook=unique,
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite response')))


def decode_observation(answer):
    """Return validated PNG bytes for an actual image consumer; never SVG/text."""
    fields = {'seq','type','media_type','png_base64','width','height'}
    if (type(answer) is not dict or set(answer) != fields or type(answer['seq']) is not int
            or answer['seq'] < 0 or answer['type'] != 'image' or answer['media_type'] != 'image/png'
            or type(answer['width']) is not int or type(answer['height']) is not int
            or type(answer['png_base64']) is not str or len(answer['png_base64']) > MAX_BASE64):
        raise ValueError('exact PNG-only observation required')
    try:
        png = base64.b64decode(answer['png_base64'].encode('ascii'),validate=True)
    except (ValueError,UnicodeError) as error:
        raise ValueError('canonical base64 PNG required') from error
    if not 0 < len(png) <= MAX_PNG or base64.b64encode(png).decode('ascii') != answer['png_base64']:
        raise ValueError('bounded canonical PNG encoding')
    raster.validate_png(png,expected_width=answer['width'],expected_height=answer['height'])
    return png


def image_content_block(answer):
    """Return a validated MCP-style image part; callers must attach it as an image.

    Constructing this object is not evidence of provider display or preservation
    of native image resolution. This helper performs no provider/model call.
    """
    decode_observation(answer)
    return {'type':'image','mimeType':'image/png','data':answer['png_base64']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--calibration',choices=('all','none'),default='all')
    parser.add_argument('--crop-first',action='store_true')
    args = parser.parse_args(argv)
    hello = receive()
    if (hello.get('schema') != 'neural021_raster_participant_messages_v1'
            or hello.get('calibration_count') != 272 or len(hello.get('queries',[])) != 92
            or hello.get('response_shape') != [30,2] or hello.get('velocity_units') != 'm/s'
            or hello.get('max_response_bytes') != MAX_RESPONSE or hello.get('max_png_bytes') != MAX_PNG
            or hello.get('mode') not in ('direct_observation','typed_viewer')
            or len({row['trial_id'] for row in hello['queries']}) != 92):
        raise ValueError('complete declared raster task required')
    seq = 0
    def request(operation,**fields):
        nonlocal seq
        body=(json.dumps({'seq':seq,'op':operation,**fields},sort_keys=True,
                        separators=(',', ':'),allow_nan=False)+'\n').encode()
        if not 0 < len(body) <= 8192:
            raise ValueError('request cap')
        sys.stdout.buffer.write(struct.pack('!I',len(body))+body)
        sys.stdout.buffer.flush()
        answer=receive()
        if type(answer) is not dict or type(answer.get('seq')) is not int or answer['seq'] != seq:
            raise ValueError('exact response sequence')
        seq += 1
        return answer
    if args.calibration == 'all':
        for index in range(272):
            decode_observation(request('calibration',index=index))
    for index,row in enumerate(hello['queries']):
        key=row['trial_id']
        decode_observation(request('view',trial_id=key))
        if index == 0 and args.crop_first and hello['mode'] == 'typed_viewer':
            decode_observation(request('crop',trial_id=key,unit_start=0,unit_stop=5,bin_start=0,bin_stop=6))
        answer=request('answer',trial_id=key,velocity_m_s=[[0.0,0.0] for _ in range(30)])
        if answer.get('type') != 'answer_ack' or answer.get('accepted') is not True:
            raise ValueError('answer acknowledgment')
    answer=request('finish')
    if answer.get('type') != 'complete' or answer.get('queries') != 92 or answer.get('grading_pending') is not True:
        raise ValueError('complete original handoff acknowledgment')
    if sys.stdin.buffer.read(1):
        raise ValueError('trailing operator data')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
