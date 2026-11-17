"""Authenticate an entire selected mount, rejecting extra files and aliases."""
import os
import stat
from .strict import require, integer, relative

def verify_tree(root, rows, *, byte_cap, file_cap, clock):
    require(type(rows) is list and len(rows)<=file_cap,"whole mount file cap")
    expected={r["path"]:r for r in rows};require(len(expected)==len(rows),"duplicate mount path")
    for path in expected:relative(path)
    expected_dirs={"/".join(path.split("/")[:i]) for path in expected for i in range(1,len(path.split("/")))}
    found=set();dirs=set();count=0;total=0
    def walk(fd,prefix):
        nonlocal count,total
        with os.scandir(fd) as entries:
            for entry in entries:
                clock.check();name=entry.name
                path=prefix+"/"+name if prefix else name
                st=entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(st.st_mode):
                    require(path in expected_dirs,"undeclared mount directory")
                    dirs.add(path)
                    child=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
                    try:walk(child,path)
                    finally:os.close(child)
                else:
                    require(stat.S_ISREG(st.st_mode) and st.st_nlink==1,"mount aliases/nonregular entry")
                    require(path in expected,"undeclared mount file")
                    count+=1;require(count<=file_cap,"mount file cap")
                    total+=integer(expected[path]["bytes"],"file bytes");require(total<=byte_cap,"whole mount byte cap")
                    root.authenticate(path,expected[path],cap=byte_cap,clock=clock);found.add(path)
    walk(root.fd,"")
    require(found==set(expected) and dirs==expected_dirs,"incomplete mount")
    return {"files":count,"authenticated_bytes":total,"root_identity":root.identity}
