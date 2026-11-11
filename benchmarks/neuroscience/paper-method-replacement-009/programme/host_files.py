"""Actual coordinator file-operation prefixes; physical storage effects stay unknown."""
from pathlib import Path
import stat
from .native import io
class HostFiles:
 def __init__(self,caps,owner):
  self.caps=caps;self.owner=owner;self.rows=[];self.reserved={'read_bytes':0,'write_bytes':0,'files':0};self.known={'read_bytes':0,'write_bytes':0}
  owner.record['host_io']={'operations':self.rows,'reserved':self.reserved,'known_returned':self.known,'physical':'UNKNOWN'}
 def reserve(self,kind,path,size):
  io.need(type(size)is int and size>=0 and size<=self.caps['member_bytes'],'host per-file ceiling')
  field=kind+'_bytes';io.need(self.reserved[field]+size<=self.caps[field]and self.reserved['files']<self.caps['files'],'whole host I/O ceiling')
  self.reserved[field]+=size;self.reserved['files']+=1
  row={'kind':kind,'path':str(path),'reserved':size,'known_returned':0,'status':'attempted','physical':'UNKNOWN'};self.rows.append(row);return row
 def read(self,path,cap,pin=None):
  row=self.reserve('read',path,cap)
  try:
   body=io.read(path,cap,pin);row.update(known_returned=len(body),status='complete');self.known['read_bytes']+=len(body);return body
  except BaseException as exc:row['status']='failed_prefix_unknown';self.owner.fail(exc,'host_read');raise
 def write(self,path,body,cap):
  io.need(len(body)<=cap,'host write member');row=self.reserve('write',path,len(body))
  try:
   pin=io.write_new(path,body,cap);row.update(known_returned=len(body),status='complete');self.known['write_bytes']+=len(body);return pin
  except BaseException as exc:row['status']='failed_prefix_unknown';self.owner.fail(exc,'host_write');raise
 def load(self,path,cap=1048576,pin=None):return io.parse(self.read(path,cap,pin))
 def dump(self,path,value,cap=1048576):return self.write(path,io.canonical(value)+b'\n',cap)
 def tree(self,root,*,total,member,files):
  root=Path(root).absolute();io.need(root.is_dir()and not root.is_symlink(),'host ordinary root');rows=[];used=0
  for p in sorted(root.rglob('*')):
   st=p.lstat()
   if stat.S_ISDIR(st.st_mode):continue
   io.need(stat.S_ISREG(st.st_mode)and st.st_nlink==1,'host ordinary finite tree')
   io.need(len(rows)<files and used+st.st_size<=total,'host pre-read tree total')
   body=self.read(p,min(member,st.st_size));used+=len(body);rows.append({'path':io.relative(p.relative_to(root).as_posix()),**io.identity(body),'mode':stat.S_IMODE(st.st_mode)})
  return {'files':rows,'bytes':used,'identity':io.digest(rows)}
