"""Concrete Linux-only trusted-issuer restriction, never executed at import.

Qualification must establish syscall/namespace/Landlock behavior in the selected
kernel and interpreter. Unsupported or denied mechanisms fail before input FDs.
There is no success-flag replacement for the actual restriction syscalls.
"""
import ctypes,errno,os,platform,resource,socket
import common as c

def restrict(selected):
    c.exact(selected,('platform','machine','minimum_landlock_abi','memory_bytes','cpu_seconds','max_open_files'))
    c.need(selected['platform']=='Linux'and platform.system()=='Linux'and platform.machine()==selected['machine']and selected['machine']in ('x86_64','aarch64'),'selected supported Linux syscall ABI')
    for name in ('minimum_landlock_abi','memory_bytes','cpu_seconds','max_open_files'):c.integer(selected[name],1)
    libc=ctypes.CDLL(None,use_errno=True);libc.syscall.restype=ctypes.c_long
    def syscall(number,*args):
        value=libc.syscall(ctypes.c_long(number),*args)
        if value<0:raise OSError(ctypes.get_errno(),'selected issuer restriction syscall failed')
        return int(value)
    # The same three generic syscall numbers are selected for these two Linux ABIs.
    abi=syscall(444,ctypes.c_void_p(),ctypes.c_size_t(0),ctypes.c_uint(1))
    c.need(abi>=selected['minimum_landlock_abi']and abi>=3,'Landlock truncate/right coverage required')
    uid,gid=os.getuid(),os.getgid();c.need(uid!=0,'unprivileged outer issuer identity')
    libc.unshare.argtypes=[ctypes.c_int];libc.unshare.restype=ctypes.c_int
    c.need(libc.unshare(0x10000000)==0,'new user namespace required')
    # These are this worker's own namespace maps, before filesystem restriction.
    with open('/proc/self/setgroups','w',encoding='ascii')as s:s.write('deny\n')
    with open('/proc/self/uid_map','w',encoding='ascii')as s:s.write('0 '+str(uid)+' 1\n')
    with open('/proc/self/gid_map','w',encoding='ascii')as s:s.write('0 '+str(gid)+' 1\n')
    c.need(libc.unshare(0x40000000)==0,'fresh network namespace required')
    resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_AS,(selected['memory_bytes'],selected['memory_bytes']))
    resource.setrlimit(resource.RLIMIT_CPU,(selected['cpu_seconds'],selected['cpu_seconds']))
    resource.setrlimit(resource.RLIMIT_NOFILE,(selected['max_open_files'],selected['max_open_files']))
    c.need(libc.prctl(38,1,0,0,0)==0,'no_new_privs required')
    # Handle all filesystem actions through ABI3, including REFER/TRUNCATE.
    # No path rules are added: only descriptors opened and explicitly passed by
    # the trusted controller remain usable. No root/key/other-role open is possible.
    class Ruleset(ctypes.Structure):_fields_=[('handled_access_fs',ctypes.c_uint64)]
    attr=Ruleset((1<<15)-1);fd=syscall(444,ctypes.byref(attr),ctypes.c_size_t(ctypes.sizeof(attr)),ctypes.c_uint(0))
    try:syscall(446,ctypes.c_int(fd),ctypes.c_uint(0))
    finally:os.close(fd)
    # An actual forbidden open is a startup boundary check, not a qualification
    # of every kernel behavior. The source receives no authentic operand yet.
    try:
        escaped=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    except PermissionError:pass
    else:
        os.close(escaped);c.need(False,'filesystem denial did not take effect')
    return {'schema':'neural081_issuer_restriction_observation_v1','landlock_abi':abi,'path_rules':0,'handled_access_fs':(1<<15)-1,'new_user_namespace':True,'new_network_namespace':True,'no_new_privs':True,'forbidden_root_open_refused':True,'configuration':selected,'deployment_qualification_established_by_this_observation':False}
