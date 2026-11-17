"""Compose the exact original public metadata validator, before any actor exposure."""
import os
import stat
import types
from pathlib import Path
from .common import capture,parse,require,ordinary,stamp,relative,pin,integer

class Compatibility:
    def __init__(self,budget):self.budget=budget;self.metadata_operations=0;self.directory_observations=[]
    need=staticmethod(require)
    parse=staticmethod(parse)
    pin=staticmethod(pin)
    stamp=staticmethod(stamp)
    def path(self,value):
        p=Path(value);require(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)),'canonical original path');return p
    def only_pin(self,d):return {'bytes':d['bytes'],'sha256':d['sha256']}
    def exact_pin(self,d):
        require(type(d)is dict and set(d)=={'bytes','sha256'},'exact original pin')
        integer(d['bytes']);require(type(d['sha256'])is str and len(d['sha256'])==64 and all(c in '0123456789abcdef' for c in d['sha256']),'exact original SHA256')
        return self.only_pin(d)
    def capture(self,path,cap,expected,tick=None,read=None):
        p=self.path(path);s=ordinary(p)
        d=dict(path=p.name,bytes=expected['bytes'],sha256=expected['sha256'],mode=oct(stat.S_IMODE(s.st_mode)),role='qualified_public_metadata')
        return capture(p.parent,d,self.budget,cap)
    def inventory(self,root,byte_cap,file_cap):
        root=self.path(root);files={};dirs=[];total=0
        stack=[root]
        while stack:
            p=stack.pop();s=p.lstat();self.metadata_operations+=1
            require(self.metadata_operations<=100000,'finite complete metadata operation bound')
            require(not stat.S_ISLNK(s.st_mode),'no public alias')
            self.budget.check('original public inventory')
            if stat.S_ISDIR(s.st_mode):
                dirs.append(p)
                observation={'path':str(p),'iterator':None,'closed':False,'errors':[]}
                self.directory_observations.append(observation);first=None;it=None
                try:
                    it=os.scandir(p);observation['iterator']=it
                    children=sorted((Path(e.path) for e in it),reverse=True)
                except BaseException as exc:first=exc;observation['errors'].append(('iteration',exc))
                finally:
                    if it is not None:
                        try:it.close();observation['closed']=True
                        except BaseException as exc:
                            observation['errors'].append(('close',exc))
                            self.budget.uncertain('inventory:'+str(p),'managed_descriptor_closure',exc)
                            if first is None:first=exc
                if first is not None:raise first
                require(len(children)<=file_cap,'bounded original directory');stack.extend(children)
            else:
                require(stat.S_ISREG(s.st_mode) and s.st_nlink==1,'ordinary original public member')
                name=str(p.relative_to(root));relative(name);total+=s.st_size;files[name]=(p,stamp(s))
                require(total<=byte_cap and len(files)<=file_cap,'full original public capacity')
        return files,dirs,total

class OriginalInputs:
    def __init__(self,source,budget):
        self.source=source;self.budget=budget;self.compat=Compatibility(budget)
        self.packet=source.legacy_module('program/packet.py')
        self.packet.c=self.compat;self.packet.core=source.legacy_module('public/interface.py')
    def inspect(self,operator_root,index_descriptor):
        # The exact original packet's TRAINING/CASE/ASSETS/calibration/source-order
        # schema is retained. Numerical array/header qualification is independent.
        body=capture(operator_root,index_descriptor,self.budget,16777216)
        facade=types.SimpleNamespace(tick=lambda:self.budget.check('original packet'),read=self.budget.read)
        index,rows,plan=self.packet.inspect_index(body,facade)
        require(plan['cases']==10 and plan['query_count']==2000,'complete original public panel')
        self.index=index;self.rows={r['person']:r for r in rows};self.original_plan=plan;self.identity=pin(body)
        return self
    def unchanged(self,person):
        row=self.rows[person];files,_,_=self.compat.inventory(row['root'],self.packet.NEURAL_CAP,64)
        require({n:v[1] for n,v in files.items()}==row['stamps'],'same original public input tree')
        self.budget.check('original input before exposure')
