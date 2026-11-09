"""Build-safe inspection; authentic operations require explicit external root admission."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).absolute().parent))
from program.common import need,decode,canonical,Ledger,read_json
from program.deployment import inspect
def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest="command",required=True)
    sub.add_parser("inspect")
    for name in ("operate","prepare","launch"):
        op=sub.add_parser(name);op.add_argument("--request",type=Path,required=True);op.add_argument("--request-bytes",type=int,required=True);op.add_argument("--request-sha256",required=True)
    a=p.parse_args()
    if a.command=="inspect":
        d=decode((Path(__file__).parent/"DEPLOYMENT.json").read_bytes())
        print(json.dumps(inspect(d),sort_keys=True));return
    # Reading a selected root request is not permission to bypass unconfigured deployment.
    from program.runner import operate
    cap={"wall_seconds":60,"read_bytes":1048576,"write_bytes":1048576,"provider_requests":1,"input_tokens":1,"output_tokens":1}
    req=read_json(a.request.absolute(),{"bytes":a.request_bytes,"sha256":a.request_sha256},Ledger(cap),"root operation request")
    if a.command=="operate":result=operate(req)
    elif a.command=="prepare":
        from program.preparation import prepare
        manifest,accounting=prepare(req)
        result={"status":"prepared","manifest":manifest,"accounting":accounting,"scientific_qualification":False}
    else:
        from program.outer import launch
        result=launch(req)
        print(json.dumps(result,sort_keys=True))
        raise SystemExit(result["status"]!="complete")
    print(json.dumps(result,sort_keys=True))
if __name__=="__main__":main()

