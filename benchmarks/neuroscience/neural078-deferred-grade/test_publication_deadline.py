"""Focused V2 publication-clock and own-marker tests; native boundary is stubbed."""
import hashlib,json,os,sys,tempfile,types
from pathlib import Path
HERE=Path(__file__).resolve().parent
READS=0
def load(name,path):
    global READS
    b=path.read_bytes();READS+=len(b);m=types.ModuleType(name);m.__file__=str(path);sys.modules[name]=m;exec(compile(b,str(path),'exec'),m.__dict__);return m
io=load('bound_io',HERE/'bound_io.py');g=load('_deadline_grade_v2',HERE/'grading.py')
class Clock:
    value=0.
    def monotonic(self):return self.value
clock=Clock();g.time=clock;g.command=lambda *a:['create','generated'];g.verify=lambda *a:None
score={'schema':'neural078_numeric_grade_v1','score':1.,'matching_fields':195,'required_fields':195,'full_reconstruction':True,'effect_sign_is_not_a_pass_criterion':True,'field_checks':[{'field':'generated'+str(i),'matches':True} for i in range(195)]}
class Engine:
    def __init__(self,*a):self.commands=[]
    def own(self,*a):pass
    def run(self,args,**kw):return types.SimpleNamespace(returncode=0,stdout=json.dumps(score).encode() if args[0]=='start' else b'created',stderr=b'')
    def inspect(self,*a):return {'State':{'Status':'exited','Running':False,'Dead':False,'Pid':0,'ExitCode':0,'OOMKilled':False}}
    def cleanup(self,*a):return {'absence_verified':True}
class Budget:
    def __init__(self,mode):self.mode=mode
    def write(self,path,body,**kw):Path(path).write_bytes(body)
    def save(self,path,obj,cap=200000,publication=None,**kw):
        path=Path(path);body=(json.dumps(obj,sort_keys=True)+'\n').encode();assert len(body)<=cap
        path.write_bytes(body);s=path.stat();pin={'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
        if publication is not None:publication.update(st_dev=s.st_dev,st_ino=s.st_ino,**pin)
        if path.name=='GRADE_COMPLETION.json':
            if self.mode=='late':clock.value=31.
            elif self.mode=='interrupted':raise OSError('generated post-publication failure')
            elif self.mode=='foreign':
                foreign=path.with_name('foreign.tmp');foreign.write_bytes(b'foreign replacement\n');os.replace(foreign,path);raise OSError('generated replacement after publication')
            elif self.mode=='pending':
                os.link(path,path.with_name('.'+path.name+'.pending'));raise OSError('generated pending-link interruption')
            else:clock.value=1.
        return pin
outcomes=[]
for mode in ('normal','late','interrupted','foreign','pending'):
    with tempfile.TemporaryDirectory(prefix='n078-deadline-') as d:
        folder=Path(d).resolve();clock.value=0.;error=None;returned=None
        try:returned=g.run({'engine_class':Engine,'contract':types.SimpleNamespace(IMAGE='generated')},folder,{},Budget(mode),180)
        except (ValueError,OSError) as e:error=e
        marker=folder/'GRADE_COMPLETION.json'
        if mode=='normal':assert returned['success'] is True and error is None and marker.exists() and clock.value==1.
        elif mode=='foreign':assert isinstance(error,OSError) and marker.read_bytes()==b'foreign replacement\n'
        else:
            assert error is not None and not marker.exists()
            if mode=='late':assert 'Original30second grade phase includes completion publication' in str(error)
            if mode=='pending':assert (folder/'.GRADE_COMPLETION.json.pending').exists()
        outcomes.append({'case':mode,'passed':True,'marker_exists':marker.exists(),'clock':clock.value,'exception':type(error).__name__ if error else None})
print(json.dumps({'generated_only':True,'native_profile_stubbed':True,'actual_Docker_or_targets':False,'cases':outcomes,'explicit_source_reads':READS,'small_generated_marker_reads_additional':True}))
