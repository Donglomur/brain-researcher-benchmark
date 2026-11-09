"""Portable NEURAL-073 inspection and selected complete-run command line."""
import sys
sys.dont_write_bytecode = True

# Direct central argv and standalone relocation use the same actual package.
# No environment variables, private worktree history or configured global path.
if __package__ in (None, ''):
    import hashlib
    import importlib.util
    import os
    from pathlib import Path
    _root=Path(os.path.abspath(__file__)).parent
    _name='_n073_full_'+hashlib.sha256(str(_root).encode()).hexdigest()[:16]
    _spec=importlib.util.spec_from_file_location(_name,_root/'__init__.py',
                                               submodule_search_locations=[str(_root)])
    _module=importlib.util.module_from_spec(_spec)
    sys.modules[_name]=_module
    _spec.loader.exec_module(_module)
    __package__=_name

import argparse
import json
import os
from pathlib import Path
from .declaration import load_package,DeclarationError,read_json_pinned,ReadLedger

SOURCE_INSPECTION_CAP=64*1024*1024


def inspect_instance(task_root,deployment_path,expected_deployment_sha256):
    """Only exact source/deployment metadata; no L, key, array or native reads."""
    package=load_package(task_root,read_cap=SOURCE_INSPECTION_CAP)
    actual=package['pins']['D']
    path=Path(deployment_path)
    if not path.is_absolute():path=Path(os.path.abspath(path))
    if path!=package['root']/'DEPLOYMENT.json' or actual['sha256']!=expected_deployment_sha256:
        raise DeclarationError('inspection must name the exact frozen deployment')
    return {'schema':'n073_source_inspection_v1','task_id':'NEURAL-073',
        'scope':package['T']['scope'],'status':'source_only_unqualified',
        'deployment_status':package['D']['status'],
        'source_identities':package['pins'],'source_read_bytes':package['read_bytes'],
        'scientific_run':False,'native_qualification':False,'runnable_claim':False,
        'external_sections_read':False}


def main(argv=None):
    parser=argparse.ArgumentParser(description='Complete source-bound NEURAL-073 programme')
    sub=parser.add_subparsers(dest='command',required=True)
    inspect=sub.add_parser('inspect',help='Verify source only without operational inputs')
    run=sub.add_parser('run',help='Execute one independently qualified original invocation')
    for p in (inspect,run):
        p.add_argument('--deployment',required=True)
        p.add_argument('--deployment-sha256',required=True)
    run.add_argument('--program',required=True,help='Closed fixed model/inference policy JSON')
    run.add_argument('--output',required=True,help='Exact signed grading-submission JSON destination')
    run.add_argument('--review',required=True,help='Independent root-signed execution selection')
    run.add_argument('--other-reserve-bytes',required=True,type=int)
    args=parser.parse_args(argv)
    root=Path(os.path.abspath(__file__)).parent
    try:
        if args.command=='inspect':
            result=inspect_instance(root,args.deployment,args.deployment_sha256)
        else:
            from .orchestrator import run_instance
            result=run_instance(root,args.deployment,args.deployment_sha256,args.program,
                args.output,args.review,other_reserve_bytes=args.other_reserve_bytes)
        print(json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False))
        return 0
    except Exception as exc:
        # A consumed attempt survives preparation failures before the scientific
        # store exists. Public stderr carries only bounded pointers/counters and
        # capture-error types; private original receipts never appear here.
        from .attempts import InvocationFailed
        attempt_diagnostic=exc.public_diagnostic if type(exc) is InvocationFailed else None
        print(json.dumps({'schema':'n073_command_failure_v1','status':'refused_or_failed',
            'exception_type':type(exc).__name__,'qualified':False,
            'attempt_diagnostic':attempt_diagnostic,
            'scientific_completion_claim':False},sort_keys=True),file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
