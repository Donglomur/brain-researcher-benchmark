"""Concrete owned bounded Linux tmpfs channel mounts, with strict retirement."""
import ctypes
import os
from pathlib import Path
from .core import need


def rows(kernel):
    raw=kernel('/proc/self/mountinfo')
    result=[]
    for line in raw.splitlines():
        left,right=line.split(' - ',1); a=left.split(); b=right.split()
        decoded=a[4]
        for old,new in (('\\040',' '),('\\011','\t'),('\\012','\n'),('\\134','\\')):
            decoded=decoded.replace(old,new)
        result.append({'id':a[0],'device':a[2],'mountpoint':decoded,'options':a[5],
                       'type':b[0],'source':b[1],'super_options':b[2]})
    return raw,result


def mount(path,name,byte_cap,file_cap,kernel,record):
    need(type(record) is dict and not record,'original mount intent owned before effects')
    record.update(path=str(path),name=name,bytes=byte_cap,files=file_cap,attempted=False,
                  mounted=False,unmounted=False,original_before=None,original_after=None)
    before,inventory=rows(kernel); record['original_before']=before
    need(not any(x['mountpoint']==str(path) for x in inventory),'fresh channel has no preexisting mount')
    libc=ctypes.CDLL(None,use_errno=True)
    fn=libc.mount; fn.argtypes=(ctypes.c_char_p,ctypes.c_char_p,ctypes.c_char_p,ctypes.c_ulong,ctypes.c_char_p)
    fn.restype=ctypes.c_int
    options=('size=%d,nr_inodes=%d,uid=65534,gid=65534,mode=0700'%(byte_cap,file_cap)).encode()
    record['attempted']=True
    if fn(name.encode(),os.fsencode(path),b'tmpfs',2|4|8,options)!=0:
        raise OSError(ctypes.get_errno(),'original channel tmpfs mount')
    record['mounted']=True
    after,inventory=rows(kernel); record['original_after']=after
    selected=[x for x in inventory if x['mountpoint']==str(path)]
    need(len(selected)==1 and selected[0]['type']=='tmpfs' and selected[0]['source']==name
         and {'rw','nosuid','nodev','noexec'}<=set(selected[0]['options'].split(',')),
         'actual own bounded tmpfs channel mount')
    v=os.statvfs(path)
    need(0<v.f_blocks*v.f_frsize<=byte_cap and 0<v.f_files<=file_cap,
         'actual tmpfs byte and inode ceilings')
    record['identity']=selected[0]; record['statvfs']={'bytes':v.f_blocks*v.f_frsize,'files':v.f_files}
    return record


def unmount(record,kernel):
    if not record['attempted']: return
    path=Path(record['path']); before,inventory=rows(kernel); record['original_before_unmount']=before
    selected=[x for x in inventory if x['mountpoint']==str(path)]
    if not selected:
        need(not record['mounted'],'previously observed mount cannot silently disappear')
        record['unmounted']=True; return
    need(len(selected)==1 and selected[0]['type']=='tmpfs' and selected[0]['source']==record['name'],
         'recover only exact own attempted mount')
    if 'identity' in record: need(selected[0]==record['identity'],'same actual original mounted channel')
    libc=ctypes.CDLL(None,use_errno=True); fn=libc.umount2
    fn.argtypes=(ctypes.c_char_p,ctypes.c_int); fn.restype=ctypes.c_int
    if fn(os.fsencode(path),0)!=0: raise OSError(ctypes.get_errno(),'strict owned channel unmount; no lazy fallback')
    after,inventory=rows(kernel); record['original_after_unmount']=after
    need(not any(x['mountpoint']==str(path) for x in inventory),'actual removed channel mount')
    record['unmounted']=True
