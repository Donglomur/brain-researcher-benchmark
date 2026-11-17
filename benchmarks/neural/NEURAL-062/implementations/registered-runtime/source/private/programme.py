"""Full source controller for NEURAL-062. No implicit download or execution permission.

Runtime requires an independently selected trusted key, exact signed source/input/
environment grant, qualified Linux host and original full cohort inputs. None is
supplied by this source package. inspect reads only installed ordinary source.
"""
from pathlib import Path
import argparse,hashlib,json
from custody import Owner
import delivery_io as io
def verify_source(root,config):
 lock=io.json_file(root.parent/'SOURCE_LOCK.json',200_000)
 io.need(lock['schema']=='neural062.source-lock.v1'and config['source']==lock['files'],'exact complete installed source set')
 wanted={r['path']for r in lock['files']}
 found=set()
 for directory in ('private','public'):
  base=root.parent/directory
  for file in base.iterdir():
   io.need(file.is_file()and not file.is_symlink(),'flat complete source modules/contracts');found.add(directory+'/'+file.name)
 io.need(found==wanted,'no omitted or extra installed runtime source')
 for r in lock['files']:io.asset(root.parent,{'path':r['path'],**r['pin']})
 return lock
def execute(config_path,config_pin,grant,key_path,key_pin,work,bootstrap_limits):
 owner=Owner(bootstrap_limits);out=None;records={};plan=None;report=None;first=None
 try:
  with io.using(owner),owner.stage('complete_programme'):
   from admission import admit
   config=admit(config_path,config_pin,grant,key_path,key_pin,owner)
   io.need(config['limits']==bootstrap_limits,'independently selected complete programme limits')
   root=Path(__file__).absolute().parent;source_root=root.parent;inputs=io.regular(Path(config_path).absolute().parent)
   verify_source(root,config)
   out=io.fresh(work);(out/'projections').mkdir();(out/'views').mkdir();(out/'jobs').mkdir();(out/'sealed_programmes').mkdir()
   # Program source is captured before the first neural input or public training view.
   scripts={}
   for mode in ('F','I'):
    r=config['programmes'][mode];target=out/'sealed_programmes'/('participant_'+mode+'.py')
    io.copy_exact(io.resolve(inputs,r['path']),target,r['pin']);scripts[('participant',mode)]=target
   for kind in ('logistic','hgb'):
    for mode in ('F','I'):scripts[(kind,mode)]=source_root/'public/reference_phase.py'
   with owner.stage('complete_original_release_admission'):
    import cohort_binding
    from cohort import validate
    cohort_path=io.resolve(inputs,config['cohort']['path']);cohort=cohort_binding.load(root,cohort_path)
    rows,assets=validate(cohort,config['assets'])
    secret=io.read(io.resolve(inputs,config['key']['path']),32,config['key']['pin'])
   with owner.stage('project_all1936_original_sources'):
    import extract,prepare
    projection_pins={}
    for exp,record in rows.items():
     owner.check();asset=assets[exp]
     with owner.stage('projection_'+exp):
      q=extract.project(io.resolve(inputs,asset['path']),record,asset['bytes']);q['method']=prepare.method(root)
      projection_pins[exp]=io.put(out/'projections'/(exp+'.json'),q,16_000_000)
    io.put(out/'PROJECTION_PINS.json',projection_pins,1_000_000)
   with owner.stage('full_private_index_and_target_generation'):
    index,plan,gold=prepare.build_index(out/'projections',projection_pins,secret,root,cohort_path)
    io.put(out/'INDEX.json',index,32_000_000);io.put(out/'PLAN.json',plan,320_000_000)
    gold_pin=io.put(out/'REFERENCE.json',gold,640_000_000);del gold
   with owner.stage('all544_case_panel_views_and3264_fit_infer_cells'):
    import protocol
    from phase_views import split_view
    from collection import OWNERS,MODES,jobs,protected_score
    from runner import cell
    expected=jobs(plan)
    for c in plan['cases']:
     for arm in protocol.ARMS:
      label=c['case']+'_'+arm
      case_root=io.fresh(out/'views'/label)
      prepare.make_view(index,out/'projections',secret,c['case'],arm,case_root/'whole',root,cohort_path)
      fit,infer=split_view(case_root/'whole/public',case_root/'fit',case_root/'infer',owner)
      # Each owner/mode sees the same presealed FIT and INFER directories.
      for who in OWNERS:
       for mode in MODES:
        coordinate=(who,mode,c['case'],arm)
        records[coordinate]=cell(config['environment'],scripts[(who,mode)],source_root/'public',fit,infer,out/'jobs'/(who+'_'+mode+'_'+label),who,mode,owner)
    io.need(set(records)==set(expected),'exact full programme coverage before protected grading')
   with owner.stage('target_last_complete_grader'):
    report=protected_score(plan,records,lambda:io.json_file(out/'REFERENCE.json',640_000_000,gold_pin),cohort,owner)
   report.update({'status':'executed_unqualified_pending_independent_evidence','task':'NEURAL-062','execution_id':config['execution_id'],'full_job_count':len(records),'phase_count':2*len(records),'cost':owner.snapshot(),'qualification':'no automatic promotion from returned source functions'})
   io.put(out/'REPORT.json',report,32_000_000)
 except BaseException as error:
  first=error;owner.retain(error,'programme')
 finally:
  # Independent report tail never replaces the original scientific/process/source failure.
  if out is not None and first is not None:
   def fail_report():
    planned=[]if plan is None else [(who,mode,c['case'],arm)for who in('participant','logistic','hgb')for mode in('F','I')for c in plan['cases']for arm in('CONTEXT','PRE','POST','PRE_POST')]
    io.put(out/'FAILURE.json',{'status':'programme_failed_no_score','task':'NEURAL-062','completed':[list(k)for k in records],'unattempted_or_incomplete':[list(k)for k in planned if k not in records],'expected_original_experiments':1936,'cost':owner.snapshot(),'primary_score':None,'exception_type':type(first).__name__},8_000_000)
   # No primary owner debit/check can suppress this independent diagnostic tail.
   owner.cleanup('independent_failure_report',fail_report)
  owner.close()
 if first is not None:raise first
 return report
def inspect():
 root=Path(__file__).absolute().parent.parent
 lock=io.json_file(root/'SOURCE_LOCK.json',200_000)
 for r in lock['files']:io.asset(root,{'path':r['path'],**r['pin']})
 return {'task':'NEURAL-062','source_members':len(lock['files']),'programme':'source only; no runtime/native/data qualification','qualified':False,'registered':False}
def main():
 a=argparse.ArgumentParser();sub=a.add_subparsers(dest='command',required=True);sub.add_parser('inspect')
 run=sub.add_parser('run')
 for key in('config','config-pin','grant','trusted-key','trusted-key-pin','work','limits'):run.add_argument('--'+key,required=True)
 q=a.parse_args()
 if q.command=='inspect':print(json.dumps(inspect()));return 0
 # Limits and pins are ordinary operator arguments; genuine key selection remains external.
 report=execute(q.config,io.decode(q.config_pin.encode()),q.grant,q.trusted_key,io.decode(q.trusted_key_pin.encode()),q.work,io.decode(q.limits.encode()))
 print(json.dumps({'status':report['status'],'qualified':False}));return 0
if __name__=='__main__':raise SystemExit(main())
