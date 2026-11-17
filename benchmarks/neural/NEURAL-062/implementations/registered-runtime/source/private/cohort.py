"""Exact external cohort and hierarchy joins. Never builds a replacement cohort."""
from collections import Counter
import delivery_io as io
import protocol as p
def validate(cohort,assets):
 io.need(cohort['release']=='visual-behavior-ophys1.1.0'and len(cohort['rows'])==1936,'full fixed release')
 rows=cohort['rows'];exps={};sessions={};containers={};cells={};mice={}
 for r in rows:
  p.static(r);e=r['ophys_experiment_id'];m=r['mouse_id'];s=r['ophys_session_id'];c=r['ophys_container_id']
  io.need(e not in exps and r['image_set']in p.SETS and r['split']in('train','validation','test'),'original experiment identity')
  exps[e]=r
  identity=(m,r['split'])
  io.need(m not in mice or mice[m]==r['split'],'mouse split closure');mice[m]=r['split']
  io.need(s not in sessions or sessions[s]==identity,'session cannot cross mouse/split');sessions[s]=identity
  io.need(c not in containers or containers[c]==identity,'container cannot cross mouse/split');containers[c]=identity
  seen=set()
  for roi,cell in r['published_rois']:
   io.need(type(roi)is int and type(cell)is int and roi not in seen,'unique published ROI');seen.add(roi)
   io.need(cell not in cells or cells[cell]==(m,c),'registered cell lineage remains within mouse/container');cells[cell]=(m,c)
  io.need(seen,'source valid ROI population cannot be replaced')
 io.need(len(sessions)==703 and len(mice)==107 and Counter(mice.values())=={'train':73,'validation':15,'test':19},'complete mouse/session/split counts')
 io.need(cohort['mouse_splits']==mice and len(cells)==50476 and sum(len(r['published_rois'])for r in rows)==133066,'exact cohort census')
 assetmap={a['experiment']:a for a in assets}
 io.need(len(assetmap)==1936 and set(assetmap)==set(exps),'full asset-source join')
 io.need(len({a['path']for a in assets})==1936,'distinct original source paths')
 for e,r in exps.items():io.need(assetmap[e]['blake2b_512']==r['asset']['file_hash'],'original provider source hash')
 return exps,assetmap
