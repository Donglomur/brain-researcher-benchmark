"""Canonical/default/named and standalone CLI use one complete stage route."""
import argparse,json,sys
from .source import inspect_source
from .execute import execute

def main(argv=None,forced_action=None):
    parser=argparse.ArgumentParser(description="Complete NEURAL-063 stage programme; source inspection grants no execution")
    if forced_action:
        parser.add_argument("--submission",required=True);action=forced_action
    else:
        parser.add_argument("action",choices=["inspect","run","prepare","reference","candidate","collect","grade","report"])
        parser.add_argument("--program")
    for name in ("output","review","deployment","deployment-sha256"):parser.add_argument("--"+name)
    parser.add_argument("--other-reserve-bytes",type=int)
    args=parser.parse_args(argv)
    try:
        action=forced_action or args.action
        if action=="inspect":
            if any(getattr(args,x) is not None for x in ("program","output","review","deployment","deployment_sha256","other_reserve_bytes")):
                raise ValueError("inspection takes no operational input paths")
            result=inspect_source()
        else:
            operand=args.submission if forced_action else args.program
            if not operand or any(getattr(args,x) is None for x in ("output","review","deployment","deployment_sha256","other_reserve_bytes")):
                raise ValueError("explicit complete method, review, deployment, output and extra reserve required")
            result=execute(action,operand,args.output,args.review,args.deployment,args.deployment_sha256,args.other_reserve_bytes)
        print(json.dumps(result,sort_keys=True,allow_nan=False))
        return 0 if action=="inspect" or (result.get("status")=="delivered" and result.get("result",{}).get("receipt_kind")=="completion" and result["result"].get("outcome") not in {"failed","publication_unresolved"}) else 1
    except Exception as exc:
        print(json.dumps({"schema":"neural063_central_refusal_v1","exception_type":type(exc).__name__,
            "reason":str(exc)[:2048],"scientific_completion_claim":False}),file=sys.stderr)
        return 2
