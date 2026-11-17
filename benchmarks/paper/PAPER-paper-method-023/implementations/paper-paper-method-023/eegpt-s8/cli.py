"""Portable source-owned full programme interface; no standalone partial stage."""
import argparse,hashlib,os,sys,time,stat
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from eegpt.protocol import Directory,fields,need,decode,encode,identity,observation,Refusal
from eegpt.scope import Scope,CONTRACT_NAMES
PACKAGE=Path(__file__).resolve().parent
RETURN_DEADLINE=None


def ordinary_json(path,expected=None,*,budget=None,with_pin=False):
    from eegpt.protocol import guard,pin,_close,account
    path=Path(path);need(path.is_absolute() and str(path)==str(path.absolute()) and '..' not in path.parts,'canonical absolute selected source path');root=None;fd=None;parts=[];failure=None;value=None;member=None
    try:
        guard(budget,'before_selected_metadata_root');root=Directory(str(path.parent));fd=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=root.fd);st=os.fstat(fd);need(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_size<=16777216,'bounded ordinary selected metadata')
        if budget is not None:budget.reserve('read_bytes',st.st_size+1)
        left=st.st_size+1
        while left:
            guard(budget,'before_selected_metadata_chunk');chunk=os.read(fd,min(left,65536));parts.append(chunk);left-=len(chunk);guard(budget,'after_selected_metadata_chunk')
            if not chunk:break
        raw=b''.join(parts);need(len(raw)==st.st_size,'complete original metadata');after=os.fstat(fd);named=os.stat(path.name,dir_fd=root.fd,follow_symlinks=False)
        need((st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)==(named.st_dev,named.st_ino,named.st_size,named.st_mtime_ns),'same selected original metadata through read')
        if expected is not None:need(hashlib.sha256(raw).hexdigest()==expected,'exact independently selected metadata bytes')
        root.verify();guard(budget,'after_selected_metadata_read');value=decode(raw);member={'path':path.name,**pin(raw)}
    except BaseException as exc:failure=exc
    finally:
        closes=_close((fd,))
        if root is not None:
            try:root.close()
            except BaseException as exc:closes.append(observation(exc))
        if budget is not None:account(budget,'read_bytes',sum(map(len,parts)),closes)
        try:guard(budget,'after_selected_metadata_close')
        except BaseException as exc:
            if failure is None:failure=exc
            else:closes.append(observation(exc))
    if failure is not None or closes:raise Refusal('original selected metadata admission failed',observation={'primary':None if failure is None else observation(failure),'secondary_failures':closes,'known_read_prefix':pin(b''.join(parts))}) from failure
    return (value,member) if with_pin else value


def scope():return Scope({name:ordinary_json(PACKAGE/'contracts'/(name+'.json')) for name in CONTRACT_NAMES})


def deployment(path,pin,*,origin,public_args):
    from eegpt.budget import Budget
    from eegpt.completion import public_invocation_binding
    mode='default' if path is None else 'named'
    if path is None:
        need(pin is None,'no detached hash on default invocation');path=PACKAGE/'DEPLOYMENT.json'
    else:need(pin is not None,'external deployment requires independent exact pin')
    d,member=ordinary_json(path,pin,with_pin=True);fields(d,('schema','configuration_path','configuration_sha256','outer','root_selection','asset_preparation'),'full selected deployment');need(d['schema']=='eegpt_complete_deployment_v1','full source operation deployment')
    need(d['configuration_path'] is not None and d['configuration_sha256'] is not None and d['outer'] is not None and d['root_selection'] is not None,'Deployment unconfigured: actual independent source, data, native, physical-isolation and scientific qualification must be selected before execution')
    window=Budget(d['outer']['limits'],origin=origin,label='original public invocation admission');window.reserve('read_bytes',member['bytes']+1);window.observe('read_bytes',member['bytes']);window.guard('after_bounded_deployment_before_configuration')
    c=ordinary_json(d['configuration_path'],d['configuration_sha256'],budget=window)
    need(d['root_selection']==c['qualification']['selection_identity'] and identity(c)==d['configuration_sha256'],'same selected root authority and canonical exact configuration bytes before launch')
    # Deployment admission is bounded metadata; all later work uses the same
    # original monotonic origin, including the inclusive outer and child.
    binding=None
    if public_args[0]=='run':
        prefix=[str(Path(d['outer']['python_root'])/d['outer']['python']['path']),'-I','-B',str(PACKAGE/'cli.py')]
        expected_args=['run'] if mode=='default' else ['run','--deployment',str(path),'--deployment-sha256',member['sha256']]
        need(public_args==expected_args,'literal default or named argv only; no ignored extra flags')
        binding=public_invocation_binding(PACKAGE,d['outer'],c,mode=mode,deployment={'root':str(Path(path).parent),'member':member},argv=prefix+public_args,cwd=os.getcwd(),origin_ns=origin)
    window.guard('after_public_invocation_selection');return d,c,window,binding


def main(argv=None):
    global RETURN_DEADLINE
    RETURN_DEADLINE=None
    origin=time.monotonic_ns();public_args=list(sys.argv[1:] if argv is None else argv)
    parser=argparse.ArgumentParser(description='One complete EEGPT research programme; 200-project catalogue counts are not output-cell counts.');parser.add_argument('operation',choices=('inspect','prepare','run','inspect-report','adjudicate-report'));parser.add_argument('--deployment');parser.add_argument('--deployment-sha256');parser.add_argument('--report');parser.add_argument('--report-sha256');parser.add_argument('--review-selection');parser.add_argument('--review-selection-sha256');args=parser.parse_args(argv)
    if args.operation=='inspect':return {'status':'source_only','canonical_id':'PAPER-paper-method-023','scope':scope().summary(),'full_operation':'run','preparation':'prepare','internal_mandatory_stages':['reference','participant','collection','protected_scoring','report'],'independently_resumable_partial_stages':False,'qualified_scientific_runs':0}
    if args.operation!='inspect':raise Refusal('Public inspection-source interface admits inspect only; no report/intake/execution authority is included.')
    if args.operation=='inspect-report':
        need(args.report and args.report_sha256,'independently selected closed report descriptor');report=ordinary_json(args.report,args.report_sha256);need(report['schema']=='eegpt_complete_scientific_report_v1' and report['numerical_scoring_closed'],'original closed whole report');return {'report_identity':identity(report),'scope':report['scope'],'scientifically_complete':report['scientifically_complete'],'qualification':report['scientific_qualification'],'interpretations':report['interpretations']}
    if args.operation=='adjudicate-report':
        need(args.review_selection and args.review_selection_sha256,'exact independently selected closed-review packet authority');selection=ordinary_json(args.review_selection,args.review_selection_sha256)
        from eegpt.review import reduce_closed_review
        result=reduce_closed_review(selection);RETURN_DEADLINE=result['final_budget']['deadline_ns'];return result
    raise Refusal('Public inspection-source copy has no qualified execution authority, complete external source or authentic intake; prepare/run are unavailable.')
    d,c,window,binding=deployment(args.deployment,args.deployment_sha256,origin=origin,public_args=public_args);RETURN_DEADLINE=window.deadline
    if argv is None and args.operation=='run':need(sys.orig_argv==binding['argv'],'actual interpreter and script command exactly selected before launch')
    from eegpt.outer import operate
    if args.operation=='prepare':
        selected=d['asset_preparation'];need(selected is not None,'Complete raw asset preparation is unconfigured; inspect is the source-only inventory operation');fields(selected,('configuration_path','configuration_sha256','outer'),'complete original raw asset preparation selection');assets=ordinary_json(selected['configuration_path'],selected['configuration_sha256'],budget=window);result=operate(PACKAGE,assets,selected['outer'],operation='prepare_assets',origin=origin);window.guard('after_full_preparation_before_return');return result
    result=operate(PACKAGE,c,d['outer'],origin=origin,public_invocation=binding,admission_budget=window);window.guard('after_whole_public_operation_before_return');return result
def publish_return(result):
    if RETURN_DEADLINE is not None:need(time.monotonic_ns()<=RETURN_DEADLINE,'original deadline before public CLI return publication')
    raw=encode(result);sys.stdout.buffer.write(raw);sys.stdout.buffer.flush()
    if RETURN_DEADLINE is not None:need(time.monotonic_ns()<=RETURN_DEADLINE,'original deadline after public CLI return publication')


if __name__=='__main__':
    try:publish_return(main());raise SystemExit(0)
    except Exception as exc:sys.stderr.buffer.write(encode({'status':'refused_or_failed','original_failure':observation(exc),'scientific_qualification_claim':False}));raise SystemExit(2)
