"""Task-specific PNG presentation over the unchanged N021 session/lifecycle.

Only this new adapter changes presentation and its wire receipt. The pinned
text/vector implementation, original Session bytes and source replay stay intact.
Raster bytes are not filesystem isolation, no-tools enforcement or a display proof.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
import types

HERE = Path(__file__).resolve().parent
SCHEMA = 'neural021_raster_participant_messages_v1'
MAX_RESPONSE = 22 * 1024**2
MAX_MESSAGES = 2048 + 92 + 1
MAX_SENT = (MAX_MESSAGES + 1) * (MAX_RESPONSE + 4)
MAX_PNG = 15406963
MAX_PROFILE = 8192
MAX_MAPPING_ROW = 512
MAX_FRAME_ROW = 448
MAX_TRANSCRIPT = 2 * 1024**2 - 32768
BASE_PIN = {'bytes':22957,'sha256':'4286017412f4f597b44406d855b7bcf44de1144741d3591da9d74744038de41d'}


def need(value, message):
    if not value:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value,sort_keys=True,separators=(',', ':'),allow_nan=False)+'\n').encode()


def pin(body):
    return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}


def _load(path, expected, name):
    path = Path(path).absolute()
    need('..' not in path.parts and all(not p.is_symlink() for p in (path,*path.parents)),
         'ordinary pinned source ancestry')
    need(type(expected) is dict and set(expected) == {'bytes','sha256'}
         and type(expected['bytes']) is int and 0 < expected['bytes'] <= 262144
         and type(expected['sha256']) is str and re.fullmatch('[0-9a-f]{64}',expected['sha256']),
         'exact bounded source pin')
    fd = os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and before.st_size == expected['bytes'],'ordinary pinned source extent')
        raw = stream.read(expected['bytes']+1)
        after = os.fstat(stream.fileno())
    identity = lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    need(identity(before) == identity(after) == identity(path.stat()) and pin(raw) == expected,
         'source identity changed or mismatched')
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(raw,str(path),'exec'),module.__dict__)
    return module


def source_dimensions(svg):
    """Exact pinned source root grammar; not a permissive SVG reader."""
    need(type(svg) is str and 0 < len(svg.encode()) <= 524288,'bounded original SVG')
    match = re.match(r'<svg xmlns="http://www.w3.org/2000/svg" width="([0-9]{1,4})" height="([0-9]{1,4})" viewBox="0 0 \1 \2">',svg)
    need(match is not None,'original SVG dimensions and viewBox required')
    width,height = map(int,match.groups())
    need(1 <= width <= 6365 and 1 <= height <= 2420,'original image dimensions')
    return width,height


def make_runtime(*,renderer_pin,base_transport_path=None,renderer_path=None,renderer_override=None):
    """Trusted operator API. The generated renderer override is not a CLI option.

    Even an injected generated renderer must pass the real pinned PNG validator
    and exact original dimension checks. It is always labelled in private receipts.
    """
    need(type(renderer_pin) is dict,'exact renderer source pin')
    renderer_pin = dict(renderer_pin)  # Freeze caller data before validating and loading.
    base = _load(base_transport_path or HERE.parent/'participant-transport-v1/transport.py',
                 BASE_PIN,'_n021_raster_base')
    raster = _load(renderer_path or HERE/'raster.py',renderer_pin,'_n021_raster_renderer')
    need(raster.MAX_PNG == MAX_PNG,'selected bounded PNG contract')
    need(renderer_override is None or callable(renderer_override),'trusted generated renderer callable')
    render = raster.render_svg if renderer_override is None else renderer_override
    original_exchange = base.Exchange
    original_run = base.run_participant
    base.MAX_RESPONSE = MAX_RESPONSE
    base.MAX_SENT = MAX_SENT
    base.SCHEMA = SCHEMA

    class RasterExchange(original_exchange):
        def __init__(self,sources,packet,mode):
            super().__init__(sources,packet,mode)
            self.failed = False
            self.raster_rows = []
            self.renderer_profile = None

        def hello(self):
            hello = json.loads(super().hello())
            hello['observation_format'] = 'image/png raster bytes, base64 encoded only for framing'
            hello['image_channel_requirement'] = (
                'Decode PNG and deliver it through an actual image input/display channel; base64 text is not image presentation. '
                'This adapter does not resize or tile. Downstream providers may resize; native-resolution readability is unqualified.')
            hello['max_png_bytes'] = MAX_PNG
            hello['max_image_dimensions'] = [6365,2420]
            hello['raster_display_qualified'] = False
            return encode(hello)

        def dispatch(self,body):
            need(not self.failed,'failed raster exchange cannot resume')
            try:
                response = super().dispatch(body)
                value = json.loads(response)
                if value.get('type') == 'svg':
                    svg = value['svg']
                    svg_pin = pin(svg.encode())
                    width,height = source_dimensions(svg)
                    rendered = render(svg)
                    need(type(rendered) is dict and set(rendered) ==
                         {'png','width','height','pixels_sha256','svg_sha256','profile'},'exact renderer result')
                    need(rendered['svg_sha256'] == svg_pin['sha256'] and type(rendered['width']) is int
                         and type(rendered['height']) is int and (rendered['width'],rendered['height']) == (width,height),
                         'renderer must preserve the exact original image and dimensions')
                    png = rendered['png']
                    need(type(png) is bytes and 0 < len(png) <= MAX_PNG,'bounded PNG observation')
                    checked = raster.validate_png(png,expected_width=width,expected_height=height)
                    need(checked['width'] == width and checked['height'] == height
                         and checked['pixels_sha256'] == rendered['pixels_sha256']
                         and checked['png_sha256'] == pin(png)['sha256'],'PNG pixels/dimensions bound')
                    need(type(rendered['profile']) is dict,'operator renderer profile')
                    profile = {'renderer':rendered['profile'],'renderer_source':dict(renderer_pin),
                               'generated_renderer_override_used':renderer_override is not None}
                    profile_bytes = encode(profile)
                    need(len(profile_bytes) <= MAX_PROFILE,'bounded renderer profile')
                    if self.renderer_profile is None:
                        self.renderer_profile = json.loads(profile_bytes)
                    need(encode(self.renderer_profile) == profile_bytes,'renderer profile changed during session')
                    event = self.session._events[-1]
                    need(event['operation'] in ('training_view','query_view')
                         and event['svg_sha256'] == svg_pin['sha256'],'original Session SVG binding')
                    response = encode({'seq':value['seq'],'type':'image','media_type':'image/png',
                        'png_base64':base64.b64encode(png).decode('ascii'),'width':width,'height':height})
                    need(len(response) <= MAX_RESPONSE,'raster response cap')
                    mapping = {'seq':value['seq'],'source_event_sequence':event['sequence'],
                        'source_svg':svg_pin,'png':pin(png),'width':width,'height':height,
                        'pixels_sha256':checked['pixels_sha256']}
                    need(len(encode(mapping)) <= MAX_MAPPING_ROW and len(self.raster_rows) < 2048,
                         'bounded complete raster mapping')
                    self.raster_rows.append(mapping)
                    # The preceding row already names its delivered PNG response.
                    row = self.rows[-1]
                    row['response'] = pin(response)
                    row['sha256'] = pin(encode({k:v for k,v in row.items() if k != 'sha256'}))['sha256']
                need(len(encode(self.rows[-1])) <= MAX_FRAME_ROW,'bounded complete wire row')
                return response
            except BaseException:
                # Source Session may have advanced before rendering failed. Never resume.
                self.failed,self.finished,self.pending = True,True,None
                raise

        def run(self,channel):
            need(not self.failed,'failed raster exchange cannot resume')
            try:
                transcript = super().run(channel)
                transcript.update(schema='neural021_raster_transport_exchange_v1',
                    presentation='PNG-only observation payloads; original SVG and numeric tables remain operator-side',
                    raster_observations=self.raster_rows,renderer_profile=self.renderer_profile,
                    base_transport_source=dict(BASE_PIN),generated_renderer_override_used=renderer_override is not None,
                    raster_display_qualified=False,isolation_qualified=False)
                need(len(encode(transcript)) <= MAX_TRANSCRIPT,'complete raster transcript cap')
                return transcript
            except BaseException:
                self.failed,self.finished,self.pending = True,True,None
                raise

    def raster_run(grade,sources,packet,mode,argv,cwd,timeout_seconds,*,observer):
        started = base.time.monotonic()
        result = original_run(grade,sources,packet,mode,argv,cwd,timeout_seconds,observer=observer)
        receipt = json.loads(result[3])
        receipt.update(schema='neural021_raster_participant_transport_receipt_v1',
            base_transport_source=dict(BASE_PIN),renderer_source=dict(renderer_pin),
            generated_renderer_override_used=renderer_override is not None,
            note='PNG-only observation messages were generated operator-side. Actual image-channel delivery, downstream resizing, '
                 'human/model readability, filesystem isolation and no-tools enforcement remain unqualified.')
        encoded = encode(receipt)
        base.need(len(encoded) <= base.MAX_SIDECAR,'bounded raster transport receipt')
        base.need(base.time.monotonic() <= started+timeout_seconds,'deadline exceeded during raster receipt finalization')
        return result[:3]+(encoded,)

    base.Exchange = RasterExchange
    base.run_participant = raster_run
    base.raster_module = raster
    base.raster_adapter = {'base':dict(BASE_PIN),'renderer':dict(renderer_pin),
        'overrides':['Exchange','SCHEMA','MAX_RESPONSE','MAX_SENT','run_participant receipt metadata'],
        'response_cap':MAX_RESPONSE,'response_wire_cap':MAX_SENT,
        'generated_renderer_override_used':renderer_override is not None}
    return base


def collect(public_root,mode,argv,participant_cwd,output_root,*,renderer_pin,
            timeout_seconds=180,implementations_root=None,base_transport_path=None):
    need(type(timeout_seconds) in (int,float) and 1 <= timeout_seconds <= 3600,'whole operation deadline')
    deadline = time.monotonic()+timeout_seconds
    runtime = make_runtime(renderer_pin=renderer_pin,base_transport_path=base_transport_path)
    remaining = deadline-time.monotonic()
    need(remaining >= 1,'source loading exhausted raster deadline')
    result = runtime.operator_collect(public_root,mode,argv,participant_cwd,output_root,
        remaining,implementations_root)
    need(time.monotonic() <= deadline,'whole raster operation deadline exceeded')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-root',required=True)
    parser.add_argument('--mode',choices=('direct_observation','typed_viewer'),required=True)
    parser.add_argument('--participant-cwd',required=True)
    parser.add_argument('--output-root',required=True)
    parser.add_argument('--renderer-bytes',type=int,required=True)
    parser.add_argument('--renderer-sha256',required=True)
    parser.add_argument('--base-transport')
    parser.add_argument('--implementations-root')
    parser.add_argument('--timeout-seconds',type=int,default=180)
    parser.add_argument('participant',nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.participant[1:] if args.participant[:1] == ['--'] else args.participant
    try:
        result = collect(args.public_root,args.mode,command,args.participant_cwd,args.output_root,
            renderer_pin={'bytes':args.renderer_bytes,'sha256':args.renderer_sha256},
            timeout_seconds=args.timeout_seconds,implementations_root=args.implementations_root,
            base_transport_path=args.base_transport)
    except (Exception,KeyboardInterrupt) as error:
        print(json.dumps({'status':'failed_raster_transport','error_type':type(error).__name__,
                          'admissible_handoff':False,'automatic_retry':False}),file=sys.stderr)
        signum = getattr(error,'signum',None)
        return 128+signum if type(signum) is int and 0 < signum < 128 else 2
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
