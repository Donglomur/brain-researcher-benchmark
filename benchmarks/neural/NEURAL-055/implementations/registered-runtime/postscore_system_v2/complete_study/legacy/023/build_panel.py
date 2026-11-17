"""Assemble only the ten grading case rosters/targets after case preparation.

No EEG copying, prediction execution or scoring. This operator bundle is not a
candidate mount; each candidate receives only its single outer-fold public case.
"""
import argparse
import json
import sys
from pathlib import Path
from source_io import descriptor, save_json
from build_case import local_descriptor, copy_pinned
from metadata_core import PARTICIPANTS
PACKAGE_ROOT=Path(__file__).resolve().parents[1]
if not (PACKAGE_ROOT/'public').is_dir():PACKAGE_ROOT=PACKAGE_ROOT.parent
sys.path.insert(0,str(PACKAGE_ROOT/'public'))
from interface import opaque_id,validate_case,decode_json


def build(roots,output):
    if len(roots)!=10:raise ValueError('ten prepared outer cases required')
    collected=[];people=set();ids=set()
    for root in roots:
        r=Path(root);m=json.loads((r/'PREPARED.json').read_text())
        if m.get('schema')!='neural055-prepared-case-v1' or m['outer_participant'] in people or m['case_id'] in ids:raise ValueError('complete distinct prepared cases required')
        opaque_id(m['case_id'])
        case_path=local_descriptor(r,m['public_case']);target_path=local_descriptor(r,m['private_target'])
        case=validate_case(decode_json(case_path.read_bytes()));target=decode_json(target_path.read_bytes())
        if case['case_id']!=m['case_id'] or type(target) is not dict or set(target)!={'schema','case_id','query_to_candidate'} or target['schema']!='neural055-private-target-v1' or target['case_id']!=m['case_id']:
            raise ValueError('prepared/public/private case identity mismatch')
        join=target['query_to_candidate']
        if type(join) is not dict or set(join)!=set(case['query_ids']) or any(type(x) is not str for x in join.values()) or len(set(join.values()))!=200 or set(join.values())!=set(case['candidate_ids']):
            raise ValueError('complete private bijection matching public case required')
        people.add(m['outer_participant']);ids.add(m['case_id'])
        collected.append((m['case_id'],case_path,target_path))
    if people!=set(PARTICIPANTS):raise ValueError('all ten original people required')
    out=Path(output);out.mkdir(parents=False,exist_ok=False);pub=out/'public';priv=out/'private';pub.mkdir();priv.mkdir()
    public=[];private={}
    for ident,case,target in sorted(collected):
        cp=pub/(ident+'.json');tp=priv/(ident+'.json');copy_pinned(case,cp);copy_pinned(target,tp)
        public.append(descriptor(cp,pub));private[ident]=descriptor(tp,priv)
    save_json(pub/'PANEL.json',{'schema':'neural055-public-panel-v1','cases':public})
    save_json(priv/'PANEL.json',{'schema':'neural055-private-panel-v1','cases':private})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--case-root',action='append',required=True);p.add_argument('--output',required=True);a=p.parse_args();build(a.case_root,a.output)
