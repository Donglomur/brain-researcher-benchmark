"""Artifact-only scorer. All public predictions validated before private numeric read."""
import argparse,json,pathlib,sys
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'public/common'))
from artifact_io import Invalid,capture,strict_json,read_predictions
from bindings import sha,bound,fresh,write_json
from program_io import validate_panel
from metrics import evaluate

def validate_public(submission,panel_bytes):
    panel=strict_json(panel_bytes)
    if panel.get('schema')!='trial_session_panel_v1' or panel.get('condition')!='re40_prospective_known_session':raise RuntimeError('operator panel condition')
    if submission.is_symlink() or not submission.is_dir():raise Invalid('ordinary submission directory required')
    if {p.name for p in submission.iterdir()}!={'submission.json','predictions.npy'}:raise Invalid('exact two-file submission required')
    meta=strict_json(capture(submission/'submission.json',16384))
    if type(meta)is not dict or set(meta)!={'schema','panel_sha256','methods','method_provenance'} or meta['schema']!='trial_session_submission_v1' or meta['panel_sha256']!=sha(panel_bytes) or meta['methods']!=panel['methods']:raise Invalid('exact panel/method binding required')
    mp=meta['method_provenance']
    if type(mp)is not dict or set(mp)!=set(panel['methods']) or any(type(v)is not str or not 1<=len(v)<=2000 for v in mp.values()):raise Invalid('bounded method provenance text required')
    n=panel['prediction_rows'];b=capture(submission/'predictions.npy',min(1_000_000_000,n*len(panel['methods'])*8+2048))
    pred=read_predictions(b,(n,len(panel['methods'])))
    for c in panel['cases']:
        if c['target']=='choice':
            x=pred[slice(*c['offset'])]
            if np.any((x<0)|(x>1)):raise Invalid('choice probabilities must be in[0,1]')
    return panel,pred

def grade(submission,panel_path,reference_path):
    try:
        pb=capture(panel_path,10_000_000);panel=strict_json(pb)
        validate_panel(panel,capture(ROOT/'public/common/PROTOCOL.json',100000))
    except Invalid as e:raise RuntimeError('operator panel violates full protocol') from e
    panel,pred=validate_public(submission,pb)
    # Only after the entire public artifact has passed, cross the private boundary.
    ref=strict_json(capture(reference_path,1_000_000))
    if ref.get('schema')!='trial_session_reference_v1' or ref.get('panel_sha256')!=sha(pb):raise RuntimeError('operator reference/panel mismatch')
    try:
        y=read_predictions(bound(reference_path.parent,ref['truth']),(panel['prediction_rows'],))
        t=read_predictions(bound(reference_path.parent,ref['template']),(panel['prediction_rows'],))
        g=read_predictions(bound(reference_path.parent,ref['groups']),(panel['group_rows'],3))
    except Invalid as e:raise RuntimeError('operator private binding invalid') from e
    for c in panel['cases']:
        if c['target']=='choice' and not np.isin(y[slice(*c['offset'])],[0.,1.]).all():raise RuntimeError('operator binary truth invalid')
    return {'status':'scored','panel_sha256':sha(pb),'candidate_execution_verified':False,'scientific_qualification':False,'metrics':evaluate(panel,y,t,g,pred)}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--submission',type=pathlib.Path,required=True);ap.add_argument('--panel',type=pathlib.Path,required=True);ap.add_argument('--reference',type=pathlib.Path,required=True);ap.add_argument('--output',type=pathlib.Path,required=True);a=ap.parse_args()
    fresh(a.output) # reject existing/dangling output before private or candidate reads
    try:out=grade(a.submission,a.panel,a.reference)
    except Invalid as e:out={'status':'invalid_submission','reason':str(e)}
    except Exception as e:out={'status':'operator_error','reason':type(e).__name__}
    write_json(a.output,out)

if __name__=='__main__':main()
