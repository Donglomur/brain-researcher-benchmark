"""Join full independently prepared source panels; no signal-body reads or copies."""
import argparse,hashlib
from pathlib import Path
import io_contract as io
import analysis
import scientific_contract as scientific

def combine(chb_raw,siena_raw,chb_targets,siena_targets):
 rows=[];targets=[];mounts=[]
 for raw,gold_raw,task,cohort in [(chb_raw,chb_targets,'NEURAL-009','CHB'),(siena_raw,siena_targets,'NEURAL-011','Siena')]:
  p=io.strict(raw);io.fields(p,['schema_version','task_id','records']);io.need(type(p['schema_version'])is int and p['schema_version']==1 and p['task_id']==task,'prepared source panel identity')
  g=io.strict(gold_raw);io.fields(g,['schema_version','task_id','panel_sha256','records']);io.need(g['task_id']==task and type(g['schema_version'])is int and g['schema_version']==1 and g['panel_sha256']==hashlib.sha256(raw).hexdigest(),'exact source target-panel join');gold={}
  for r in g['records']:
   io.fields(r,['recording_id','events']);io.need(type(r['recording_id'])is str and r['recording_id'] not in gold,'unique source target');gold[r['recording_id']]=r['events']
  ids=set()
  for r in p['records']:
   io.fields(r,['recording_id','patient_id','duration_seconds','observed_intervals','path','bytes','sha256']);rid=r['recording_id'];io.need(rid not in ids and r['observed_intervals']==[[0,r['duration_seconds']]],'entire observed recording');ids.add(rid);io.need(rid in gold,'source annotation support');analysis.interval_list(gold[rid],r['duration_seconds'])
   rows.append({'recording_id':rid,'patient_id':r['patient_id'],'cohort':cohort,'duration_seconds':r['duration_seconds'],'montage_sha256':'0'*64,'signal':{'file':r['path'],'bytes':r['bytes'],'sha256':r['sha256']}})
   targets.append({'recording_id':rid,'events':gold[rid]});mounts.append({'recording_id':rid,'cohort':cohort,'file':r['path'],'bytes':r['bytes'],'sha256':r['sha256']})
  io.need(ids==set(gold),'complete source targets')
  if cohort=='Siena':io.need(len(ids)==41 and sum(len(x) for x in gold.values())==47,'all41 Siena recordings and47 original event entries')
 # Montage identities must be supplied from trusted header inventory, not fabricated.
 return rows,targets,mounts

def source_join_binding(chb_raw,siena_raw,chb_targets,siena_targets,reference,siena_preparation_profile):
 return scientific.digest({'chb_panel_sha256':hashlib.sha256(chb_raw).hexdigest(),'siena_panel_sha256':hashlib.sha256(siena_raw).hexdigest(),'chb_targets_sha256':hashlib.sha256(chb_targets).hexdigest(),'siena_targets_sha256':hashlib.sha256(siena_targets).hexdigest(),'reference_sha256':scientific.digest(reference),'siena_preparation_profile_sha256':scientific.digest(siena_preparation_profile)})

def bind(chb_raw,siena_raw,chb_targets,siena_targets,reference,source_qualification_sha256,siena_preparation_profile,source_owner=None):
 from source_validation import SourceValidationOwner
 io.need(type(source_owner)is SourceValidationOwner,'original complete source-validation owner before joined output')
 rows,targets,mounts=combine(chb_raw,siena_raw,chb_targets,siena_targets)
 scientific.validate_reference(reference);by_id={r['recording_id']:r for r in reference['records']}
 io.need(set(by_id)=={r['recording_id'] for r in rows},'all727 per-record physical declarations')
 for row in rows:
  row['montage_sha256']=by_id[row['recording_id']]['montage_sha256']
 scientific.validate_reference(reference,rows);profile=reference['scientific_profile'];profile_pin=scientific.profile_sha256(profile)
 s=siena_preparation_profile;io.fields(s,['schema','scientific_profile','panel_sha256','targets_sha256','clock_records_sha256','release_whitelists_sha256','source_qualification_sha256','authority_status'])
 io.need(s['schema']=='siena_preparation_profile_v1' and s['authority_status']=='unissued' and s['scientific_profile']==profile and s['panel_sha256']==hashlib.sha256(siena_raw).hexdigest() and s['targets_sha256']==hashlib.sha256(siena_targets).hexdigest(),'Siena label profile joins exact projected panel and targets; no C1/C2 substitution')
 for k in ('clock_records_sha256','release_whitelists_sha256','source_qualification_sha256'):scientific.pin(s[k])
 scientific.pin(source_qualification_sha256)
 io.need(source_qualification_sha256==source_join_binding(chb_raw,siena_raw,chb_targets,siena_targets,reference,s),'exact full-source qualification request binding, not an issued proof')
 p={'schema_version':2,'task_id':io.TASK,'scientific_profile':profile,'source_qualification_sha256':source_qualification_sha256,'records':sorted(rows,key=lambda x:x['recording_id'])};records=analysis.panel(p)
 panel_pin=hashlib.sha256(io.encoded(p)).hexdigest();targets=sorted(targets,key=lambda x:x['recording_id'])
 source_gold={'panel_sha256':panel_pin,'scientific_profile_sha256':profile_pin,'records':[r for r in targets if records[r['recording_id']]['cohort']=='CHB']}
 source_owner.require_original(io.encoded(p),io.encoded(reference),io.encoded(source_gold),profile_pin)
 source_owner.require_qualified('full_panel_source_join',source_qualification_sha256)
 all_gold={'panel_sha256':panel_pin,'scientific_profile_sha256':profile_pin,'records':targets}
 # The same original source owner has derived every original label. Candidate
 # code never receives this private preparation join or its target selection.
 source_owner.require_target_content(io.encoded(all_gold))
 io.need(hashlib.sha256(io.encoded(all_gold)).hexdigest()==source_owner.target_selection['sha256']and len(io.encoded(all_gold))==source_owner.target_selection['bytes'],'complete target content equals originally selected private artifact')
 return p,all_gold,source_gold,{'signals':mounts,'scientific_profile_sha256':profile_pin,'source_qualification_sha256':source_qualification_sha256,'physical_staging_done':False}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for k in ['chb-panel','siena-panel','chb-targets','siena-targets','reference','siena-preparation-profile','source-selection','source-roots','source-limits']:
  p.add_argument('--'+k,type=Path,required=True);p.add_argument('--'+k+'-sha256',required=True)
 p.add_argument('--source-qualification-sha256',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();io.need(not a.output.exists() and not a.output.is_symlink(),'fresh output beforeprivateaccess')
 from source_validation import SourceValidationOwner
 source_owner=SourceValidationOwner(io.read(a.source_selection,io.MAX_JSON,a.source_selection_sha256),io.strict(io.read(a.source_roots,1000000,a.source_roots_sha256)),io.strict(io.read(a.source_limits,1000000,a.source_limits_sha256)))
 source_owner.observe()
 raws={k:io.read(getattr(a,k),3000000,getattr(a,k+'_sha256')) for k in ['chb_panel','siena_panel','chb_targets','siena_targets','reference','siena_preparation_profile']}
 values=bind(raws['chb_panel'],raws['siena_panel'],raws['chb_targets'],raws['siena_targets'],io.strict(raws['reference']),a.source_qualification_sha256,io.strict(raws['siena_preparation_profile']),source_owner);a.output.mkdir(mode=0o700)
 for name,value in zip(['panel.json','all_targets.json','source_targets.json','SIGNAL_STAGING.json'],values):io.write(a.output/name,value)
