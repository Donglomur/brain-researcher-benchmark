#!/usr/bin/env python3
"""Ordinary manifest-file ABI for default complete and named OFC conditions."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from ofc.operator import execute
def main():
 p=argparse.ArgumentParser();p.add_argument('--program',required=True);p.add_argument('--output',required=True);p.add_argument('--review',required=True);p.add_argument('--other-reserve-bytes',required=True,type=int);p.add_argument('--condition',default='all',choices=('all','I_A','I_B','R_A','R_B'));a=p.parse_args()
 def emit(result):
  print(json.dumps({'task_id':result['task_id'],'conditions':result['condition_order'],'scientifically_qualified':False,'report':str(Path(a.output)/'REPORT.json'),'requires_original_zero_exit':True}),flush=True)
 execute(a.program,a.output,a.review,a.other_reserve_bytes,a.condition,on_complete=emit);return 0
if __name__=='__main__':raise SystemExit(main())
