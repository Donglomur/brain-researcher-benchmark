"""Actual XFS project-quota admission; no native operation at module import.

API facts are derived from Linux v6.12, adc218676eef25575469234709c2d87185ca223a,
fs.h/quota.h/dqblk_xfs.h. Full upstream bodies stay outside the source release.
Only Linux x86_64/aarch64 little-endian LP64 is supported pending actual ABI and
adversarial isolation qualification. The code never enables/disables a quota
subsystem, borrows an existing project, resets usage, or removes a failed lease.
"""
import ctypes,fcntl,os,stat,sys
from pathlib import Path
from .protocol import Directory,fields,need,integer,digest,encode,persist,observation


class DiskQuota(ctypes.Structure):
    _fields_=[('version',ctypes.c_int8),('flags',ctypes.c_int8),('mask',ctypes.c_uint16),('project',ctypes.c_uint32)]+[(n,ctypes.c_uint64) for n in ('blocks_hard','blocks_soft','inodes_hard','inodes_soft','blocks_used','inodes_used')]+[('inode_timer',ctypes.c_int32),('block_timer',ctypes.c_int32),('inode_warnings',ctypes.c_uint16),('block_warnings',ctypes.c_uint16),('inode_timer_high',ctypes.c_int8),('block_timer_high',ctypes.c_int8),('realtime_timer_high',ctypes.c_int8),('pad2',ctypes.c_int8)]+[(n,ctypes.c_uint64) for n in ('realtime_hard','realtime_soft','realtime_used')]+[('realtime_timer',ctypes.c_int32),('realtime_warnings',ctypes.c_uint16),('pad3',ctypes.c_int16),('pad4',ctypes.c_char*8)]


class QuotaFile(ctypes.Structure):
    _fields_=[('inode',ctypes.c_uint64),('blocks',ctypes.c_uint64),('extents',ctypes.c_uint32),('pad',ctypes.c_uint32)]


class QuotaStatus(ctypes.Structure):
    _fields_=[('version',ctypes.c_int8),('pad1',ctypes.c_uint8),('flags',ctypes.c_uint16),('in_core',ctypes.c_uint32),('user',QuotaFile),('group',QuotaFile),('project',QuotaFile),('block_time',ctypes.c_int32),('inode_time',ctypes.c_int32),('realtime_time',ctypes.c_int32),('block_warnings',ctypes.c_uint16),('inode_warnings',ctypes.c_uint16),('realtime_warnings',ctypes.c_uint16),('pad3',ctypes.c_uint16),('pad4',ctypes.c_uint32),('pad2',ctypes.c_uint64*7)]


class FileAttributes(ctypes.Structure):
    _fields_=[('flags',ctypes.c_uint32),('extent_size',ctypes.c_uint32),('extents',ctypes.c_uint32),('project',ctypes.c_uint32),('cow_extent_size',ctypes.c_uint32),('pad',ctypes.c_uint8*8)]


def abi():
    need(os.uname().sysname=='Linux' and os.uname().machine in ('x86_64','aarch64') and sys.byteorder=='little' and ctypes.sizeof(ctypes.c_void_p)==8,'explicit supported Linux project-quota ABI')
    need(ctypes.sizeof(DiskQuota)==112 and ctypes.sizeof(QuotaStatus)==160 and ctypes.sizeof(FileAttributes)==28,'exact selected native structure widths')
    need(DiskQuota.blocks_hard.offset==8 and DiskQuota.realtime_hard.offset==72 and QuotaStatus.project.offset==56 and FileAttributes.project.offset==12,'exact selected native field alignment')


class NativeQuotaAPI:
    def __init__(self,device):
        abi();self.device_fd=os.open(device,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            st=os.fstat(self.device_fd);need(stat.S_ISBLK(st.st_mode),'held actual mounted block device for quotactl');self.device_number=st.st_rdev;self.device_path=('/proc/self/fd/'+str(self.device_fd)).encode();self.libc=ctypes.CDLL(None,use_errno=True);self.function=self.libc.quotactl;self.function.argtypes=(ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_void_p);self.function.restype=ctypes.c_int
        except BaseException:
            self.close();raise
    def query(self,operation,project,value):
        command=(((ord('X')<<8)+operation)<<8)|2;ctypes.set_errno(0)
        if self.function(command,self.device_path,project,ctypes.byref(value))!=0:
            code=ctypes.get_errno();raise OSError(code,os.strerror(code),'original quotactl operation '+str(operation))
        return value
    def status(self):
        value=QuotaStatus();value.version=1;self.query(8,0,value);need(value.version==1,'original requested quota status version');return {'version':int(value.version),'flags':int(value.flags)}
    def get(self,project):
        value=DiskQuota();value.version=1;value.flags=2;value.project=project;self.query(3,project,value);need(value.version==1 and value.flags&2 and value.project==project,'exact queried project identity/version');return {name:int(getattr(value,name)) for name in ('project','blocks_hard','blocks_soft','inodes_hard','inodes_soft','blocks_used','inodes_used','realtime_hard','realtime_soft','realtime_used')}
    def set_limits(self,project,blocks,inodes):
        value=DiskQuota();value.version=1;value.flags=2;value.project=project;value.mask=15;value.blocks_hard=blocks;value.inodes_hard=inodes;self.query(4,project,value)
    def attributes(self,fd):
        raw=bytearray(28);fcntl.ioctl(fd,(2<<30)|(28<<16)|(ord('X')<<8)|31,raw,True);return FileAttributes.from_buffer_copy(raw)
    def set_project(self,fd,attributes,project):
        attributes.project=project;attributes.flags|=0x200;raw=bytearray(bytes(attributes));fcntl.ioctl(fd,(1<<30)|(28<<16)|(ord('X')<<8)|32,raw,True)
    def close(self):
        fd=self.device_fd;self.device_fd=None
        if fd is not None:os.close(fd)


class ProjectQuota:
    def __init__(self,configuration,budget):
        fields(configuration,('kind','device','lease_root','project_first','project_last','qualification','abi_source_commit'),'concrete actual XFS project quota')
        need(configuration['kind']=='xfs_project_quota_v1' and configuration['abi_source_commit']=='adc218676eef25575469234709c2d87185ca223a','one concrete versioned quota implementation');digest(configuration['qualification']);integer(configuration['project_first'],'first dedicated project',1,2**31-1);integer(configuration['project_last'],'last dedicated project',configuration['project_first'],2**31-1)
        self.config=configuration;self.budget=budget;self.leases=Directory(configuration['lease_root']);self.native=None;self.next_project=configuration['project_first'];self.jobs={}
        try:self.native=NativeQuotaAPI(configuration['device'])
        except BaseException:
            self.leases.close();raise
    def acquire(self,job,workspace,requested,limits):
        need(job not in self.jobs and self.next_project<=self.config['project_last'],'fresh project and full selected finite project range');project=self.next_project;self.next_project+=1
        row={'job':job,'project':project,'phase':'original_lease','workspace_identity':{'device':os.fstat(workspace.fd).st_dev,'inode':os.fstat(workspace.fd).st_ino},'before':None,'admitted':None,'failures':[]};self.jobs[job]=row
        # Exclusive durable lease precedes every kernel mutation. A previous
        # failed or used ID is never silently retried, skipped or recycled.
        row['lease']=persist(self.leases,str(project)+'.json',encode({'job':job,'project':project,'workspace_identity':row['workspace_identity'],'quota_source_commit':self.config['abi_source_commit'],'reusable':False}),ledger=self.budget)
        try:
            need(row['workspace_identity']['device']==self.native.device_number,'held workspace resides on the exact queried block device')
            need(not os.listdir(workspace.fd),'project inheritance assigned before any candidate-created descendant')
            status=self.native.status();need(status['flags']&48==48,'actual kernel project accounting AND enforcement enabled')
            before=self.native.get(project);row['before']=before;need(all(before[k]==0 for k in ('blocks_hard','blocks_soft','inodes_hard','inodes_soft','blocks_used','inodes_used','realtime_hard','realtime_soft','realtime_used')),'unused dedicated project, never alter an existing allocation')
            attributes=self.native.attributes(workspace.fd);need(attributes.project==0 and not(attributes.flags&0x101),'fresh non-realtime workspace before selected project assignment')
            blocks=(requested['scratch_bytes']+requested['output_bytes'])//512;need(blocks>0 and limits['files']>0,'finite nonzero hard block/inode limits, zero would mean unlimited');row['requested_hard_bytes']=blocks*512;row['requested_hard_inodes']=limits['files']
            self.native.set_limits(project,blocks,limits['files']);row['phase']='limits_set';self.native.set_project(workspace.fd,attributes,project);row['phase']='workspace_assigned'
            attrs=self.native.attributes(workspace.fd);after=self.native.get(project);need(attrs.project==project and attrs.flags&0x200 and not(attrs.flags&0x101),'actual inherited project, no realtime escape');need(after['blocks_hard']==blocks and after['inodes_hard']==limits['files'] and after['blocks_soft']==after['inodes_soft']==0,'kernel returned exact finite selected limits')
            row['admitted']={'status':status,'quota':after,'flags':int(attrs.flags)};row['phase']='admitted';return row
        except BaseException as exc:row['failures'].append(observation(exc));row['phase']='failed_original_admission';raise
    def assign_observer(self,job,observer):
        row=self.jobs[job];need(row['phase']=='admitted' and os.fstat(observer.fd).st_dev==self.native.device_number and not os.listdir(observer.fd),'same actual filesystem and initially empty original observer directory');attributes=self.native.attributes(observer.fd);need(attributes.project==0 and not(attributes.flags&0x101),'fresh non-realtime observer directory');self.native.set_project(observer.fd,attributes,row['project']);after=self.native.attributes(observer.fd);need(after.project==row['project'] and after.flags&0x200,'observer trace/stdout/stderr count against SAME original hard project quota');row['observer_project_assigned']=True
    def observe(self,job,workspace):
        row=self.jobs[job];need(row['phase']=='admitted','original admitted project');status=self.native.status();attrs=self.native.attributes(workspace.fd);value=self.native.get(row['project']);need(status['flags']&48==48 and attrs.project==row['project'] and attrs.flags&0x200 and not(attrs.flags&0x101),'quota enforcement and inheritance unchanged')
        need(value['blocks_hard']*512==row['requested_hard_bytes'] and value['inodes_hard']==row['requested_hard_inodes'],'same original hard ceilings');need(value['blocks_used']<=value['blocks_hard'] and value['inodes_used']<=value['inodes_hard'],'kernel observed project usage within hard ceilings');row['final']={'kernel_quota':value,'allocated_bytes':value['blocks_used']*512,'allocated_inodes':value['inodes_used'],'limits_left_in_place':True,'files_not_deleted_or_refunded':True};return row['final']
    def close(self):
        failures=[]
        for h in (self.native,self.leases):
            try:h.close()
            except BaseException as e:failures.append(observation(e))
        need(not failures,'original quota observer handle closure: '+str(failures))
