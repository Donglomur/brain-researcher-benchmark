"""Bounded CLI failure continuity; original clocks, costs and custody remain explicit."""
import hashlib,json,os
from central_common import encode,extent,need

def retained(value,cap,meter):
    """Inline small facts; commit larger facts only within the original reserve."""
    try:
        raw=encode(value,cap)
        return {'support':'inline','value':value,'pin':{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}}
    except Exception:
        try:
            meter.tick('outer')
            remaining=meter.limits['metadata_bytes']-meter.used['metadata_bytes']
            maximum=min(33554432,max(0,remaining//3))
            n=extent(value,maximum);meter.charge(metadata_bytes=3*n)
            raw=encode(value,maximum)
            return {'support':'commitment_only','pin':{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},
                'items':len(value) if type(value) in (list,dict) else None,
                'body_retained_in_diagnostic':False,
                'meaning':'Exact canonical content commitment; use original published paths for available durable bodies. No complete body is claimed here.'}
        except BaseException as error:
            return {'support':'unavailable_within_original_failure_reserve','reason':type(error).__name__+': '+str(error)[:200],
                    'items':len(value) if type(value) in (list,dict) else None}

def emit(error,prefix,meter):
    """One retained stderr record; delivery failures remain explicit on original error."""
    try:
        meter.tick('outer');meter.charge(metadata_bytes=196608,write_bytes=65537)
        diagnostic={'schema':'motormint_retained_central_failure_v2',
            'reason':type(error).__name__+': '+str(error)[:1000],
            'qualified':False,'successful_delivery':False,
            'failure_stage':prefix.get('failure_stage','engine'),
            'source':prefix.get('source'),'review':prefix.get('review'),
            'inclusive_cost':retained(prefix.get('inclusive_cost'),8192,meter),
            'measurement_failure':retained(prefix.get('measurement_failure'),2048,meter),
            'cleanup_failures':retained(prefix.get('cleanup_failures',[]),4096,meter),
            'owned_output':retained(prefix.get('owned_output'),4096,meter),
            'published':retained(prefix.get('published',[]),12288,meter),
            'prepared':retained(prefix.get('prepared'),4096,meter),
            'outer':retained(prefix.get('outer'),8192,meter),
            'runtime_output_created':prefix.get('runtime_output_created'),
            'original_meter':retained(prefix.get('meter'),2048,meter),
            'secondary':retained({'notes':getattr(error,'__notes__',[]),
                'cleanup':getattr(error,'secondary',[]),
                'capture':getattr(error,'central_capture_prefix',None),
                'publication':getattr(error,'central_publication_prefix',None)},4096,meter),
            'failure_meter':meter.snapshot()}
        raw=encode(diagnostic,65536)+b'\n';at=0
        while at<len(raw):
            meter.tick('outer');n=os.write(2,raw[at:]);need(n>0,'failure diagnostic short write');at+=n
        error.central_retained_diagnostic={'pin':{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},'stream':'stderr','complete':True}
    except BaseException as secondary:
        error.central_retained_diagnostic={'complete':False,'secondary':type(secondary).__name__,
            'written_bytes':locals().get('at',0),'failure_meter':meter.snapshot()}
        error.add_note('Retained failure diagnostic incomplete: '+type(secondary).__name__)
