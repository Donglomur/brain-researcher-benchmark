"""Artifact reconstruction grading; never runs the analysis reference."""
import argparse
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from protocol import validate_report,CELL_KEYS,CONTRAST_KEYS
from io_utils import read_json,write_json


def grade(candidate,participants,reference_loader):
    validate_report(candidate,participants)  # complete admission before private callback
    reference=reference_loader();validate_report(reference,participants)
    rows={}
    for p in participants:
        a=candidate['participants'][p];b=reference['participants'][p]
        rows[p]={'cell_mae':math.fsum(abs(a['cells'][k]-b['cells'][k]) for k in CELL_KEYS)/len(CELL_KEYS),
                 'contrast_mae':math.fsum(abs(a['contrasts'][k]-b['contrasts'][k]) for k in CONTRAST_KEYS)/len(CONTRAST_KEYS)}
    summary={}
    for key in CONTRAST_KEYS:
        values=[candidate['participants'][p]['contrasts'][key] for p in participants]
        mean=math.fsum(values)/len(values)
        sd=math.sqrt(math.fsum((v-mean)**2 for v in values)/(len(values)-1))
        summary[key]={'equal_participant_mean':mean,'participant_sd':sd,
                      'descriptive_se':sd/math.sqrt(len(values)),'n_participants':len(values)}
    return {'schema':'neural098-grade-v1','status':'scored','primary_cell_mae':math.fsum(r['cell_mae'] for r in rows.values())/len(rows),
            'secondary_contrast_mae':math.fsum(r['contrast_mae'] for r in rows.values())/len(rows),
            'per_participant':rows,'candidate_temporal_contrasts':summary,
            'p_values':None,'multiplicity':'All24 prespecified signed contrasts reported; no significance selection or threshold.',
            'method_execution_authenticated':False,'empirical_runtime_qualified':False}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--submission',type=Path,required=True);ap.add_argument('--reference',type=Path,required=True);ap.add_argument('--reference-sha256',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    if a.output.exists() or a.output.is_symlink():raise ValueError('fresh output required')
    participants=read_json(Path(__file__).resolve().parents[1]/'public/COHORT.json')[0]['participants']
    state={'reference_invoked':False};candidate_sha=None
    def load():
        state['reference_invoked']=True
        return read_json(a.reference,expected=a.reference_sha256)[0]
    try:
        candidate,candidate_sha=read_json(a.submission)
        result=grade(candidate,participants,load)
    except (ValueError,TypeError,KeyError,OSError,UnicodeError,RecursionError,OverflowError) as error:
        result={'schema':'neural098-grade-v1','status':'operator_error' if state['reference_invoked'] else 'invalid_submission',
                'primary_cell_mae':None,'secondary_contrast_mae':None,'error_type':type(error).__name__}
    result.update(state);result['submission_sha256']=candidate_sha
    write_json(a.output,result)
    if result['status']!='scored':raise SystemExit(2)


if __name__=='__main__':main()
