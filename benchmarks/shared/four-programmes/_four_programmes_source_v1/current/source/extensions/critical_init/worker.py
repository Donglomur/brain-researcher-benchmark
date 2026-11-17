"""Fixed future numeric worker CLI, invoked only by the selected outer controller."""
import argparse
from .custody import read_pin,parse,need,write_json
from .guard import Budget
from .workflow import selected_plan,run_numeric_job

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',required=True);p.add_argument('--selection-path',required=True)
    p.add_argument('--selection-bytes',required=True,type=int);p.add_argument('--selection-sha256',required=True)
    p.add_argument('--job',required=True);p.add_argument('--output',required=True)
    p.add_argument('--seconds',required=True,type=float);p.add_argument('--read-bytes',required=True,type=int)
    p.add_argument('--write-bytes',required=True,type=int);p.add_argument('--array-bytes',required=True,type=int)
    p.add_argument('--operation',required=True,choices=['prepare','independent_reference'])
    a=p.parse_args();budget=Budget(seconds=a.seconds,read_bytes=a.read_bytes,write_bytes=a.write_bytes,array_bytes=a.array_bytes)
    authority={'path':a.selection_path,'bytes':a.selection_bytes,'sha256':a.selection_sha256}
    selection,scope,census=selected_plan(a.root,authority,budget,a.operation)
    job=next(j for j in census['jobs']if j['id']==a.job)
    need(job['operation']==a.operation and job['kind']=='numeric','exact selected numeric producer')
    need(a.array_bytes==job['logical_array_bytes'] and a.seconds<=job['limits']['seconds'],'selected exact worker resource envelope')
    return run_numeric_job(a.root,job,a.output,budget)

if __name__=='__main__':main()

