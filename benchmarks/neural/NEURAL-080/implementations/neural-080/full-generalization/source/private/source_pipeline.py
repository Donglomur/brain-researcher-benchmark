"""Concrete media/log preparation chain, callable only in admitted deployment.

This source does not manufacture an authentic-input or native authority issuer.
The deployment must select complete real maps, roots and capacity before calling.
No candidate process, target scorer or hardware calibration is launched here.
"""
import hashlib
import json
from pathlib import Path
from input_owner import capture, need, descriptor

JOIN_SHA='fa3b05a001c897327990d60f13ba0969cced17a4f1aa1e6a5b64cb284148cd24'
REQUIRED_SHA='629f374eb781cb37ae207b295d7ab4aa758013e601bb5350274b9df2054add78'

def decode_json(body):
    def pairs(rows):
        result={}
        for k,v in rows:
            need(k not in result,'Duplicate JSON key');result[k]=v
        return result
    return json.loads(body.decode('utf-8'),object_pairs_hook=pairs,
                      parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))

def selected(root,row,owner):
    raw=capture(root,row,owner)
    return decode_json(raw),hashlib.sha256(raw).hexdigest()

def prepare_sources(*, selection_root, media_root, log_root, metadata_root,
                    raw_root, selection, outputs, pool_output_cap, owner):
    """All media and behavioral roles, then unchanged clip-time EEG/eye recipe.

    Outputs are four distinct fresh directories, chosen by the trusted caller.
    Preparation can fail partially; the same original Owner retains its prefix.
    """
    rec=owner.begin('complete_source_preparation');answer=None
    try:
        need(type(selection) is dict and set(selection)=={'media','logs','joined','recordings'},'Closed original selections')
        for row in selection.values():descriptor(row)
        need(selection['joined']['path']=='JOINED_METADATA.json' and selection['joined']['sha256']==JOIN_SHA,'Exact original joined metadata')
        need(selection['recordings']['path']=='source/REQUIRED_RECORDINGS.json' and selection['recordings']['sha256']==REQUIRED_SHA,'Exact original recording manifest')
        need(type(outputs) is dict and set(outputs)=={'decoded','presentation','features','pool'} and len({str(Path(x).absolute()) for x in outputs.values()})==4,'Four distinct caller-owned outputs')
        need(type(pool_output_cap) is int and pool_output_cap>0,'Original explicit pool output cap')
        # Imports are effects inside the original retained attempt.
        import decode_media
        import presentation_clock
        import feature_pipeline
        media,media_sha=selected(selection_root,selection['media'],owner)
        logs,_=selected(selection_root,selection['logs'],owner)
        joined,_=selected(metadata_root,selection['joined'],owner)
        selected(metadata_root,selection['recordings'],owner)
        decode_media.validate_selection(media)
        decoded=decode_media.produce(media_root,media,media_sha,outputs['decoded'],owner)
        # Bind the actual written product; no hand-authored descriptor substitute.
        body=(json.dumps(decoded,allow_nan=False,separators=(',',':'))+'\n').encode()
        decoded_row={'path':'DECODED_MEDIA.json','bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
        presentation=presentation_clock.produce(log_root,logs,media,joined,owner,outputs['presentation'])
        features=feature_pipeline.prepare(media_root,outputs['decoded'],decoded_row,outputs['features'],owner)
        # The inherited HDF5 preparation has explicit output accounting but is
        # not a fully metered native reader. Its physical-cost gate remains open.
        import prepare_pool
        pool=prepare_pool.prepare(Path(raw_root),Path(outputs['features']),Path(outputs['pool']),pool_output_cap,metadata_root=Path(metadata_root),owner=owner)
        answer={'schema':'neural080_source_preparation_v2','complete_source_support':True,
                'media':1102,'persons':6,'sessions_per_person':8,'recordings':96,
                'joined_trials':presentation['joined_trials'],'pool':pool,
                'clock_profile':features['clock_domain'],'hardware_alignment_verified':False,
                'native_cost_qualified':False,'candidate_runs':0,'scientific_qualification':False}
    except BaseException as exc:owner.failure(rec,exc)
    owner.complete(rec);return answer

def active_programme(*args,**kwargs):
    raise RuntimeError('NEURAL-080 activation held: genuine source-map/admission, deployment capacity, candidate isolation and hardware-clock qualification are unavailable; source hashes and this caller do not issue them')
