"""Finite stdlib regression for the actual N006 CI deadline-evidence checker.
No Docker, provider, model, task, scientific calls or subprocesses.
"""
import ast
import hashlib
import json
import math
from pathlib import Path
import sys

CI_BYTES = 18605
CI_SHA = 'ec1c45d98c57d3b9ddd79469c2be745d08ca704d3b485af43c8d569023c61c06'


def check(ok,reason):
    if not ok:raise AssertionError(reason)


def main():
    check(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode and not sys.flags.optimize,
          'isolated unoptimized stdlib invocation')
    path=Path(__file__).absolute().with_name('ci_source.py')
    check(not any(p.is_symlink() for p in (path,*path.parents)),'ordinary source ancestry')
    with path.open('rb') as f:raw=f.read(CI_BYTES+1)
    check(len(raw)==CI_BYTES and hashlib.sha256(raw).hexdigest()==CI_SHA,'exact reviewed actual CI helper')
    tree=ast.parse(raw,filename=str(path))
    functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    admit=functions['admit']
    calls=[n for n in ast.walk(admit) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
           and n.func.id=='require_original_deadline']
    check(len(calls)==1 and not calls[0].keywords,'exact actual admission checker call')
    expected=ast.parse("require_original_deadline(result['original_start'],result['original_end'])").body[0].value
    check(ast.dump(calls[0],include_attributes=False)==ast.dump(expected,include_attributes=False),'actual result operand join')
    # Load the captured reviewed source with a non-main name; no operation is selected.
    ns={'__name__':'n006_deadline_regression_subject','__file__':str(path)}
    exec(compile(raw,str(path),'exec',dont_inherit=True),ns)
    actual=ns['require_original_deadline'];rows=[]
    def case(name,start,end,accepted):
        error=None
        try:actual(start,end)
        except ValueError as e:error=type(e).__name__
        check((error is None)==accepted,name)
        rows.append({'name':name,'accepted':accepted,'status':'PASS'})
    start=51.01518696;end=111.01518696
    check(end-start==59.99999999999999 and end-start!=60 and end==start+60,'exact original floating subtraction failure')
    case('original_timestamp_pair',start,end,True)
    case('zero_origin',0.0,60.0,True)
    case('ordinary_positive_origin',10.5,70.5,True)
    case('adjacent_endpoint_below',start,math.nextafter(end,-math.inf),False)
    case('adjacent_endpoint_above',start,math.nextafter(end,math.inf),False)
    case('shortened_endpoint',start,end-1.0,False)
    case('extended_endpoint',start,end+1.0,False)
    case('equal_endpoint',start,start,False)
    case('reversed_endpoint',end,start,False)
    case('negative_start',-1.0,59.0,False)
    case('rounded_away_interval',1e308,1e308,False)
    invalid=[('bool',True),('int',1),('string','1.0'),('none',None),('list',[]),
             ('nan',math.nan),('positive_infinity',math.inf),('negative_infinity',-math.inf)]
    for name,value in invalid:
        case('invalid_start_'+name,value,61.0,False)
        case('invalid_end_'+name,1.0,value,False)
    check(len(rows)==27 and len({r['name'] for r in rows})==27,'exact27 finite regression cases')
    print(json.dumps({'schema':'n006-original-deadline-regression-v1','status':'PASS','cases':rows,
        'case_count':len(rows),'actual_admission_call_verified':True,'actual_checker_source':{'bytes':CI_BYTES,'sha256':CI_SHA},
        'original_pair':{'start':start,'end':end,'inverse_subtraction':end-start},
        'owner_or_control_execution':False,'Docker_calls':0,'subprocesses':0,'network_provider_model_science_calls':0},sort_keys=True))
    return 0


if __name__=='__main__':raise SystemExit(main())
