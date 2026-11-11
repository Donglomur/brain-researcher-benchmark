"""Bounded publisher metadata/header acquisition; never download EEG samples."""
import hashlib,json,urllib.request,re,time,shutil
from pathlib import Path
BASE='https://physionet.org/files/siena-scalp-eeg/1.0.0/'

def main():
 package=Path(__file__).resolve().parents[1];root=package/'source' if (package/'source').is_dir() else package/'private/source';root.mkdir(exist_ok=True)
 need=13188761753+100000000+20*1024**3
 assert shutil.disk_usage(root).free>=need,'reserved disk floor'
 pins={line.split(maxsplit=1)[1]:line.split()[0] for line in (root/'SHA256SUMS.txt').read_text().splitlines()}
 ledger=[];charged=0;started=time.monotonic()
 def fetch(path,header_bytes=None):
  nonlocal charged
  assert charged<5000000 and time.monotonic()-started<600,'bounded source intake'
  url=BASE+path
  if header_bytes:url+='?source-header='+str(header_bytes)
  req=urllib.request.Request(url,headers={'Range':f'bytes=0-{header_bytes-1}'} if header_bytes else {})
  with urllib.request.urlopen(req,timeout=30) as response:
   cap=header_bytes if header_bytes else 100000
   if header_bytes:
    assert response.status==206,'server must honor bounded header range'
    cr=re.fullmatch(r'bytes 0-(\d+)/(\d+)',response.headers['Content-Range']);assert cr and int(cr[1])+1==header_bytes
   data=response.read(cap+1);charged+=len(data);assert 0<len(data)<=cap
   if header_bytes:assert len(data)==header_bytes
   row={'path':path,'header_bytes':header_bytes,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'source_bytes':int(cr[2]) if header_bytes else len(data)}
  if not header_bytes:assert row['sha256']==pins[path],'publisher content SHA'
  ledger.append(row);return data,row
 for path in ['LICENSE.txt']+[p for p in pins if p.endswith('.txt') and 'Seizures-list' in p]:
  dest=root/path;dest.parent.mkdir(exist_ok=True)
  if dest.exists():assert hashlib.sha256(dest.read_bytes()).hexdigest()==pins[path];continue
  data,_=fetch(path);dest.write_bytes(data)
 rows=[]
 for path in (root/'RECORDS').read_text().splitlines():
  dest=root/'headers'/(path.replace('/','__')+'.header');dest.parent.mkdir(exist_ok=True)
  first,_=fetch(path,256);n=int(first[184:192]);assert 256<n<=131328
  data,row=fetch(path,n);assert data[:256]==first;dest.write_bytes(data)
  row.update({'header_file':str(dest.relative_to(root)),'source_sha256':pins[path]});rows.append(row)
 (root/'HEADERS.json').write_text(json.dumps({'schema':'siena_source_headers_v1','records':rows,'body_samples_read':False},indent=2)+'\n')
 (root/'HEADER_INTAKE.json').write_text(json.dumps({'status':'closed','response_bytes':charged,'duration_seconds':time.monotonic()-started,'requests':ledger},indent=2)+'\n')
 print(json.dumps({'records':len(rows),'response_bytes':charged,'status':'closed'}))
if __name__=='__main__':main()
