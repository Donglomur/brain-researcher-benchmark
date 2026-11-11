"""Ordinary source-plan inspection only; no scientific execution command."""
import argparse
from .domain import parse_plan, readiness, Pin, Limits, canonical
from .custody import Budget, Store

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--plan-root',required=True);p.add_argument('--plan-path',required=True)
    p.add_argument('--plan-bytes',type=int,required=True);p.add_argument('--plan-sha256',required=True)
    p.add_argument('--read-cap',type=int,required=True);p.add_argument('--wall-ns',type=int,required=True)
    args=p.parse_args()
    limits=Limits(args.read_cap,args.read_cap,1,1,args.wall_ns,1,1,1)
    budget=Budget(limits);store=Store(args.plan_root,budget)
    try:
        plan=parse_plan(store.json(Pin(args.plan_path,args.plan_bytes,args.plan_sha256)))
        print(canonical(readiness(plan)).decode())
    finally: store.close_once()

if __name__=='__main__':main()
