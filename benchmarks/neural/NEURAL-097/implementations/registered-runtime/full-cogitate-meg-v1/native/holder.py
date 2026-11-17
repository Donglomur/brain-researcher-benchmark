"""Read-only output-volume custodian after producer removal; bounded chunks."""
import base64,hashlib,json,os,stat,sys,time
from pathlib import Path
ROOT=Path("/capture")

def need(x,m):
    if not x:raise ValueError(m)

def safe(name):
    p=Path(name)
    need(name and not p.is_absolute()and p.as_posix()==name and all(x not in(".","..")for x in p.parts),"Canonical capture path")
    f=ROOT/p
    need(all(not q.is_symlink()for q in(f,*f.parents)),"No output symlinks")
    s=f.stat();need(stat.S_ISREG(s.st_mode)and s.st_nlink==1,"Only ordinary single-link output")
    return f,s

def digest(f):
    h=hashlib.sha256()
    with f.open("rb")as stream:
        while True:
            b=stream.read(1048576)
            if not b:break
            h.update(b)
    return h.hexdigest()

def main():
    if sys.argv[1]=="hold":
        print("HOLDER_READY",flush=True)
        while True:time.sleep(1)
    if sys.argv[1]=="inventory":
        cap=int(sys.argv[2]);rows=[];total=0
        for f in sorted(ROOT.rglob("*")):
            need(not f.is_symlink(),"Reject output symlink including directories")
            if f.is_dir():continue
            name=f.relative_to(ROOT).as_posix();f,s=safe(name);total+=s.st_size
            need(total<=cap and len(rows)<10000,"Selected full output byte/file limits")
            rows.append({"path":name,"bytes":s.st_size,"sha256":digest(f)})
        print(json.dumps({"files":rows,"total_bytes":total},sort_keys=True));return 0
    need(sys.argv[1]=="chunk"and len(sys.argv)==5,"Exact capture command")
    f,s=safe(sys.argv[2]);offset=int(sys.argv[3]);size=int(sys.argv[4])
    need(0<=offset<=s.st_size and 0<size<=1048576,"Bounded chunk interval")
    with f.open("rb")as stream:stream.seek(offset);b=stream.read(min(size,s.st_size-offset))
    print(json.dumps({"path":sys.argv[2],"offset":offset,"bytes":len(b),"base64":base64.b64encode(b).decode()},sort_keys=True))
    return 0

if __name__=="__main__":raise SystemExit(main())
