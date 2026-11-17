"""Original target-owner analysis composition; no provider/receipt issues authority."""
import hashlib
import io_contract as io
import analysis
from protocol_policy import protocol_sources,validate_comparison
from scientific_contract import profile_sha256
from phase_provenance import validate_evidence
from protected_targets import ProtectedTargetOwner,acquire_target_owner,validate_targets

SEAL_FIELDS=('schema_version','task_id','panel_sha256','streams_sha256','protocol_sha256','program_sha256','training_rule','targets_sha256','source_targets_sha256','scientific_profile_sha256','source_qualification_sha256','execution_evidence_sha256','target_selection_sha256')
TRAINING_RULE='CHB_LOPO_source_audit_and_full_CHB_target_fit_no_Siena_labels'
def digest(raw):return hashlib.sha256(raw).hexdigest()

def original_execution_evidence(execution,panel_raw,stream_raw):
 from campaign_owner import CampaignOwner
 io.need(type(execution)is CampaignOwner,'original live CampaignOwner required, never a receipt')
 p=io.strict(panel_raw);analysis.panel(p);io.need(panel_raw==io.encoded(p),'exact canonical full panel')
 execution.source_owner.require_original(panel_raw,execution.reference_raw,execution.source_targets_raw,profile_sha256(p['scientific_profile']))
 execution.source_owner.require_target_selection(execution.target_selection)
 evidence=execution.analysis_evidence(panel_raw,stream_raw)
 validate_evidence(evidence,digest(panel_raw),profile_sha256(p['scientific_profile']));return evidence

def build_seal(owner,evidence):
 io.need(type(owner)is ProtectedTargetOwner and owner.execution.target_owner is owner,'same acquired original target attempt')
 p=owner.require_original();e=owner.execution
 io.need(evidence is owner.evidence,'same original full execution evidence')
 checked=original_execution_evidence(e,owner.panel_raw,owner.stream_raw)
 io.need(io.encoded(checked)==io.encoded(evidence),'same complete original execution observation')
 # protocol_sources reads at most eight ordinary bodies, each capped100000;
 # reserve its full possible bytes including each overflow witness before reads.
 e.budget.reserve_postprediction_read(8*100001);_,protocol_pin,_=protocol_sources();e.budget.check()
 validate_comparison(evidence['comparison']);io.need(evidence['comparison']['protocol_sha256']==protocol_pin,'same current frozen reference protocol')
 seal={'schema_version':3,'task_id':io.TASK,'panel_sha256':digest(owner.panel_raw),'streams_sha256':{a:digest(b)for a,b in owner.stream_raw.items()},'protocol_sha256':protocol_pin,'program_sha256':evidence['programme_sha256'],'training_rule':TRAINING_RULE,'targets_sha256':owner.selection['sha256'],'source_targets_sha256':digest(e.source_targets_raw),'scientific_profile_sha256':profile_sha256(p['scientific_profile']),'source_qualification_sha256':p['source_qualification_sha256'],'execution_evidence_sha256':digest(io.encoded(evidence)),'target_selection_sha256':digest(owner.selection_raw)}
 io.fields(seal,SEAL_FIELDS);return io.encoded(seal)

def prepare(owner):
 """Consume exactly this original closed target release once; no target callback."""
 io.need(type(owner)is ProtectedTargetOwner,'original protected target owner required')
 e=owner.execution;p=owner.require_original();e.budget.check()
 io.need(owner.capture_complete and owner.first_error is None,'complete closed target capture before analysis')
 panel_raw,stream_raw,seal_raw=owner.panel_raw,owner.stream_raw,owner.seal_raw
 records=analysis.panel(p);profile_pin=profile_sha256(p['scientific_profile'])
 seal=io.strict(seal_raw);io.fields(seal,SEAL_FIELDS)
 io.need(type(seal['schema_version'])is int and seal['schema_version']==3 and seal['task_id']==io.TASK and seal['panel_sha256']==digest(panel_raw),'exact source-owned prediction seal')
 io.need(seal['training_rule']==TRAINING_RULE and seal['scientific_profile_sha256']==profile_pin and seal['source_qualification_sha256']==p['source_qualification_sha256'],'same selected training/profile/source bindings')
 io.need(seal['target_selection_sha256']==digest(owner.selection_raw)and seal['targets_sha256']==owner.selection['sha256']and seal['source_targets_sha256']==digest(e.source_targets_raw),'same original target selection and source targets')
 io.fields(stream_raw,analysis.ARMS);io.fields(seal['streams_sha256'],analysis.ARMS);io.fields(seal['program_sha256'],analysis.ARMS)
 admitted={}
 for arm in analysis.ARMS:
  io.need(digest(stream_raw[arm])==seal['streams_sha256'][arm],'same sealed complete stream')
  value=io.strict(stream_raw[arm]);io.need(value['arm']==arm,'exact named arm');admitted[arm]=analysis.admit_stream(value,records)
 evidence=original_execution_evidence(e,panel_raw,stream_raw)
 io.need(digest(io.encoded(evidence))==seal['execution_evidence_sha256']and evidence['programme_sha256']==seal['program_sha256']and evidence['source_targets_sha256']==seal['source_targets_sha256'],'same live full campaign lineage')
 validate_comparison(evidence['comparison']);io.need(evidence['comparison']['protocol_sha256']==seal['protocol_sha256'],'same actual programme classification')
 for arm in analysis.ARMS:
  io.need(evidence['stream_pins'][arm]=={'bytes':len(stream_raw[arm]),'sha256':seal['streams_sha256'][arm]},'original stream extent and hash')
 gold_raw=owner.release_for_analysis();gold=validate_targets(gold_raw,panel_raw,e.source_targets_raw,owner.selection)
 targets={r['recording_id']:r['events']for r in gold['records']}
 packet={'schema_version':2,'task_id':io.TASK,'seal_sha256':digest(seal_raw),'scientific_profile':p['scientific_profile'],'source_qualification_sha256':p['source_qualification_sha256'],'execution_evidence':evidence,'records':[dict(row,annotations=targets[rid],arms={a:admitted[a][rid]for a in analysis.ARMS})for rid,row in sorted(records.items())]}
 analysis.validate_packet(packet);e.budget.check();return packet

def prepare_completed_campaign(execution):
 """Actual CLI calls once on its original owner; failed attempts remain retained."""
 from campaign_owner import CampaignOwner
 io.need(type(execution)is CampaignOwner,'same canonical original campaign')
 owner=acquire_target_owner(execution)
 try:
  owner.capture();packet=prepare(owner);owner.publish_analysis(packet)
 except BaseException as error:
  owner.retain(error);execution.analysis_complete=False
  if execution.analysis_first_error is None:execution.analysis_first_error=owner.first_error
  elif error is not execution.analysis_first_error:execution.analysis_secondary_errors.append(error)
  raise owner.first_error
 return packet

if __name__=='__main__':
 raise SystemExit('Use the original source-validation/campaign pipeline; receipts and callbacks cannot create protected target authority.')
