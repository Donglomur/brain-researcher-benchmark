"""Future isolated reference worker. Not run during source construction."""
import argparse
from pathlib import Path
from .io import read_json,write_json,need
from .contract import require_deployment
from .views import read_training_view

def main():
    require_deployment()
    parser=argparse.ArgumentParser()
    parser.add_argument("--request",required=True);parser.add_argument("--output-dir",required=True)
    args=parser.parse_args();out=Path(args.output_dir)
    request=read_json(args.request,16_000_000)
    need(request["operation"]=="reference_train","Reference-only entry")
    train=read_json(request["input_capabilities"]["training_view"]["path"],1_000_000,request["input_capabilities"]["training_view"])
    rows,inner=read_training_view(Path(request["input_capabilities"]["training_view"]["path"]).parent,train)
    query=read_json(request["input_capabilities"]["query_views"]["path"],16_000_000,request["input_capabilities"]["query_views"])
    from .references import complete_reference_bank
    result=complete_reference_bank(request["reference_recipe"]["reference"],rows,inner,query,out/"reference_fit_journal")
    result["contract"]=request["contract"]
    write_json(out/"REFERENCE_BANK.json",result,64_000_000)
    write_json(out/"PRODUCTS.json",{"schema":"n097-worker-products-v1","status":"complete",
               "products":{"reference_bank":{"path":"REFERENCE_BANK.json"}},"failure_reasons":[]})
    return 0

if __name__=="__main__":raise SystemExit(main())
