"""Explicit readonly Docker Desktop mount alias policy; original helper unchanged."""
import sys
from runtime_io import need,ordinary as path

def gate(policy,daemon):
    need(policy in ('identity','darwin_docker_desktop_users_v1'),'selected mount source policy')
    if policy!='identity':
        need(sys.platform=='darwin' and type(daemon)is dict and daemon.get('OperatingSystem')=='Docker Desktop','explicit Darwin and observed Docker Desktop')
    return policy

def admit(info,mounts,policy):
    # The original helper treats bind/volume lists; our separately checked /tmp
    # tmpfs may appear in effective Mounts and is never an alias.
    extras=[x for x in info['Mounts'] if x.get('Type')=='tmpfs']
    need(len(extras)<=1 and all(x.get('Destination')=='/tmp' and x.get('RW') is True for x in extras),'only declared tmpfs')
    view={**info,'Mounts':[x for x in info['Mounts'] if x.get('Type')!='tmpfs']}
    return mount_admission(view,mounts,policy)

def mount_admission(value,mounts,mount_source_policy):
    """Compare requested and effective mount identities without path rewriting.

    The caller may select darwin_docker_desktop_users_v1 only after binding its
    lock, Darwin host and observed Docker Desktop daemon. Identity is default.
    The sole alias in either inspected table is exactly '/host_mnt'+the true
    operator-requested canonical /Users/... path for a readonly bind. No prefix
    stripping, realpath, symlink resolution or
    writable/volume alias is performed. This is inspect-metadata admission, not
    a claim of independent filesystem identity or new native qualification.
    """
    message='Exact mounts; no host writable candidate bind'
    need(type(mount_source_policy)is str and
         mount_source_policy in ('identity','darwin_docker_desktop_users_v1'),message)
    expected={}
    for target,(kind,source,rw)in mounts.items():
        need(type(target)is str and kind in ('bind','volume')and type(rw)is bool,message)
        if kind=='bind':need(str(path(source))==str(source),message)
        expected[target]=(kind,str(source),rw)
    requested=value['HostConfig'].get('Mounts');effective=value.get('Mounts')
    need(type(requested)is list and type(effective)is list and
         len(requested)==len(effective)==len(expected),message)
    request_map={}
    for row in requested:
        need(type(row)is dict and type(row.get('Target'))is str and
             row['Target']not in request_map and type(row.get('Type'))is str and
             type(row.get('Source'))is str,message)
        # Docker's omitted false ReadOnly has precisely the writable meaning;
        # readonly bindings still require an explicit true boolean.
        readonly=row.get('ReadOnly',False)
        need(type(readonly)is bool,message)
        request_map[row['Target']]=(row['Type'],row['Source'],not readonly)
    need(set(request_map)==set(expected),message)
    effective_map={}
    for row in effective:
        need(type(row)is dict and type(row.get('Destination'))is str and
             row['Destination']not in effective_map and type(row.get('Type'))is str and
             type(row.get('RW'))is bool,message)
        effective_map[row['Destination']]=row
    need(set(effective_map)==set(expected),message)
    def source_mapping(observed_source,kind,operator_source,rw):
        need(type(observed_source)is str,message)
        if observed_source==operator_source:return 'identity'
        canonical_users=(operator_source.startswith('/Users/')and
            all(part not in ('','.','..')for part in operator_source.split('/')[1:])and
            not any(char in operator_source for char in ('\x00','\r','\n','\\')))
        need(mount_source_policy=='darwin_docker_desktop_users_v1'and kind=='bind'and
             rw is False and canonical_users and observed_source=='/host_mnt'+operator_source,message)
        return 'host_mnt_prefix'
    observed=[]
    for target in sorted(expected):
        kind,source,rw=expected[target];row=effective_map[target]
        request_kind,request_source,request_rw=request_map[target]
        need(request_kind==kind and request_rw is rw,message)
        request_mapping=source_mapping(request_source,kind,source,rw)
        need(row['Type']==kind and row['RW']is rw,message)
        field='Name'if kind=='volume'else'Source';effective_source=row.get(field)
        mapping=source_mapping(effective_source,kind,source,rw)
        observed.append({'target':target,'type':kind,'requested_source':source,
                         'operator_requested_source':source,'observed_requested_source':request_source,
                         'requested_mapping':request_mapping,
                         'effective_source':effective_source,'effective_source_field':field,
                         'read_only':not rw,'mapping':mapping})
    return {'schema':'thalamus_mount_admission_v1','mount_source_policy':mount_source_policy,
            'mounts':observed}
