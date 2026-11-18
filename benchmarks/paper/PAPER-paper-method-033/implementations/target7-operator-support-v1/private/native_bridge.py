"""Command construction only. Never launches author code or downloads models.
Expanded four-target matrix is a source-derived recipe, not observed paper runs.
"""
import hashlib
from pathlib import Path
import delivery_io as d,protocol as p
ROOT=Path(__file__).resolve().parent

def source_root():
 for q in (ROOT.parent/'source/official',ROOT.parent/'public/author_code'):
  if q.is_dir():return q
 raise ValueError('Pinned official source absent')

def check_source():
 doc=d.json_file(ROOT/'CODE_PROVENANCE.json',100000)
 for r in doc['files']:d.read(source_root()/r['path'],r['bytes'],{k:r[k]for k in('bytes','sha256')},empty=r['bytes']==0)
 return doc['commit']

def commands(data_root,python='python'):
 check_source();jobs=[]
 def add(name,subjects,epochs,lr,length=None,adapt=None):
  argv=[python,'main.py','--model_name',name,'--data_path',str(data_root),'--subj_list',*[str(s)for s in subjects],'--num_epochs',str(epochs),'--batch_size','50','--val_batch_size','50','--h_size','2048','--n_blocks','4','--pool_type','max','--pool_num','8192','--mse_mult','10000','--max_lr',str(lr),'--eval_interval','10','--ckpt_interval','10','--seed','42','--no-wandb_log']
  if len(subjects)>1:argv+=['--rec_mult','1','--cyc_mult','1']
  if length is not None:argv+=['--length',str(length)]
  if adapt is not None:argv+=['--adapting','--subj_source',*[str(s)for s in subjects if s!=adapt],'--subj_target',str(adapt),'--load_from',f'../train_logs/pretrain_without_s{adapt:02d}/last.pth']
  jobs.append({'name':name,'argv':argv,'cwd':'public/author_code/src','completed':False})
 add('joint_1257',p.SUBJECTS,600,1.5e-4)
 for s in p.SUBJECTS:
  add(f'single_s{s:02d}',[s],600,3e-4);add(f'pretrain_without_s{s:02d}',[v for v in p.SUBJECTS if v!=s],600,1.5e-4)
  for k in p.BUDGETS:
   add(f'adapt_reset_s{s:02d}_k{k:04d}',[v for v in p.SUBJECTS if v!=s]+[s],200,1.5e-4,k,s)
   add(f'adapt_scratch_s{s:02d}_k{k:04d}',[s],200,3e-4,k)
 return {'jobs':jobs,'not_launched':True,'completed':False,'native_distributed_topology_unbound':True,
 'limitations':['Original joint/single scripts use8/2 processes and multiply learning rate by process count; this command list does not silently equate another topology.','Only target7/4000 is scripted upstream; matrix expansion follows full paper panel, not authenticated per-case published commands.','Original command abbreviations are expanded; no original file edited.','All checkpoints, captions, CLIP/VD assets and numeric environment remain unbound; offline isolated runtime required.']}
if __name__=='__main__':
 import argparse,json
 a=argparse.ArgumentParser();a.add_argument('--data-root',required=True);z=a.parse_args();print(json.dumps(commands(z.data_root),indent=2))
