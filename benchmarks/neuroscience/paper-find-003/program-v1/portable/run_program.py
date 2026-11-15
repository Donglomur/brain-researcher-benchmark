"""Standalone operator entry; never execute candidate code on the host."""
import argparse
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sys.path.insert(0,str(HERE))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request",required=True)
    parser.add_argument("--request-bytes",required=True,type=int)
    parser.add_argument("--request-sha256",required=True)
    args=parser.parse_args()
    from runner import run
    from common import encode
    result=run({"path":args.request,"bytes":args.request_bytes,"sha256":args.request_sha256})
    print(encode({"task_id":result["task_id"],"status":result["status"],
                  "score_status":result["score_status"]}).decode(),end="")

if __name__=="__main__":
    main()

