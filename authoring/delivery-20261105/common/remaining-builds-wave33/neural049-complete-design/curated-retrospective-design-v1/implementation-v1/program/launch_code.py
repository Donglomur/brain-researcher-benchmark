"""Literal captured source launcher. External caller authenticates this literal."""
CODE = r'''
import hashlib,json,math,os,stat,sys,time,types
from pathlib import Path
config=json.loads(sys.argv[1]);origin=config['origin'];deadline=config['bootstrap_deadline']
if any(type(x)not in(int,float) or not math.isfinite(x) for x in(origin,deadline)) or not origin<deadline:
 raise ValueError('source launch original clocks')
account={'reserved':0,'observed':0,'attempted':[]}
def tick():
 if not origin<=time.monotonic()<deadline:raise ValueError('original launch clock')
def body(name,desc):
 tick();text=config['source_root']+'/'+name;p=Path(text)
 if not text.startswith('/') or text.startswith('//') or str(p)!=text or '..'in p.parts:raise ValueError('canonical source name')
 for parent in reversed(p.parents):
  if not stat.S_ISDIR(os.lstat(parent).st_mode):raise ValueError('source parent custody')
 if type(desc['bytes'])is not int or not 0<=desc['bytes']<=2097152:raise ValueError('bounded entry bytes')
 account['reserved']+=desc['bytes']+1;account['attempted'].append(text)
 if account['reserved']>config['launch_source_read_cap']:raise ValueError('launch source allowance')
 fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 try:
  st=os.fstat(fd)
  if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1 or st.st_size!=desc['bytes']:raise ValueError('entry extent')
  raw=bytearray()
  while len(raw)<desc['bytes']:
   tick();part=os.read(fd,min(65536,desc['bytes']-len(raw)));account['observed']+=len(part)
   if not part:raise ValueError('entry truncated')
   raw.extend(part)
  extra=os.read(fd,1);account['observed']+=len(extra)
  stamp=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
  if extra or stamp(st)!=stamp(os.fstat(fd)) or stamp(st)!=stamp(os.lstat(p)):raise ValueError('entry changed')
  if hashlib.sha256(raw).hexdigest()!=desc['sha256']:raise ValueError('entry hash')
  tick();return bytes(raw)
 finally:
  first=sys.exception()
  try:os.close(fd)
  except BaseException as later:
   if first is not None:raise BaseExceptionGroup('entry capture and close',[first,later]) from None
   raise
try:
 bootstrap=body('program/bootstrap.py',config['bootstrap_source'])
 entry=body('program/entry.py',config['entry_source'])
 module=types.ModuleType('_neural049_bootstrap');tick();exec(compile(bootstrap,'<captured bootstrap>','exec'),module.__dict__);tick()
 namespace={'__name__':'_neural049_entry'};exec(compile(entry,'<captured entry>','exec'),namespace);tick()
 result=namespace['main'](config,module.load,account)
 print(json.dumps(result,allow_nan=False,separators=(',',':')))
except BaseException as error:
 report={'status':'failed','error_type':type(error).__name__,'launch_source_accounting':account,
         'failure':getattr(error,'failure_record',None)}
 raw=json.dumps(report,allow_nan=False,separators=(',',':'))
 print(raw if len(raw.encode())<=60000 else json.dumps({'status':'failed','error_type':type(error).__name__,
       'launch_source_accounting':account,'failure_record_truncated':True}))
 raise SystemExit(1)
'''
