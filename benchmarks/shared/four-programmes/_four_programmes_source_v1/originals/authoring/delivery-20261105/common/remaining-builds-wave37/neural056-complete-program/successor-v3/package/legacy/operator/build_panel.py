"""Future deterministic packet binding, not training or scientific evaluation.
All ten records, all image identities and a complete frozen representation are
required. The produced collection is OPERATOR ONLY; stage one outer view.
"""
import argparse,sys,json,shutil
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from common import PEOPLE,ARMS,need,canonical,digest,hash_ok
from array_io import capture,metadata,arrays,identity,fresh_output
from roster import make
from source_bindings import checked_metadata,check_staged_people

def build(staged,features,meta,out):
 fresh_output(out);staged=Path(staged);features=Path(features);out=Path(out);m=checked_metadata(metadata(meta,2_000_000));roster=make(m);fm=metadata(features/'FEATURES.json');need(fm['schema']=='neural056_features_v1' and fm['image_metadata_sha256']==digest(m),'Exact feature/sourcejoin');need(hash_ok(fm['checkpoint_sha256']) and hash_ok(fm['extraction_source_sha256']),'Fixed representation before outcomes')
 need(fm['representation']=='alexnet_relu7_4096_resize224_imagenet_normalization','Selected representation')
 need(set(fm['arrays'])=={'train','test'},'Two completefeaturepartitions')
 for part,n in [('train',16540),('test',200)]:
  b=capture(features/(part+'.npz'),330_000_000);need(identity(b)==fm['arrays'][part],'Feature pin');v=arrays(b,('representation','low_level'),330_000_000);need(v['representation'].shape==(n,4096) and v['low_level'].shape==(n,768) and all(x.dtype.kind=='f' and np.isfinite(x).all() for x in v.values()),'Full imagefeatures')
  del b,v
 people={};coordinate=None;sourcepins=[]
 for person in PEOPLE:
  r=metadata(staged/person/'STAGED.json');need(r['person']==person and r['schema']=='neural056_staged_person_v1','Actual personjoin')
  if coordinate is not None:need(r['coordinates']==coordinate,'Allten exactcoordinateagreement')
  coordinate=r['coordinates'];people[person]=r;sourcepins.append(r['archive']['sha256'])
 check_staged_people(people)
 # Authenticated files are copied opaquely; private target data are never in a public union.
 out.mkdir();(out/'people').mkdir();(out/'features').mkdir();targets={}
 (out/'targets').mkdir()
 for person,r in people.items():
  (out/'people'/person).mkdir()
  for part in ['train','test']:
   b=capture(staged/person/(part+'.npz'),230_000_000);need(identity(b)==r['arrays'][part],'Full staged pin')
   dest=out/'people'/person/'train.npz' if part=='train' else out/'targets'/(person+'.npz');dest.write_bytes(b)
  targets[person]=r['arrays']['test']
 for part in ['train','test']:
  b=capture(features/(part+'.npz'),330_000_000);need(identity(b)==fm['arrays'][part],'Same bound feature bytes');(out/'features'/(part+'.npz')).write_bytes(b)
 design={'schema':'neural056_design_v1','task_id':'NEURAL-056','people':list(PEOPLE),'arms':list(ARMS),'query_image_ids':[x['image_id'] for x in roster['test']],'coordinates':{**coordinate,'source_binding_sha256':digest(people)},'roster_sha256':digest(roster),'feature_binding_sha256':digest(fm)}
 (out/'design.json').write_bytes(canonical(design));(out/'ROSTER.json').write_bytes(canonical(roster));(out/'PEOPLE.json').write_bytes(canonical(people));(out/'FEATURES.json').write_bytes(canonical(fm));(out/'TARGETS.json').write_bytes(canonical({'design_sha256':digest(design),'targets':targets}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--staged',required=True);p.add_argument('--features',required=True);p.add_argument('--metadata',required=True);p.add_argument('--output',required=True);a=p.parse_args();build(a.staged,a.features,a.metadata,a.output)
