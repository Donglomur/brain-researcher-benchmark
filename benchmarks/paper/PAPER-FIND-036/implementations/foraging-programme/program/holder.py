"""Trusted bounded tmpfs holder and chunk capture; never parses candidate models."""
import argparse,base64,hashlib,json,os,stat,time
from pathlib import Path

def need(ok,msg):
    if not ok:raise ValueError(msg)
def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['hold','describe','chunk']);p.add_argument('--name');p.add_argument('--cap',type=int,default=0);p.add_argument('--offset',type=int,default=0);p.add_argument('--size',type=int,default=0);a=p.parse_args()
    if a.mode=='hold':
        while True:time.sleep(1)
    need(a.name in ('result.bin','model.bin'),'fixed opaque output name');root=Path('/capture');entries=list(root.iterdir());need(len(entries)==1 and entries[0].name==a.name,'oneexactoutput noextras');path=root/a.name;s=path.lstat();need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and 0<s.st_size<=a.cap,'regular bounded output')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        f=os.fstat(fd);need((f.st_dev,f.st_ino,f.st_size,f.st_mtime_ns)==(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns),'same opened output')
        if a.mode=='describe':
            h=hashlib.sha256();left=s.st_size
            while left:b=os.read(fd,min(left,1048576));need(b,'completeoutput');h.update(b);left-=len(b)
            need(not os.read(fd,1),'outputEOF');value={'bytes':s.st_size,'sha256':h.hexdigest(),'identity':[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]}
        else:
            need(0<=a.offset<s.st_size and 0<a.size<=1048576 and a.offset+a.size<=s.st_size,'boundedexactchunk');os.lseek(fd,a.offset,os.SEEK_SET);b=b''
            while len(b)<a.size:
                part=os.read(fd,a.size-len(b));need(part,'completechunk');b+=part
            value={'offset':a.offset,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'base64':base64.b64encode(b).decode(),'identity':[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]}
        z=os.fstat(fd);need((z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns)==(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns),'stable output capture')
    finally:os.close(fd)
    print(json.dumps(value,separators=(',',':'),allow_nan=False))
if __name__=='__main__':main()
