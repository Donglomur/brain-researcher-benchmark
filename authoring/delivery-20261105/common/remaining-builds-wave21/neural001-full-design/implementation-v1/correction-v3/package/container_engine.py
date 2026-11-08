"""Concrete fresh-container tool execution; physical/daemon admission is external.

No Docker/process call occurs on import. The only child observer is the captured
no-mutating-signal implementation. Failed/unknown nested custody is never success;
this module does not stop an unrelated PID, container, job or shared service.
"""
import os
import re
from .protocol import require, pin_bytes, check_pin, canonical, Refusal
from .vendor import caller_observer


class ContainerEngine:
    def __init__(self, *, qualification_guard, selection, context, mounts,
                 work_directory, output_directory, code_stager, artifact_store,
                 budget, journal, independent_custody, original_deadline):
        self.guard, self.selection, self.context = qualification_guard, selection, context
        self.mounts = tuple(mounts)
        self.work, self.output = work_directory, output_directory
        self.stage, self.store = code_stager, artifact_store
        self.budget, self.journal, self.custody = budget, journal, independent_custody
        self.original_deadline = original_deadline
        self.ordinal = 0
        require(type(context)is str and re.fullmatch('[a-f0-9]{32}',context),'fresh opaque context UUID hex required')
        require(re.fullmatch(r'[^\s]+@sha256:[0-9a-f]{64}',selection['image']), 'exact immutable image digest')
        require(type(selection['uid'])is int and selection['uid']>0
                and type(selection['gid'])is int and selection['gid']>0,'qualified non-root container identity')
        for key in ('memory_bytes','pids','tmpfs_bytes'):
            require(type(selection[key])is int and selection[key]>0,'positive qualified container limit')
        require(type(selection['cpus'])in (int,float) and 0<selection['cpus']<=256,'qualified CPU ceiling')

    @staticmethod
    def _path(path):
        require(type(path)is str and os.path.isabs(path) and '..' not in path.split('/')
                and not any(x in path for x in ('\x00','\n','\r',',')), 'canonical bounded mount path')
        return path

    def command(self, source, *, action, phase):
        """Pure recipe construction; not a filesystem/container admission claim."""
        require(action in ('action','train','predict') and phase in ('author','training','case'),
                'explicit current phase/action')
        require(set(source)=={'path','pin'},'sealed current source descriptor')
        check_pin(source['pin'])
        self._path(source['path'])
        self._path(self.work);self._path(self.output)
        s=self.selection
        argv=[s['docker_executable'],'run','--rm','--name',self.context,
              '--label','neurobench.task=NEURAL-001','--label','neurobench.context='+self.context,
              '--network','none','--read-only','--ipc','private','--cap-drop','ALL',
              '--security-opt','no-new-privileges','--user',f"{s['uid']}:{s['gid']}",
              '--pids-limit',str(s['pids']),'--cpus',str(s['cpus']),
              '--memory',str(s['memory_bytes']),'--memory-swap',str(s['memory_bytes']),
              '--tmpfs',f"/tmp:rw,noexec,nosuid,size={s['tmpfs_bytes']}",
              '--workdir','/work','--env','PYTHONDONTWRITEBYTECODE=1']
        targets=set()
        for row in (*self.mounts,{'source':source['path'],'target':'/program/current.py','role':'current_source'}):
            require(set(row)=={'source','target','role'},'exact readonly mount fields')
            src=self._path(row['source']); dst=self._path(row['target'])
            require(row['role'] in ('documents','training','query','frozen_state','reference_tools','current_source'),
                    'only explicit scientific/document/source mounts')
            require(dst.startswith(('/docs/','/input/','/state/','/tools/','/program/')),
                    'readonly namespace mount destination')
            require(dst not in targets and not src.endswith(('docker.sock','containerd.sock')),
                    'no duplicate mount/socket capability')
            require(not any(dst.startswith(x+'/') or x.startswith(dst+'/') for x in targets),
                    'no overlapping readonly mounts')
            targets.add(dst)
            argv.extend(['--mount',f'type=bind,src={src},dst={dst},readonly'])
        for src,dst in ((self.work,'/work'),(self.output,'/output')):
            argv.extend(['--mount',f'type=bind,src={src},dst={dst}'])
        argv.extend([s['image'],s['python_executable'],'-I','-B','/program/current.py'])
        if action=='train':
            argv.extend(['train','--training','/input/training.npz','--state-output','/output/state.npz'])
        elif action=='predict':
            argv.extend(['predict','--training','/input/training.npz','--query-metadata','/input/query.json',
                         '--state','/state/state.npz',
                         '--output','/output/prediction.npy'])
            if any(row['target']=='/input/query.npz' for row in self.mounts):
                argv.extend(['--query','/input/query.npz'])
        return argv

    def _execute(self, source, *, action, phase, cutoff):
        self.guard()  # Must precede staging, stat, mount authentication or spawn.
        require(cutoff<self.original_deadline,'phase cutoff inside original study deadline')
        now=self.budget.tick(cutoff)
        cleanup_end=min(self.original_deadline,cutoff+self.selection['cleanup_seconds'])
        require(now<cutoff<cleanup_end,'unchanged bounded normal/cleanup deadlines')
        argv=self.command(source,action=action,phase=phase)
        # Independent daemon and mount observer must bind newly created container
        # identity, image, readonly assets and source before/after its lifecycle.
        admission=self.custody.before_container(self.context,argv,self.mounts,source,
                                                self.work,self.output,now,cutoff,cleanup_end)
        require(admission is True,'independent launch/mount/daemon admission refused')
        token=self.budget.reserve_tool(cutoff,cleanup_end)
        self.ordinal+=1
        self.journal({'kind':'tool_attempt','ordinal':self.ordinal,'context':self.context,
                      'command':argv,'source_pin':source['pin'],'cutoff':cutoff,
                      'cleanup_end':cleanup_end,'original_deadline':self.original_deadline})
        bundle=None
        try:
            bundle=caller_observer.run(argv,cutoff,cleanup_end,self.selection['host_environment'],
                                       self.selection['host_cwd'])
            observed=self.custody.after_container(self.context,bundle,admission)
            require(type(observed)is dict and set(observed)=={'natural_zero','container_absent',
                    'all_nested_resources_closed','readonly_unchanged','usage','peaks','evidence_pin'},
                    'independent complete nested-resource/usage observation required')
            # Close observed accounting BEFORE accepting scientific output.
            self.budget.finish_tool(token,observed['usage'],observed['peaks'])
            token=None
            require(all(observed[k]is True for k in ('natural_zero','container_absent',
                    'all_nested_resources_closed','readonly_unchanged')),'unknown nested custody is failed')
            self.journal({'kind':'tool_closed','context':self.context,'caller':bundle['record'],
                          'nested':observed,'mutating_signal_count':0})
            return {'stdout':bundle['stdout'].decode('utf-8','strict'),
                    'stderr':bundle['stderr'].decode('utf-8','strict'),
                    'observation_pin':observed['evidence_pin'],'usage':observed['usage']}
        except BaseException as error:
            if isinstance(error,caller_observer.ChildFailure):bundle=error.bundle
            if token is not None:self.budget.abandon_tool(token,'failed or unknown nested usage/custody')
            self.journal({'kind':'tool_failed','context':self.context,'error_type':type(error).__name__,
                          'caller':None if bundle is None else bundle['record'],
                          'unknown_survivors_require_separate_inspection':True,
                          'automatic_retry_or_mutating_signal':False})
            raise

    def execute_current_action(self, code, *, context, phase, cutoff):
        self.guard()
        require(context==self.context and type(code)is str and 0<len(code.encode())<=65536,
                'one current context and bounded source')
        source=self.stage(code.encode(),role='current_action_source',context=context)
        return self._execute(source,action='action',phase=phase,cutoff=cutoff)

    def seal_source(self, source, method, *, context, phase):
        self.guard()
        require(context==self.context and type(source)is str and 0<len(source.encode())<=65536,
                'bounded sealed source')
        require(type(method)is dict and len(canonical(method))<=32768,'bounded method metadata')
        return {'program':self.store.put_bytes(source.encode(),'program',{'phase':phase}),
                'method_recipe':self.store.put_bytes(canonical(method),'method_recipe',{'phase':phase})}

    def execute_sealed_program(self, program, *, action, phase, cutoff):
        self.guard()
        body=self.store.read_exact(program,65536)
        require(pin_bytes(body)==program['pin'],'sealed exact source identity')
        source=self.stage(body,role='sealed_program_source',context=self.context)
        return self._execute(source,action=action,phase=phase,cutoff=cutoff)
