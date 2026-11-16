"""Actual operator observation receipt→target-free native query descriptor."""
from pathlib import Path
from preprocessing_current.observations import row_lineage
from .policy import DATASETS,exact,need,relative,sha

def query_descriptor(observations,canonical_dataset_query,full_query_sha256,relative_owner):
 need(observations['schema']=='cbramod_target_free_observations_v2'and observations['split']=='test','operator assessment observation receipt')
 dataset=observations['dataset_id'];need(dataset in DATASETS and canonical_dataset_query['id']==dataset,'dataset/query join')
 need(observations['contains_target_labels']is False,'target-free exported observation role')
 lineage=observations['lineage'];expected=row_lineage(dataset,'test',lineage['source_keys'],lineage['group_by_key'])
 need(lineage==expected,'actual source-key/epoch lineage identity')
 rows=[{'id':r['id'],'group':r['group']}for r in lineage['rows']]
 need(rows==canonical_dataset_query['rows'],'full exact frozen assessment order; no subset/reordering')
 sha(full_query_sha256);relative(relative_owner)
 f=observations['signal_file'];exact(f,('path','shape','dtype','bytes','sha256','fortran_order'));relative(f['path']);sha(f['sha256'])
 need(f['dtype']=='<f4'and f['fortran_order']is False,'official-collate-compatible numeric observation bank')
 d=DATASETS[dataset];shape=[len(lineage['source_keys']),20,6,6000]if dataset=='ISRUC'else[len(rows),d[3],d[4],200]
 need(f['shape']==shape,'exact model/observation geometry')
 return {'path':relative_owner+'/'+f['path'],'shape':f['shape'],'dtype':f['dtype'],'bytes':f['bytes'],'sha256':f['sha256'],
  'row_ids':[r['id']for r in rows],'groups':[r['group']for r in rows],
  'lineage_sha256':lineage['lineage_sha256'],'query_sha256':full_query_sha256}
