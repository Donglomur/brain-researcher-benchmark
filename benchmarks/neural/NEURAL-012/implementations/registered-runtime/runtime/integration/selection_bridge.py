"""Pure, unqualified planning bridge; never acquire inputs or publish authority.

The host supplies actual preparation metadata and each preparation's private
32-byte key in the future. Keys are used only for the existing opaque-ID formula
and are not returned. All source/reference/clock declarations remain unissued.
SourceValidationOwner must subsequently observe the original complete inputs;
genuine admission and target publication remain separate unavailable gates.
This module belongs beside, not inside or instead of, the accepted source tree.
The trusted launcher supplies the canonical neural012/private import directory.
"""
import hashlib,hmac
import io_contract as io
import analysis
import scientific_contract as sc
import source_evidence as evidence
from combine_panels import combine,source_join_binding
from protected_targets import validate_targets

def digest(raw):return hashlib.sha256(raw).hexdigest()
def clone(value):return io.strict(io.encoded(value))
def equal(left,right,message):io.need(io.encoded(left)==io.encoded(right),message)

def opaque_ids(row,key):
 """Exactly the N009 and N011 producers' existing UTF-8 HMAC formulas."""
 io.need(type(key)is bytes and len(key)==32,'actual respective preparation key must be32 bytes')
 io.need(type(row)is dict and type(row.get('path'))is str and type(row.get('patient'))is str and row['patient'],'original preparation path/patient metadata')
 return tuple(hmac.new(key,(prefix+row[field]).encode(),hashlib.sha256).hexdigest()[:24]
              for prefix,field in(('record:','path'),('patient:','patient')))

def _source_mapping(cohort,source_rows,panel_raw,key,roots):
 io.need(type(source_rows)is list and len(source_rows)==(686 if cohort=='CHB'else 41),'whole original preparation source rows')
 retained=clone(source_rows);panel=io.strict(panel_raw)
 io.fields(panel,['schema_version','task_id','records'])
 io.need(type(panel['schema_version'])is int and panel['schema_version']==1 and panel['task_id']==('NEURAL-009'if cohort=='CHB'else'NEURAL-011'),'exact prepared source task')
 io.need(type(panel['records'])is list and len(panel['records'])==len(retained),'complete corresponding prepared source panel')
 prepared={}
 for row in panel['records']:
  io.fields(row,['recording_id','patient_id','duration_seconds','observed_intervals','path','bytes','sha256'])
  rid=row['recording_id'];io.need(type(rid)is str and io.ID.fullmatch(rid)and rid not in prepared,'unique prepared opaque record')
  io.need(type(row['patient_id'])is str and io.ID.fullmatch(row['patient_id']),'prepared opaque patient')
  io.need(type(row['duration_seconds'])is int and 0<row['duration_seconds']<=86400 and row['observed_intervals']==[[0,row['duration_seconds']]],'whole prepared recording extent')
  io.need(row['path']=='signals/'+rid+'.h5'and type(row['bytes'])is int and 0<row['bytes']<10000000000,'exact prepared signal path/extent');sc.pin(row['sha256'])
  prepared[rid]=row
 seen=set();patients={};inverse={};mapping=[];assets=[];by_rid={}
 for original in retained:
  # Preserve the complete actual lock/source-map row, including extra original
  # evidence fields. No new simplified source-row schema replaces that source.
  io.need(type(original)is dict and all(k in original for k in('path','patient','bytes','sha256')),'actual existing lock/source-map row')
  path=evidence.relative(original['path']);patient=original['patient'];rid,pid=opaque_ids(original,key)
  io.need(path not in seen and rid in prepared and rid not in by_rid,'regenerated original-to-prepared inverse; never positional matching');seen.add(path)
  row=prepared[rid];io.need(row['patient_id']==pid,'same actual respective preparation key and patient identity')
  io.need(type(original['bytes'])is int and 0<original['bytes']<10000000000,'positive full original source extent');sc.pin(original['sha256'])
  if cohort=='Siena':io.need(patient==path.split('/')[0],'original Siena patient matches source directory')
  group=evidence.group(path,cohort)
  io.need((group not in patients or patients[group]==patient)and(patient not in inverse or inverse[patient]==group),'source biological grouping declaration is bijective; chb21 remains chb01')
  patients[group]=patient;inverse[patient]=group
  raw_id=evidence.asset_id('raw:'+cohort+':'+rid);prepared_id=evidence.asset_id('prepared:'+cohort+':'+rid)
  assets.extend([{'asset_id':raw_id,'root':roots[cohort],'path':path,'bytes':original['bytes'],'sha256':original['sha256'],'capture':'edf_header'},
                 {'asset_id':prepared_id,'root':roots['prepared'],'path':row['path'],'bytes':row['bytes'],'sha256':row['sha256'],'capture':'none'}])
  mapping.append({'cohort':cohort,'publisher_path':path,'source_patient':patient,'recording_id':rid,'patient_id':pid,'original_asset':raw_id,'prepared_asset':prepared_id})
  by_rid[rid]=(original,row)
 io.need(set(by_rid)==set(prepared)and len(patients)==(23 if cohort=='CHB'else 14),'whole cohort mapping without missing/extra record or person')
 return retained,mapping,assets,by_rid

def build_selection(*,chb_panel_raw,siena_panel_raw,chb_targets_raw,siena_targets_raw,
                    chb_source_rows,siena_source_rows,chb_key,siena_key,
                    reference,siena_preparation_profile,document_assets,documents,
                    whitelists,clock_records,target_path,asset_roots):
 """Return one complete unqualified plan with no filesystem or native effects.

 ``*_source_rows`` are the unchanged actual CHB lock.records and Siena
 source_map.records lists. ``asset_roots`` names future root aliases with exact
 keys CHB,Siena,prepared; it contains no filesystem paths. ``document_assets``
 are existing evidence-schema whole_metadata descriptors, and ``documents``
 uses that schema's closed document-role map. ``clock_records`` maps the41 exact
 Siena publisher paths to their complete retained source clock declarations.
 ``reference`` and ``whitelists`` must be explicitly supplied source-derived
 declarations; this planner cannot infer physical reference or adjudicate time.

 Returned selection,panel,allgold,sourcegold use the accepted schemas. Private
 mappings/full source rows are host-only explanatory products, never receipts
 or candidate payloads. Future snapshot materialization uses selection's full
 prepared asset roster and then the original SourceValidationOwner observes it.
 """
 for raw in(chb_panel_raw,siena_panel_raw,chb_targets_raw,siena_targets_raw):io.need(type(raw)is bytes,'exact original preparation bytes retained')
 io.fields(asset_roots,['CHB','Siena','prepared']);roots=clone(asset_roots)
 for root in roots.values():evidence.asset_id(root)
 io.need(len(set(roots.values()))==3,'distinct original cohort and unified prepared root aliases')
 reference=clone(reference);profile=reference['scientific_profile'];sc.validate_profile(profile);sc.validate_reference(reference)
 docs=clone(documents);whitelists=clone(whitelists);clocks=clone(clock_records)
 io.need(type(document_assets)is list and document_assets,'explicit full documentary asset roster')
 doc_assets=clone(document_assets)
 for asset in doc_assets:
  io.fields(asset,['asset_id','root','path','bytes','sha256','capture'])
  io.need(asset['capture']=='whole_metadata','only actual documentary descriptors supplied; raw/prepared IDs are derived')
 retained={};mapping=[];assets=[];originals={}
 for cohort,rows,raw,key in(('CHB',chb_source_rows,chb_panel_raw,chb_key),('Siena',siena_source_rows,siena_panel_raw,siena_key)):
  saved,joined,derived,by_rid=_source_mapping(cohort,rows,raw,key,roots)
  retained[cohort]=saved;mapping.extend(joined);assets.extend(derived)
  io.need(not(set(originals)&set(by_rid)),'no cross-cohort opaque record collision');originals.update(by_rid)
 refs={r['recording_id']:r for r in reference['records']}
 io.need(set(refs)==set(originals)and len(refs)==727,'all727 explicit physical reference declarations')
 io.need(type(clocks)is dict and set(clocks)=={m['publisher_path']for m in mapping if m['cohort']=='Siena'},'complete exact41 source clock inverse')
 # Same original source-panel/target join as accepted combine_panels; no gated
 # bind call here, because the genuinely observed owner does not yet exist.
 rows,targets,mounts=combine(chb_panel_raw,siena_panel_raw,chb_targets_raw,siena_targets_raw)
 target_by_id={t['recording_id']:t['events']for t in targets};records=[]
 for mapped in sorted(mapping,key=lambda m:m['recording_id']):
  rid=mapped['recording_id'];original,prepared=originals[rid];ref=refs[rid]
  io.need(ref['cohort']==mapped['cohort']and ref['duration_seconds']==prepared['duration_seconds']and ref['signal_sha256']==prepared['sha256'],'exact original reference/prepared cohort,extent and signal binding')
  subject=mapped['publisher_path'].split('/')[0]
  if mapped['cohort']=='CHB':summary=docs['chb_summaries'].get(subject);clock=None
  else:
   summary=docs['siena_summaries'][subject];clock=sc.validate_clock_record(clocks[mapped['publisher_path']])
   io.need(all(k in original for k in('header','header_sha256','release_whitelist')),'actual full Siena source-map header and whitelist metadata')
   header=original['header'];sc.pin(original['header_sha256'])
   io.need(clock['path']==original['path']and clock['source_sha256']==original['sha256']and clock['header_sha256']==original['header_sha256']and clock['header_clock']==header['registration_clock']and clock['duration_seconds']==header['duration_seconds']==prepared['duration_seconds'],'same retained original Siena source/header/clock/extent')
   equal(original['release_whitelist'],whitelists[subject],'same complete original Siena release whitelist')
   io.need(clock['annotation_sha256']==whitelists[subject]['summary_sha256'],'clock binds original summary')
   selected=header['selected_channels']
   io.need(header['sample_rate_hz']==ref['sample_rate_hz']and [c['label']for c in selected]==ref['channel_labels']and [c['source_index']for c in selected]==ref['source_channel_indices'],'actual Siena source-map channel declaration equals reference')
   equal([c['scale_to_microvolts']for c in selected],ref['calibration']['scale_to_microvolts'],'same Siena header scale')
   equal([c['offset_microvolts']for c in selected],ref['calibration']['offset_microvolts'],'same Siena header offset')
   selected_events=clock['source_events']if profile['label_profile']=='C1_source_parser'else clock['C2_candidate']['events']
   io.need(type(selected_events)is list,'complete selected clock candidate; no clipping/partial-support substitution')
   equal(target_by_id[rid],selected_events,'prepared Siena target values exactly match selected clock profile; still unqualified')
  records.append({'recording_id':rid,'publisher_path':mapped['publisher_path'],'original_asset':mapped['original_asset'],'prepared_asset':mapped['prepared_asset'],'summary_asset':summary,'clock_record':clock})
 for row in rows:row['montage_sha256']=refs[row['recording_id']]['montage_sha256']
 sc.validate_reference(reference,rows)
 s=clone(siena_preparation_profile)
 io.fields(s,['schema','scientific_profile','panel_sha256','targets_sha256','clock_records_sha256','release_whitelists_sha256','source_qualification_sha256','authority_status'])
 io.need(s['schema']=='siena_preparation_profile_v1'and s['authority_status']=='unissued','original unissued Siena preparation profile')
 equal(s['scientific_profile'],profile,'one explicit original scientific profile')
 io.need(s['panel_sha256']==digest(siena_panel_raw)and s['targets_sha256']==digest(siena_targets_raw),'exact original Siena preparation bytes')
 for key in('clock_records_sha256','release_whitelists_sha256','source_qualification_sha256'):sc.pin(s[key])
 # Siena prepare.build hashes clock records in original source-map order.
 ordered_clocks=[clocks[r['path']]for r in retained['Siena']]
 io.need(s['clock_records_sha256']==sc.digest(ordered_clocks),'same original Siena preparation clock order and full contents')
 whitelist_pin=sc.digest({'schema':'siena_release_EEG_whitelists_v1','subjects':[whitelists[p]for p in sorted(whitelists)]})
 io.need(s['release_whitelists_sha256']==whitelist_pin,'same whole-release whitelist preparation identity')
 request=source_join_binding(chb_panel_raw,siena_panel_raw,chb_targets_raw,siena_targets_raw,reference,s)
 panel={'schema_version':2,'task_id':io.TASK,'scientific_profile':profile,'source_qualification_sha256':request,'records':sorted(rows,key=lambda r:r['recording_id'])}
 admitted=analysis.panel(panel);panel_raw=io.encoded(panel);profile_pin=sc.profile_sha256(profile)
 targets=sorted(targets,key=lambda r:r['recording_id'])
 allgold={'panel_sha256':digest(panel_raw),'scientific_profile_sha256':profile_pin,'records':targets}
 sourcegold={'panel_sha256':digest(panel_raw),'scientific_profile_sha256':profile_pin,'records':[t for t in targets if admitted[t['recording_id']]['cohort']=='CHB']}
 allgold_raw=io.encoded(allgold);sourcegold_raw=io.encoded(sourcegold)
 target_selection={'path':target_path,'bytes':len(allgold_raw),'sha256':digest(allgold_raw),'panel_sha256':digest(panel_raw),'scientific_profile_sha256':profile_pin,'source_targets_sha256':digest(sourcegold_raw)}
 selection={'schema':evidence.SCHEMA,'panel':panel,'reference':reference,'source_targets':sourcegold,'target_selection':target_selection,'records':records,'assets':sorted(assets+doc_assets,key=lambda a:a['asset_id']),'documents':docs,'whitelists':whitelists}
 evidence.validate_selection(selection)
 evidence.validate_consumer_binding(selection,panel_raw,io.encoded(reference),sourcegold_raw,profile_pin)
 validate_targets(allgold_raw,panel_raw,sourcegold_raw,target_selection)
 return {'schema':'neural012_unqualified_selection_plan_v1','selection':selection,'panel':panel,'allgold':allgold,'sourcegold':sourcegold,
         'private_mapping':sorted(mapping,key=lambda m:m['recording_id']),'private_source_rows':retained,
         'signal_staging':{'signals':mounts,'scientific_profile_sha256':profile_pin,'source_qualification_sha256':request,'physical_staging_done':False},
         'unresolved':list(evidence.HOLDS),'authority_status':'unissued','authentic_inputs_observed':False,'physical_staging_done':False,'genuine_source_qualified':False}
