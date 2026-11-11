"""Full classification grids from manuscript Tables1/2/16/17; no raw-data inference."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from protocol import digest
TASK_ID='PAPER-paper-method-replacement-008'
PEOPLE=(1,2,3,4,6,7,10)
SCALES=('channels','parcels','lobes')
MODELS=tuple('barista_'+e+'_'+m for e in SCALES for m in SCALES)+tuple('random_'+e for e in SCALES)+('popt_brainbert','brant')
ARMS=('paper_and_data','paper_data_official_code')
PROTOCOLS=('random_nonoverlap','chronological')
TASKS={'random_nonoverlap':('sentence_onset','speech_vs_nonspeech'),'chronological':('sentence_onset_time','speech_vs_nonspeech_time','volume','optical_flow')}
# Logical slots bind the five source-seed and five chronological-fold identities.
# The source integer values must be separately pinned; slots are not invented RNG seeds.

def contexts():
    result=[]
    for protocol in PROTOCOLS:
        for person in PEOPLE:
            for task in TASKS[protocol]:
                for fold in ((0,) if protocol=='random_nonoverlap' else (1,2,3,4,5)):
                    for seed in (1,2,3,4,5):
                        case_id=f'{protocol}-sub{person}-{task}-f{fold}-s{seed}'
                        result.append({'id':case_id,'protocol':protocol,'person':person,'task':task,'fold':fold,'seed':seed})
    return result


def hexhash(v):return isinstance(v,str) and len(v)==64 and all(c in '0123456789abcdef' for c in v)


def validate_public(d):
    if not isinstance(d,dict) or set(d)!={'schema','task_id','source_protocol_sha256','contexts','panel_id','generation_commitment'} or d['schema']!='barista_public_panel_v1' or d['task_id']!=TASK_ID or d['source_protocol_sha256']!=SOURCE_PROTOCOL_SHA or not hexhash(d['generation_commitment']):raise ValueError('Bound complete public panel')
    if d['panel_id']!=digest({k:v for k,v in d.items() if k!='panel_id'}):raise ValueError('Public generation fingerprint')
    expected=contexts()
    if not isinstance(d['contexts'],list) or len(d['contexts'])!=len(expected):raise ValueError('All770 classification contexts required')
    for r,e in zip(d['contexts'],expected):
        if set(r)!=set(e)|{'query_count','query_ids_sha256'} or any(r.get(k)!=v for k,v in e.items()) or type(r['query_count']) is not int or not 1<=r['query_count']<=200000 or not hexhash(r['query_ids_sha256']):raise ValueError('Complete source context identity/support')
    return d


def outputs(public):
    for arm in ARMS:
        for context in public['contexts']:
            for model in MODELS+(('improved',) if context['protocol']=='chronological' else ()):
                yield dict(context,arm=arm,model=model)

SOURCE_PROTOCOL_SHA='4efa128d8dc7d81c5cb560f0b422e4aecef18fe2d3db442e18bbf431c2ff60a2'

RECORDINGS={1:'sub_1_trial001',2:'sub_2_trial006',3:'sub_3_trial000',4:'sub_4_trial000',6:'sub_6_trial004',7:'sub_7_trial000',10:'sub_10_trial000'}
