"""Emit a source-bound future command recipe; never import or execute author code."""
import argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'public'))
from io_contract import *
from author_source import verify

CONFIGS={'pretraining':'configs/Visnav/lateral/mconf_pretrain.yaml',
         'joint_behavior':'configs/Visnav/lateral/mconf_predict_all.yaml'}
INPUTS=('spikerates_dt_0.01.npy','behavior_speed_dt_0.05.npy','stimulus.npy','phi_dt_0.05.npy','th_dt_0.05.npy')

def plan(condition,seed):
    require(condition in CONFIGS,'one supplied lateral native configuration')
    require(type(seed) is int and 0<=seed<2**32,'exact nonnegative native seed')
    pins=verify()
    return {'schema':'neuroformer_native_source_recipe_v1','task_id':TASK,'source':pins,
      'condition':condition,'dataset':'lateral','working_directory':'a separately provisioned exact official_code copy',
      'training_argv':['python','neuroformer_train.py','--dataset','lateral','--config',CONFIGS[condition],'--seed',str(seed),'--title',condition],
      'inference_argv':['python','neuroformer_inference.py','--dataset','lateral','--seed',str(seed),'--ckpt_path','OPERATOR_SELECTED_OWN_CHECKPOINT'],
      'native_required_inputs':['data/VisNav_VR_Expt/LateralVRDataset/NF_1.5/'+p for p in INPUTS],
      'may_execute':False,'programs_invoked':0,
      'blockers':['Exact original arrays, clocks, units, full cohort/session identities and own checkpoint absent.',
        'Native random split and current configuration differ from paper and prospective qualified bridge; no hidden-test conversion supplied.',
        'Original train entrypoint evaluates test_dataset; fine-tune flags do not select finetune_dataset.',
        'Original inference generates on finetune_dataset and then overwrites predict_modes with speed/phi/th.',
        'Original get_interval ignores passed generated history; true_past=False does not certify recursive rollout.',
        'Native environment unbuilt; telemetry/download behavior must be isolated and independently qualified before use.',
        'This lateral recipe supplies no authenticated medial config or full baseline/few-shot/ablation run mapping.']}

def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--condition',choices=CONFIGS,required=True);a.add_argument('--seed',type=int,required=True)
    x=a.parse_args();print(encode(plan(x.condition,x.seed)).decode(),end='')
if __name__=='__main__':main()
