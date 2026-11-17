"""Assemble exact operator-owned episode metadata after baseline production.
No models, target values, numerical scoring or candidate process is executed.
"""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from delivery_io import need,read,decode,pin,put,resolve
from array_io import fresh_output
from protocol import FOLD_IDS,ARMS
from score import binding_admit


def collect(root,selection_path,output):
    fresh_output(output);sel=decode(read(selection_path,1000000));need(list(sel['episodes'])==FOLD_IDS,'All70 explicitly selected episodes')
    episodes={}
    for eid,row in sel['episodes'].items():
        def meta(r):return decode(read(resolve(root,r['path']),2000000,{k:r[k] for k in ('bytes','sha256')}))
        b=meta(row['binding']);m=meta(row['baseline_metadata'])
        need(m['case_sha256']==pin(__import__('delivery_io').canonical(b['case']))['sha256'] and m['baselines']=={k:row['baselines'][k] for k in ('bytes','sha256')},'Same public case and baseline identity')
        need(set(m['selected'])==set(ARMS[1:]),'Full four baseline recipes')
        # Paths are supplied explicitly relative to one operator collection; no discovery.
        need({k:row['target'][k] for k in ('bytes','sha256')}=={k:b['target'][k] for k in ('bytes','sha256')},'Target identity')
        episodes[eid]={'case':b['case'],'source_rows':b['source_rows'],'target':row['target'],'baselines':row['baselines']}
    d={'schema':'language_episodes_v1','design_sha256':sel['design_sha256'],'episodes':episodes};binding_admit(d,sel['design_sha256']);put(output,d,32*1024**2)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--selection',required=True);p.add_argument('--output',required=True);a=p.parse_args();collect(a.root,a.selection,a.output)
