"""Full main+supplement MindBridge primary panel. Source-derived protocol; native numerical parity unqualified."""
SUBJECTS=(1,2,5,7)
BUDGETS=(500,1500,4000)
N_TEST=982
TRAIN_RELEASE=8559
VALIDATION_RELEASE=300
RECONSTRUCTION_DRAWS=8
METRICS=('pixel_correlation','ssim','alexnet2','alexnet5','inception','clip','efficientnet_distance','swav_distance')

def cases():
 out=[]
 for subject in SUBJECTS:
  for mode in ('single','bridge'):
   out.append({'case_id':f'main_{mode}_s{subject:02d}','family':'main','mode':mode,'subject':subject,'budget':None,'source_subjects':list(SUBJECTS)if mode=='bridge'else[subject]})
  for budget in BUDGETS:
   for mode in ('scratch','reset'):
    out.append({'case_id':f'adapt_{mode}_s{subject:02d}_k{budget:04d}','family':'adaptation','mode':mode,'subject':subject,'budget':budget,'source_subjects':[x for x in SUBJECTS if x!=subject]if mode=='reset'else[]})
 return out

CASES=tuple(r['case_id']for r in cases())

def paired_cases():
 pairs=[]
 for s in SUBJECTS:
  pairs.append((f'main_bridge_s{s:02d}',f'main_single_s{s:02d}'))
  for k in BUDGETS:pairs.append((f'adapt_reset_s{s:02d}_k{k:04d}',f'adapt_scratch_s{s:02d}_k{k:04d}'))
 return pairs

IMAGE_SIZE=512
CHUNK=16

def chunks(n=N_TEST):
 return [(start,min(n,start+CHUNK))for start in range(0,n,CHUNK)]
