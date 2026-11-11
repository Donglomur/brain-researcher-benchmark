"""Source-only public entry. Scientific deployment has not been qualified."""
import argparse
import json
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description="Complete Jaxley paper scope; source/engineering status")
    parser.add_argument("command",choices=("status","run"),nargs="?",default="status")
    args=parser.parse_args()
    here=Path(__file__).resolve().parent
    graph=json.loads((here/"SOURCE_PRODUCER_GRAPH.json").read_text())
    gaps=json.loads((here/"SOFTWARE_GAPS.json").read_text())
    status={"task_id":"PAPER-paper-method-002","required_groups":len(graph["nodes"]),
            "conditions":["A_R","B_R","A_I","B_I"],"mathematical_endpoints_per_bank":19,
            "native_producer_role_gaps":len(graph["software_gaps"]),"runtime_gaps":gaps["runtime_gaps"],
            "complete_native_software":False,"scientifically_qualified":False,"new_benchmark_ids":0,
            "common_Jaxley_interpretation":"library-assisted experiment reconstruction"}
    if args.command=="run":
        status["requested_action"]="refused"
        status["reason"]="Build-only source package: complete native producers, original scientific versions, full GPU/multi-host adapter and external qualification are absent."
    print(json.dumps(status,indent=2,sort_keys=True))
    return 2 if args.command=="run" else 0

if __name__=="__main__":raise SystemExit(main())
