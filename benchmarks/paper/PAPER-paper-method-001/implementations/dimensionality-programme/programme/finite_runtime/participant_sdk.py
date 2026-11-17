"""Optional participant transport helpers; no estimator or fitted method supplied."""
from __future__ import annotations
import hashlib
import json
import os
import sys
from pathlib import Path

FRAME=1048576

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')
def sha(value):return hashlib.sha256(canonical(value)).hexdigest()
def read_request():
    body=sys.stdin.buffer.read(FRAME+1)
    if len(body)>FRAME:raise ValueError('request exceeds control frame')
    request=json.loads(body.decode('utf-8'))
    if request['schema']!='finite_participant_v1':raise ValueError('wrong request schema')
    return request

def visible_file(request,logical_path,role=None):
    matches=[x for x in request['payload']['visible_artifacts'] if x['logical_path']==logical_path]
    if len(matches)!=1:raise ValueError('unassigned or ambiguous artifact')
    desc=matches[0]
    if role is not None and desc['role']!=role:raise ValueError('wrong artifact role')
    return Path(desc['path'])

def write_artifact(request,relative,body,role,media_type='application/json',**metadata):
    parts=Path(relative).parts
    if not parts or Path(relative).is_absolute() or any(x in ('.','..') for x in parts):raise ValueError('invalid output path')
    output=Path('/outputs')/relative;output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as f:f.write(body);f.flush();os.fsync(f.fileno())
    return {'path':'jobs/'+request['request_id']+'/outputs/'+relative,'bytes':len(body),
        'sha256':hashlib.sha256(body).hexdigest(),'media_type':media_type,'role':role,
        'producer':request['request_id'],**metadata}

def emit(request,payload,artifacts=()):
    response={k:request[k] for k in ('schema','run_id','arm','lane','protocol_id',
        'source_manifest_sha256','plan_sha256','request_id','parent_receipt')}
    response.update(request_sha256=sha(request),payload=payload,artifacts=list(artifacts))
    body=canonical(response)
    if len(body)>FRAME:raise ValueError('response needs separately indexed artifacts')
    sys.stdout.buffer.write(body);sys.stdout.buffer.flush()
