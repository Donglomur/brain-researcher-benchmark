"""Disjoint fit/query source views, same views for all owners and F/I."""
from pathlib import Path
import delivery_io as io
import protocol as p
def split_view(whole,fit,infer,owner):
 with owner.stage('split_exact_public_views'):
  whole=Path(whole);v=io.json_file(whole/'VIEW.json',40_000_000)
  io.need(v['format']=='neural062_view_v1'and v['feature_names']==list(p.names(v['arm'])),'whole view ABI')
  fit=io.fresh(fit);infer=io.fresh(infer)
  for phase,dest,name in [('fit',fit,'train.npy'),('infer',infer,'query.npy')]:
   row=v['arrays'][name];expected={k:row[k]for k in('bytes','sha256')}
   io.copy_exact(whole/name,dest/name,expected)
   doc={'format':'neural062_phase_view_v1','phase':phase,'generation':v['generation'],'case':v['case'],'arm':v['arm'],'feature_names':v['feature_names'],'classes':v['classes'],'array':row,'array_name':name}
   if phase=='infer':doc['query_ids']=v['query_ids']
   else:
    groups=io.json_file(whole/'TRAIN_GROUPS.json',16_000_000)
    io.need(groups['schema']=='neural062.train-mouse-groups.v1'and groups['rows']==row['shape'][0],'training group support')
    doc['groups_pin']=io.put(dest/'TRAIN_GROUPS.json',groups,16_000_000)
   io.put(dest/'VIEW.json',doc,40_000_000)
  return fit,infer
