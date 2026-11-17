"""Build a candidate envelope from label-free public output index, no gold."""
import argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'public'))
from io_contract import *
from array_io import describe

def collect(index,root,arm):
    exact(index,('schema','task_id','query_sha256','cases'));require(index['schema']=='neuroformer_output_index_v1' and index['task_id']==TASK and arm in ARMS,'public output identity');sha256(index['query_sha256'])
    rows=[]
    for i,c in enumerate(index['cases']):
        name=f'predictions/{i:04d}.npy';rows.append({'case_id':c['case_id'],'array':describe(Path(root)/name,name,c['shape'],'<i4' if c['kind']=='counts' else '<f8')})
    return {'schema':'neuroformer_submission_v1','task_id':TASK,'query_sha256':index['query_sha256'],'arm':arm,'predictions':rows}

def main():
    a=argparse.ArgumentParser(description=__doc__)
    for k in ('index','root','arm','output'):a.add_argument('--'+k,required=True)
    z=a.parse_args();save(z.output,collect(load(z.index),z.root,z.arm))
if __name__=='__main__':main()
