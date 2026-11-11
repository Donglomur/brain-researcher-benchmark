"""Actual immutable-image body authentication; no execution or image pulling."""
from .resources import checkpoint, controller_operation, controller_call, controller_iter
import hashlib
import os
import posixpath
import stat
from pathlib import Path
from .io import need,load,digest,owned_resource


@controller_operation
def verify(profile):
    root=Path(profile['rootfs']);need(root.is_absolute()and not root.is_symlink(),'Selected ordinary image root')
    selected=load(profile['rootfs_manifest']['path'],16000000,profile['rootfs_manifest'])
    cap=profile['rootfs_inspection_limits'];rows=[];total=0
    for base,dirs,files in controller_iter(os.walk(root,followlinks=False),'image:iterator:16'):
        checkpoint('image:loop:14')
        for name in controller_iter(sorted(dirs+files),'image:iterator:18'):
            checkpoint('image:loop:15')
            p=Path(base)/name;rel=p.relative_to(root).as_posix();s=p.lstat()
            need(len(rows)<cap['entries'],'Pre-effect image entry bound')
            mode=stat.S_IMODE(s.st_mode)
            if stat.S_ISLNK(s.st_mode):
                target=os.readlink(p)
                resolved=posixpath.normpath(target.lstrip('/')if target.startswith('/')else posixpath.join(posixpath.dirname(rel),target))
                need(resolved!='..'and not resolved.startswith('../'),'Image symlink remains within image namespace')
                row={'path':rel,'kind':'symlink','target':target,'mode':mode}
            elif stat.S_ISDIR(s.st_mode):row={'path':rel,'kind':'directory','mode':mode}
            else:
                need(stat.S_ISREG(s.st_mode)and s.st_nlink==1,'Image has ordinary non-hardlinked files only; devices are explicit mounts')
                need(s.st_size<=cap['member']and total+s.st_size<=cap['total'],'Image read bounds before body access')
                total+=s.st_size;h=hashlib.sha256();n=0
                with owned_resource('image_source_read',lambda:os.open(p,os.O_RDONLY|os.O_NOFOLLOW),os.close) as fd:
                    checkpoint('image_after_open_before_fstat')
                    before=os.fstat(fd)
                    checkpoint('image_after_initial_fstat')
                    while True:
                        checkpoint('image:loop:31')
                        checkpoint('image_before_read_syscall')
                        b=os.read(fd,min(1048576,s.st_size+1-n))
                        checkpoint('image_after_read_syscall')
                        if not b:break
                        n+=len(b);need(n<=s.st_size,'Stable bounded image member');h.update(b)
                    after=os.fstat(fd)
                    need(n==s.st_size and(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
                         (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'Stable exact image body')
                row={'path':rel,'kind':'file','bytes':n,'sha256':h.hexdigest(),'mode':mode}
            rows.append(row)
    actual={'files':sorted(rows,key=lambda x:x['path']),'bytes':total}
    need(actual==selected and digest(actual)==profile['rootfs_identity']==profile['qualified_rootfs_identity'],
         'Actual complete image bodies, not equal caller identity strings')
    return {'identity':digest(actual),'bytes_read':total,'entries':len(rows)}
