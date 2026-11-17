"""Exact017 profile; qualified ownership and expanded bounded NPZ transport."""
from pathlib import Path
import hashlib,json,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
SHARED=ROOT/'authoring/shared-program-runner-v2'
LARGE=ROOT/'authoring/shared-large-npz-runner-v1'
OWNERS=ROOT/'authoring/shared-program-ownership-v3'
sys.path.insert(0,str(SHARED));sys.path.insert(0,str(LARGE))
from qualified_core import HostBudget,snapshot,digest,recover_unit,DOCKER,ENV
from unit import run_unit
from profile import need
sys.path.insert(0,str(OWNERS))
from process_owner import launch,stop,read,atomic
from trusted_controller import validate_controller
sys.path.insert(0,str(HERE))

def source_check():
    freeze=json.loads((HERE/'FREEZE.json').read_text())
    for rel,pin in freeze['files'].items():
        p=ROOT/rel
        need(all(not x.is_symlink()for x in(p,*p.parents))and p.is_file()and p.stat().st_nlink==1 and p.stat().st_size==pin['bytes']and digest(p)==pin['sha256'],'Frozen source identity: '+rel)
    return digest(HERE/'FREEZE.json')

def load_profile():
    return validate_profile(json.loads((HERE/'profile.json').read_text()),json.loads((ROOT/'benchmarks/neuroscience/neural-017/assets.json').read_text()))

def validate_profile(value,assets):
    need(value['candidate_id']=='NEURAL-017'and value['operator_only_profile']is True and value['mode']=='fixed_program_full_panel_retrospective_cosmoothing','Exact co-smoothing task')
    validate_controller(value['controller'],[sys.executable,str(HERE/'driver.py')])
    unit=value['unit'];pin=assets['public']['packet']
    expected={'path':pin['path'],'bytes':pin['bytes'],'sha256':pin['sha256'],'mount_destination':'/input/public.npz','read_only':True}
    need(unit=={'unit_id':'batch-00','public_inputs':[expected],'output_filename':'predictions.npz','max_output_bytes':33554432},'Exactly one full public packet and one bounded prediction archive')
    need(value['input_bytes']==113599728 and value['raw_nwb_permitted']is False and value['private_targets_permitted']is False and value['prior_predictions_permitted']is False,'No raw, private or previous prediction input')
    return value

def opaque_boundary(body,unit):
    # Semantic ZIP/NPY, rate/ID/clock validation occurs in the qualified isolated
    #017 scorer before numerical private targets are loaded. This is no score.
    need(type(body)is bytes and 0<len(body)<=unit['max_output_bytes'],'Bounded nonempty opaque submission')

def save(path,value,budget):
    body=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    need(len(body)<=300000,'Bounded operator receipt')
    budget.write(path,body,receipt=True)
