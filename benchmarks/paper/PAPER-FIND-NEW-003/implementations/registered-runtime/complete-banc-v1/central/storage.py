"""Owned immutable staging and complete ordinary output inventories."""
import os,stat
from pathlib import Path
from banc_runtime.codec import relative,need,descriptor,pin
from .io import absolute_directory,metadata,write,read,integer

def parents(root,name):
    from .custody import parent
    cap,leaf=parent(root,name,create=True)
    return cap/leaf

def copy(root,destination,raw,meter):
    from .clock import guard
    guard(meter,'before_staging_parents');parents(root,destination)
    guard(meter,'after_staging_parents');return write(root,destination,raw,meter)

def census(root,meter,*,cap,total_cap,member_cap=10000,exclude=()):
    from .clock import guard
    root=absolute_directory(root);result={};total=0
    def visit(directory,prefix=''):
        nonlocal total
        guard(meter,'before_output_census');directory.verify()
        for name in sorted(os.listdir(directory.fd)):
            st=os.stat(name,dir_fd=directory.fd,follow_symlinks=False);rel=prefix+name
            if stat.S_ISDIR(st.st_mode):visit(directory.child(name),rel+'/');continue
            need(stat.S_ISREG(st.st_mode) and st.st_nlink==1,'ordinary single-link output')
            total+=st.st_size;need(st.st_size<=cap and total<=total_cap,'whole output extent limits')
            if rel in exclude:continue
            need(len(result)<member_cap,'whole output member ceiling')
            raw=metadata(directory/name,meter,st.st_size)
            result[rel]={'path':rel,**pin(raw)}
        directory.verify();guard(meter,'after_output_census')
    visit(root);return result,total

def role_index(method):
    index={}
    for role,files in method['data'].items():
        for d in files:
            descriptor(d)
            if d['path'] in index:need(index[d['path']]['descriptor']==d,'shared role path has one exact content')
            else:index[d['path']]={'descriptor':d,'roles':[]}
            index[d['path']]['roles'].append(role)
    return index

def checked_binding(name,binding,method):
    need(type(binding) is dict and set(binding)=={'role','descriptor'},'data role binding')
    need(binding['role'] in method['data'] and binding['descriptor'] in method['data'][binding['role']],'exact declared original role file')
    need(name==binding['descriptor']['path'],'data input path is original explicit relative path')
    return binding
