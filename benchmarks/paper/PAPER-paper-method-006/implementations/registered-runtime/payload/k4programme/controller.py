"""Complete-roster local scientific call composition and independent dispositions.

This is a worker/source composition, not a qualified native deployment. A future
original process owner must provide limits, read-only arms, output capture and
protected validators. Nothing here turns a receipt dictionary into that owner.
"""
from pathlib import Path
from .common import Owner, Budget, Artifacts, Unavailable, require
from .catalog import check_plan, complete_report
from .dispatch import execute


def serialize_result(value, artifacts, prefix='result'):
    """Keep array results separate from ordinary JSON and protected receipts."""
    if value is None or type(value) in (str,int,float,bool): return value
    if isinstance(value,dict):
        return {str(k):serialize_result(v,artifacts,prefix+'-'+str(i))
                for i,(k,v) in enumerate(value.items())}
    if isinstance(value,(list,tuple)):
        return [serialize_result(v,artifacts,prefix+'-'+str(i)) for i,v in enumerate(value)]
    import numpy as np
    import io
    if isinstance(value,np.generic):return serialize_result(value.item(),artifacts,prefix)
    require(type(value) is np.ndarray and not value.dtype.hasobject, 'unserializable-worker-result')
    artifacts.budget.charge('array',value.nbytes+4096)
    local=Owner(); buffer=io.BytesIO();data=None
    try:
        np.save(buffer,value,allow_pickle=False)
        data=buffer.getvalue()
    except BaseException as error:local.catch('array-serialization',error)
    finally:local.close('array-buffer-close',buffer)
    artifacts.owner.relay(local)
    return {'array':artifacts.write(prefix+'.npy',data),
            'dtype':str(value.dtype),'shape':list(value.shape)}


class Programme:
    def __init__(self, catalog, plan, output_root, *, limits):
        self.catalog,self.plan=catalog,plan
        self.jobs,self.coverage,self.order=check_plan(plan,catalog)
        self.owner=Owner();self.results={};self.root=Path(output_root)
        self.values={};self.directories={}
        self.budget=Budget(**limits)
        require(self.root.is_dir() and not self.root.is_symlink()
                and not any(self.root.iterdir()),'fresh-programme-output-root')

    def resolve_inputs(self,job):
        """Resolve only actual successful upstream products, never asserted hashes."""
        from .waveform_chain import validate_waveform_edges
        validate_waveform_edges(job,self.jobs)
        resolved={}
        for role,binding in job['inputs'].items():
            if binding['source']=='external':
                require(set(binding)-{'source'} in ({'pin'},{'pin','shape','dtype'}),
                        'external-input-fields')
                resolved[role]={k:v for k,v in binding.items() if k!='source'}
                continue
            identity=binding['job_id']
            require(identity in job['depends_on'] and identity in self.values,'producer-not-returned')
            value=self.values[identity]
            for part in binding['result_path']:
                require(type(part) in (str,int) and type(part) is not bool,'result-path-component')
                value=value[part]
            if isinstance(value,dict) and set(value)=={'array','dtype','shape'}:
                output=value['array']
                require(output in self.results[identity]['outputs'],'array-not-owned-by-producer')
                resolved[role]={'pin':{'path':str(self.directories[identity]/output['name']),
                                      'bytes':output['bytes'],'sha256':output['sha256']},
                                'shape':value['shape'],'dtype':value['dtype']}
            else:
                resolved[role]={'value':value}
        return resolved

    def run(self):
        """Every planned cell gets a disposition; no retry and no false completion."""
        for ordinal,key in enumerate(self.order):
            job=self.jobs[key]
            blocked=[p for p in job['depends_on']
                     if self.results[p]['status']!='worker-returned-unqualified']
            if blocked:
                self.results[key]={'status':'required-unscorable','reason':{'dependencies':blocked}}
                continue
            if job['status']=='unresolved-original-producer':
                self.results[key]={'status':'required-unscorable','reason':job['missing']}
                continue
            local=Owner();artifacts=None
            try:
                self.budget.charge('operations',1)
                directory=self.root/f'job-{ordinal:06d}'
                directory.mkdir(mode=0o700)
                self.directories[key]=directory
                artifacts=Artifacts(directory,self.budget,local)
                inputs=self.resolve_inputs(job)
                value=execute(job['operation'],inputs,job['parameters'],artifacts)
                serialized=serialize_result(value,artifacts)
                artifacts.json('RESULT.json',serialized)
                self.values[key]=serialized
                self.results[key]={'status':'worker-returned-unqualified',
                                   'outputs':list(artifacts.outputs),'scientific_pass':None}
            except Unavailable as error:
                # Capture the actual occurrence even though its scientific state is unavailable.
                local.catch_or_propagate('job-unavailable',error)
                self.results[key]={'status':'required-unscorable','reason':{'code':error.code,'details':error.details},
                                   'partial_outputs':[] if artifacts is None else list(artifacts.outputs),
                                   'unrecorded_partial_effects_possible':True}
            except BaseException as error:
                # Existing inner-owner occurrences are merged, not counted again.
                local.catch_or_propagate('job-failed',error)
                self.results[key]={'status':'failed','reason':'ordinary scientific/library/IO failure',
                                   'partial_outputs':[] if artifacts is None else list(artifacts.outputs),
                                   'unrecorded_partial_effects_possible':True}
            finally:
                for event in local.events:self.owner.merge(event)
        # Final composition/publication belongs to the same original owner.
        report=None
        try:report=complete_report(self.plan,self.catalog,self.results)
        except BaseException as error:self.owner.catch('whole-report-composition',error)
        if report is None:
            return {'jobs':self.results,'terminal_report_unavailable':True,
                    'scientific_ready':False,'raw_owner':self.owner,
                    'logical_worker_costs':dict(self.budget.used)}
        report['logical_worker_costs']=dict(self.budget.used)
        report['physical_observer_costs']='unknown; separately qualified original observer required'
        report['error_occurrences']=self.owner.describe()
        try:
            terminal=self.root/'terminal';terminal.mkdir(mode=0o700)
            output=Artifacts(terminal,self.budget,self.owner)
            output.json('PROGRAMME_REPORT.json',report)
        except BaseException as error:
            self.owner.catch_or_propagate('terminal-publication',error)
            report['terminal_publication']='failed; partial output may exist'
        report['logical_worker_costs']=dict(self.budget.used)
        report['error_occurrences']=self.owner.describe()
        report['raw_owner']=self.owner
        report['terminal_file_cost_tail']='file is pre-publication snapshot; returned original owner/costs include tail'
        # Return original owner to the actual parent, never serialize it as authority.
        return report
