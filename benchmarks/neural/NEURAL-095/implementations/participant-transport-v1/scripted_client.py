"""Full offered-case software exercise; fixed800ms, no model or neural analysis."""
import json
import struct
import sys

PREFIX=struct.Struct('!II')
def exact(size):
    body=bytearray()
    while len(body)<size:
        chunk=sys.stdin.buffer.read(size-len(body))
        if not chunk:raise EOFError('Incomplete operator frame')
        body.extend(chunk)
    return bytes(body)
def receive():
    h,p=PREFIX.unpack(exact(8))
    if not 0<h<=32768 or not 0<=p<=4*1024**2:raise ValueError('Invalid operator frame bounds')
    return json.loads(exact(h)),exact(p)
def action(value):
    body=json.dumps(value,separators=(',',':'),allow_nan=False).encode()
    if len(body)>16384:raise ValueError('Request too large')
    sys.stdout.buffer.write(PREFIX.pack(len(body),0)+body);sys.stdout.buffer.flush()
    return receive()

ready,png=receive()
assert ready['kind']=='instructions' and not png
assert ready['train_n']==748 and ready['query_n']==258 and len(ready['query_ids'])==258
for index in range(748):
    row,png=action({'op':'show_train','index':index})
    assert row['kind']=='observation' and png.startswith(b'\x89PNG\r\n\x1a\n')
for index,case_id in enumerate(ready['query_ids']):
    row,png=action({'op':'show_query','index':index})
    assert row['observation']['metadata']['case_id']==case_id and png.startswith(b'\x89PNG\r\n\x1a\n')
    ack,png=action({'op':'answer','case_id':case_id,'prediction_ms':800.0})
    assert ack=={'kind':'accepted','accepted':case_id,'answered':index+1} and not png
last,png=action({'op':'finish'})
assert last=={'kind':'complete','view':ready['view'],'answers':258} and not png
