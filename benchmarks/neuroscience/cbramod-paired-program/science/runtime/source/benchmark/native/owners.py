"""Physical owner admission; metadata only, no native/data reads."""
import stat,unicodedata
from pathlib import Path

def need(ok,msg):
 if not ok:raise ValueError(msg)
def admit_owners(existing,future):
 need(type(existing)is dict and type(future)is dict and not set(existing)&set(future),'distinct named owner roles')
 roots={}
 for key,value in {**existing,**future}.items():
  raw=Path(value).absolute()
  need('..'not in raw.parts and not any(p.is_symlink()for p in(raw,*raw.parents)),'ordinary normalized owner ancestry')
  if key in existing:
   need(raw.is_dir(),'existing directory owner');path=raw.resolve(strict=True)
  else:
   need(raw.name not in('','.','..')and not raw.exists(),'fresh future owner')
   need(raw.parent.is_dir(),'existing ordinary future parent');path=raw.parent.resolve(strict=True)/raw.name
  roots[key]=path
 def inode(path):
  s=path.stat();need(stat.S_ISDIR(s.st_mode),'directory ancestry');return s.st_dev,s.st_ino
 values=list(roots.values());need(len(set(values))==len(values),'different canonical owners')
 need(not any(a in b.parents for a in values for b in values if a!=b),'nonnested canonical owners')
 ancestry={k:{inode(a)for a in v.parents}for k,v in roots.items()}
 ids={k:inode(roots[k])for k in existing};need(len(set(ids.values()))==len(ids),'different physical existing owners')
 for key,identity in ids.items():need(all(identity not in ancestry[other]for other in roots if other!=key),'nonnested physical owners despite case aliases')
 names=[(inode(v.parent),unicodedata.normalize('NFD',v.name).casefold())for v in values]
 need(len(set(names))==len(names),'no case/Unicode equivalent future siblings')
 return roots
