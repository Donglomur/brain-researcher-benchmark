"""Versioned full-cohort identity conversion only; no neural/behavior response values."""
from pathlib import Path
import csv,hashlib,json
import delivery_io as io

def split_map(rows):
 mice={}
 for r in rows:
  v=(r['cre_line'],r['project_code']);io.need(r['mouse_id'] not in mice or mice[r['mouse_id']]==v,'One mouse/genotype/project');mice[r['mouse_id']]=v
 splits={}
 for cre in sorted({v[0] for v in mice.values()}):
  ids=sorted([k for k,v in mice.items() if v[0]==cre],key=lambda s:hashlib.sha256(('allen-visual-behavior-v1:'+s).encode()).hexdigest());a=int(.7*len(ids));b=a+int(.15*len(ids))
  for i,m in enumerate(ids):splits[m]='train' if i<a else 'validation' if i<b else 'test'
 return splits

def convert(source):
 source=Path(source);manifest=io.json_file(source/'project_manifest_v1.1.0.json',3000000,{'bytes':2455839,'sha256':'8cb641fb26da107334b99d9521e12add1b33015316cb80d5df4559987315222a'})
 def table(name):
  body=io.read(source/(name+'.csv'),10000000);io.need(hashlib.blake2b(body).hexdigest()==manifest['metadata_files'][name]['file_hash'],'Original metadata BLAKE2b');return list(csv.DictReader(body.decode().splitlines()))
 rows=table('ophys_experiment_table');sessions=table('ophys_session_table');cells=table('ophys_cells_table');io.need(len(rows)==1936 and len({r['mouse_id'] for r in rows})==107 and len({r['ophys_session_id'] for r in rows})==703,'Fullv1.1.0 cohort');split=split_map(rows);by={r['ophys_experiment_id']:r for r in rows};io.need(len(by)==1936,'Unique experiment IDs')
 parent={};lineage={};published={k:[] for k in by}
 for r in rows:
  k=r['ophys_container_id'];io.need(k not in parent or parent[k]==r['mouse_id'],'Containers cannot cross mice');parent[k]=r['mouse_id']
 for c in cells:
  r=by[c['ophys_experiment_id']];v=(r['mouse_id'],r['ophys_container_id']);k=c['cell_specimen_id'];io.need(k not in lineage or lineage[k]==v,'Registered cell cannot cross mouse/container');lineage[k]=v;published[r['ophys_experiment_id']].append([int(c['cell_roi_id']),int(c['cell_specimen_id'])])
 out=[]
 for r in rows:
  d=manifest['data_files'][r['file_id']];io.need(d['url'].endswith('/behavior_ophys_experiment_'+r['ophys_experiment_id']+'.nwb'),'Exact metadata->NWB identity');io.need(r['image_set'] in('A','B','G','H') and r['session_type'].startswith('OPHYS_'),'Image-session full selection')
  out.append({**r,'split':split[r['mouse_id']],'asset':d,'bytes':248144826 if r['ophys_experiment_id']=='951980471' else None,'published_rois':sorted(published[r['ophys_experiment_id']])})
 counts={s:{'mice':sum(v==s for v in split.values()),'experiments':sum(r['split']==s for r in out),'sessions':len({r['ophys_session_id'] for r in out if r['split']==s})} for s in('train','validation','test')}
 return {'release':'visual-behavior-ophys1.1.0','rows':out,'mouse_splits':split,'counts':counts,'source_validity':'All1936released experiments included; per-event validity/support unqualified until authentic projection','source_neural_values_read':False,'lineages':len(lineage),'published_cell_rows':len(cells),'source_bytes_total':None}
if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--source',required=True);a.add_argument('--output',required=True);q=a.parse_args();d=convert(q.source);io.put(q.output,d,16000000);print(json.dumps({'counts':d['counts'],'lineages':d['lineages'],'published_cell_rows':d['published_cell_rows']}))
