"""Standalone committed-JSON artifact grader; no candidate execution or model fit."""
import argparse,json,os,stat,sys
from pathlib import Path
PACKAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PACKAGE/'private/vendor'))
import candidate,held_scorer,io_support as io,packet

def regular(path,maximum):
 p=Path(path).absolute();st=p.lstat();io.need(all(not q.is_symlink()for q in [p,*p.parents])and stat.S_ISREG(st.st_mode)and st.st_nlink==1 and 0<st.st_size<=maximum,'Bounded unlinked ordinary file');return p

def contained(root,name):
 io.need(type(name)is str and name and '\\'not in name,'Relative path');p=Path(name);io.need(not p.is_absolute()and '..'not in p.parts and p.as_posix()==name,'Canonical contained file');return Path(root)/p

def locked(root,row,maximum):
 p=regular(contained(root,row['path']),maximum);return io.capture(p,row,maximum)

def read_json(path,cap=32768):
 p=regular(path,cap)
 fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 try:
  before=os.fstat(fd)
  io.need(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and 0<before.st_size<=cap,'Bounded ordinary JSON descriptor')
  raw=os.read(fd,cap+1)
  after=os.fstat(fd)
  fields=('st_dev','st_ino','st_size','st_nlink','st_mtime_ns','st_ctime_ns')
  io.need(len(raw)==before.st_size and len(raw)<=cap and all(getattr(before,k)==getattr(after,k)for k in fields),'Stable bounded JSON snapshot')
 finally:os.close(fd)
 return candidate.strict(raw)

def assess(package,op,submission,submission_root):
 phase='candidate';loads=0
 try:
  io.need(type(submission)is dict and set(submission)=={'schema_version','task_id','file'}and type(submission['schema_version'])is int and submission['schema_version']==1 and submission['task_id']=='NEURAL-022','Exact committed artifact manifest')
  row=submission['file'];io.need(type(row)is dict and set(row)=={'path','bytes','sha256'}and type(row['bytes'])is int and 0<row['bytes']<=candidate.MAX_SUBMISSION_BYTES,'Exact bounded prediction descriptor')
  raw=locked(submission_root,row,candidate.MAX_SUBMISSION_BYTES)
  phase='operator';public=candidate.strict(locked(package,op['public']['cases.json'],16384))
  def private_loader():
   nonlocal loads
   loads+=1;io.need(loads==1,'Exactly one private load')
   body=locked(package,op['private'],65536);return packet.private_lists(io.npz(body,io.schema('private',candidate.METHODS)))
  result=candidate.evaluate(raw,public,private_loader,held_scorer.score,op['expected_fixed_reference'])
  return dict(task_id='NEURAL-022',status=result['status'],score=result['primary_score'],higher_is_better=False,result=result,target_loader_calls=loads,candidate_code_executed=False,producer_absence_verified=False,scientific_success=None)
 except Exception as e:return dict(task_id='NEURAL-022',status='invalid_submission'if phase=='candidate'else'operator_error',score=None,error=type(e).__name__+': '+str(e)[:500],target_loader_calls=loads,candidate_code_executed=False)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--submission',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 try:submission=read_json(a.submission)
 except Exception as e:r=dict(task_id='NEURAL-022',status='invalid_submission',score=None,target_loader_calls=0,error=type(e).__name__+': '+str(e)[:500],candidate_code_executed=False)
 else:
  try:op=read_json(PACKAGE/'private/operator_manifest.json')
  except Exception as e:r=dict(task_id='NEURAL-022',status='operator_error',score=None,target_loader_calls=0,error=type(e).__name__+': '+str(e)[:500],candidate_code_executed=False)
  else:r=assess(PACKAGE,op,submission,a.submission.absolute().parent)
 io.need(all(not x.is_symlink()for x in [a.output,*a.output.parents]),'Unlinked fresh report')
 body=io.encoded_json(r);io.need(len(body)<=65536,'Original bounded report size')
 with a.output.open('xb')as f:f.write(body)
 print(json.dumps({'task_id':'NEURAL-022','status':r['status']}));return 2 if r['status']=='operator_error'else 0
if __name__=='__main__':raise SystemExit(main())
