"""One closed NEURAL-017 native-table adapter for the unchanged Executor rows."""
import copy
from collections import Counter
from collections.abc import MutableMapping
from .contracts import closed, need


class FixedNativeJobs(MutableMapping):
    """Immutable recipe plus isolated, owned state only for actually used jobs."""
    def __init__(self,runtime):
        from .factored_runtime import FactoredRuntime
        need(type(runtime)is FactoredRuntime,'one source-owned factored runtime type')
        from .operator_wire import identity
        self.runtime=runtime;self.roster=runtime.roster;self.cache={};self.replacements=set();self.runtime_sha256=runtime.wire_identity['sha256']
    def __len__(self):return len(self.roster)
    def __iter__(self):return iter(self.roster)
    def __contains__(self,job):
        try:self.roster.ordinal(job);return True
        except (ValueError,KeyError,TypeError):return False
    def __getitem__(self,job):
        if job not in self.cache:
            need(job in self,'no foreign native job')
            row=self.runtime.lookup(job)
            need(row['job']==job,'exact source-derived native job lookup')
            self.cache[job]=row['native_job']
        return self.cache[job]
    def __setitem__(self,job,value):
        need(job in self and job not in self.replacements,'one replacement of an original native invocation')
        original=self.runtime.lookup(job)['native_job']
        need(type(value)is dict,'exact concrete native row')
        if 'tool_variants' in original:
            need(any(value==variant for variant in original['tool_variants'].values()),
                 'only an exact original selected tool variant')
        else:
            need(original['role']=='source_syntax','only source checker may append a dynamic input')
            base=copy.deepcopy(value)
            need(len(base['input_manifests'])==len(original['input_manifests'])+1 and
                 len(base['sandbox']['mounts'])==len(original['sandbox']['mounts'])+1,
                 'one checker source manifest and mount')
            pin=base['input_manifests'].pop();mount=base['sandbox']['mounts'].pop()
            from .contracts import descriptor
            descriptor(pin);closed(mount,{'host','guest','access','role','manifest','member'})
            policy=original['dynamic_input_policy']
            need(pin['path']==policy['manifest_path'] and mount['manifest']==pin and
                 mount['role']=='authoring_source' and mount['access']=='ro' and
                 mount['guest']=='/inputs/'+mount['member'] and
                 mount['host']==self.runtime._geometry()['store_root']+'/'+mount['member'],
                 'only original source-checker exact read-only candidate mount')
            need(base==original,'all other original checker operands unchanged')
        self.cache[job]=copy.deepcopy(value);self.replacements.add(job)
    def __delitem__(self,job):raise ValueError('cannot delete an original native invocation')
    def original_parent(self,job):return self.roster.row(self.roster.ordinal(job))['parent_group']
    def census(self):return self.roster.census()


def select_native_jobs(selected,store):
    """Retain the exact expanded dictionary route; no general resolver protocol."""
    if type(selected)is dict and selected.get('schema')!='NLB017_factored_native_jobs_v1':
        return copy.deepcopy(selected)
    from .factored_runtime import FactoredRuntime
    if type(selected)is FactoredRuntime:return FixedNativeJobs(selected)
    if type(selected)is dict and selected.get('schema')=='NLB017_factored_native_jobs_v1':
        return FixedNativeJobs(FactoredRuntime.from_selected(store,selected))
    need(type(selected)is dict,'expanded native selection is an exact dictionary')
    return copy.deepcopy(selected)


def native_census(selected):
    if type(selected)is FixedNativeJobs:return selected.census(),None
    parents={job:row['parent_group']for job,row in selected.items()}
    return dict(Counter(parents.values())),parents


def worker_context(selected,job,native):
    if type(selected)is dict and selected.get('schema')=='NLB017_factored_worker_contexts_v1':
        closed(selected,{'schema','native_jobs_sha256','assessment_declared_inputs'})
        need(type(native)is FixedNativeJobs,'factored context requires the exact original native table')
        need(selected['native_jobs_sha256']==native.runtime_sha256,'same frozen native-table identity')
        row=native.runtime.lookup(job)['worker_context']
        if job=='assessment/grade':row['declared_inputs']=copy.deepcopy(selected['assessment_declared_inputs'])
        return row
    return selected[job]
