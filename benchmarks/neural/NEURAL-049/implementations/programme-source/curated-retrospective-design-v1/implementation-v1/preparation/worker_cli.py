"""Concrete private worker CLI. Owner authenticates this package before starting Python."""
import argparse
import json
from pathlib import Path
from . import contracts as c
from .budget import Budget
from .storage import IO,OperationFailure,failure_record,root
from .prepare import prepare_run
from .views import materialize_view


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--request',required=True)
    parser.add_argument('--request-bytes',type=int,required=True)
    parser.add_argument('--request-sha256',required=True)
    parser.add_argument('--inherited-context',required=True)
    args=parser.parse_args(argv)
    budget=None
    try:
        c.need(len(args.inherited_context)<=16384,'bounded original context argument')
        context=c.parse_json(args.inherited_context)
        budget=Budget(context);store=IO(budget)
        p=Path(args.request);base=root(str(p.parent))
        request=store.json(base,{'path':p.name,'pin':{'bytes':args.request_bytes,'sha256':args.request_sha256}})
        c.need(type(request) is dict and request.get('schema')=='neural049_preparation_worker_request_v1','selected worker request')
        # Request capture has already spent the SAME instance; the API must not reset it.
        operation=request.get('operation')
        if operation=='prepare':
            c.need(set(request)=={'schema','operation','authority_path','authority_pin'},'prepare request fields')
            result=prepare_run(request['authority_path'],request['authority_pin'],budget)
        elif operation=='view':
            c.need(set(request)=={'schema','operation','packet','selection','output_root'},'view request fields')
            result=materialize_view(request['packet'],request['selection'],request['output_root'],budget)
        else:raise c.Refused('unknown or unselected preparation operation')
        budget.tick()
        print(c.canonical({'schema':'neural049_preparation_worker_result_v1','status':'returned',
                           'result':result,'costs':budget.record()}).decode('ascii'))
        return 0
    except BaseException as exc:
        record=exc.record if isinstance(exc,OperationFailure) else failure_record(exc,budget,'worker_entry')
        print(c.canonical({'schema':'neural049_preparation_worker_result_v1','status':'failed','record':record}).decode('ascii'))
        return 1

if __name__=='__main__':
    raise SystemExit(main())
