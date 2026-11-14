"""Shared pure clean-build specification; never dispatches Docker."""
import re
from pathlib import Path

def need(ok,code):
    if not ok:raise ValueError(code)

def make_plan(staging, owner_root, name, fixed, setup_sha):
    need(re.fullmatch('nider-clean-[a-z0-9-]{1,40}',name) is not None,'owned_build_name')
    need(staging['schema']=='nider_portable_dependency_staging_v1' and staging['setup_lock_sha256']==setup_sha and
         staging['archive_count']==82 and staging['input_scope']=='only_locked_dependencies_and_installers','staging_build_join')
    need(staging['files'] == fixed['expected_staging_files'] and staging['archive_body_read_bytes'] == fixed['R_archive_bytes'] + fixed['OS_archive_bytes'], 'complete_locked_staging_identity')
    root=Path(owner_root);need(root.is_absolute() and '..' not in root.parts,'build_owner_root')
    argv=['docker','create','--pull=never','--name',name,'--platform=linux/arm64','--network=none',
          '--label','nider.build_owner='+name,'--cpus=2','--memory=6g','--memory-swap=6g','--pids-limit=256','--log-driver=none',
          '--mount','type=bind,src='+staging['root']+',dst=/provision,readonly',
          '--workdir=/provision','--entrypoint=/bin/sh']
    env={'R_LIBS_SITE':'/opt/nider/library','R_LIBS_USER':'/nonexistent',
         'RENV_CONFIG_AUTOLOADER_ENABLED':'FALSE','R_PROFILE_USER':'/dev/null','R_ENVIRON_USER':'/dev/null',
         'MAKEFLAGS':'-j2','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1',
         'STRINGI_DISABLE_ICU_BUNDLE':'1','LANG':'C.UTF-8','LC_ALL':'C.UTF-8'}
    for key,value in env.items():argv+=['--env',key+'='+value]
    argv += [fixed['base'],'/provision/offline_install.sh']
    return {'schema':'nider_clean_offline_build_plan_v1','setup_lock_sha256':setup_sha,'base':fixed['base'],
            'platform':'linux/arm64','network':'none','input_scope':'only_locked_dependencies_and_installers',
            'acquisition_selected':False,'candidate_inputs_mounted':[],'staging':staging,'owner_root':str(root),
            'create_argv':argv,'start_argv':['docker','start','-a',name],
            'commit_argv':['docker','commit','--change','LABEL nider.setup_lock='+setup_sha,
                           '--change','LABEL nider.build_kind=clean-offline-dependencies-v2-inert-default',
                           '--change','ENTRYPOINT ["/bin/false"]','--change','CMD []','--change','USER 65534:65534',name],
            'owned_name':name,'active_seconds':4500,'cleanup_seconds':120,'outer_seconds':5400,
            'maximum_attempts':1,'maximum_new_disk_bytes':8589934592,'maximum_private_log_bytes':16777216,
            'execution_selected':False,'failure_policy':'Preserve exact attempt; no online fallback or automatic retry.'}

