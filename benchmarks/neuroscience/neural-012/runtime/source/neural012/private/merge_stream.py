"""Merge exactly23 source LOPO outputs and one full-target output, no execution."""
import argparse
from pathlib import Path
import io_contract as io
import analysis

def merge(panel_raw,source_outputs,target_output,arm):
 records=analysis.panel(io.strict(panel_raw));source_people={r['patient_id'] for r in records.values() if r['cohort']=='CHB'};io.need(arm in analysis.ARMS and len(source_outputs)==23,'full23folds');seen=set();rows=[]
 for pid,out in source_outputs:
  io.need(pid in source_people and pid not in seen,'unique sourceheldperson');seen.add(pid);io.fields(out,['schema_version','task_id','arm','records']);io.need(type(out['schema_version'])is int and out['schema_version']==1 and out['task_id']==io.TASK and out['arm']==arm,'sourcearmidentity')
  expected={rid for rid,r in records.items() if r['cohort']=='CHB' and r['patient_id']==pid};got=[r['recording_id'] for r in out['records']];io.need(len(got)==len(set(got)) and set(got)==expected,'whole heldperson output');rows.extend(out['records'])
 io.fields(target_output,['schema_version','task_id','arm','records']);io.need(type(target_output['schema_version'])is int and target_output['schema_version']==1 and target_output['task_id']==io.TASK and target_output['arm']==arm,'targetarmidentity');expected={rid for rid,r in records.items() if r['cohort']=='Siena'};got=[r['recording_id'] for r in target_output['records']];io.need(len(got)==len(set(got)) and set(got)==expected,'whole14patienttarget output');rows.extend(target_output['records'])
 value={'schema_version':1,'task_id':io.TASK,'arm':arm,'records':sorted(rows,key=lambda r:r['recording_id'])};analysis.admit_stream(value,records);return value
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--panel',type=Path,required=True);p.add_argument('--arm',choices=analysis.ARMS,required=True);p.add_argument('--source-output',nargs=2,action='append',metavar=('PATIENT','FILE'),required=True);p.add_argument('--target-output',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();io.need(not a.output.exists() and not a.output.is_symlink(),'freshoutput');io.write(a.output,merge(io.read(a.panel,3000000),[(pid,io.strict(io.read(Path(path)))) for pid,path in a.source_output],io.strict(io.read(a.target_output)),a.arm))
