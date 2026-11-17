"""One selected complete MotorMINT constructor, lifetime and product collection."""
import os,time
from central_common import need,keys,pin,encode,exact_json,capture,absolute,open_dir,cleanup,Publisher
from central_sources import Runtime
from central_compiler import prepare
from central_products import Products

def make_output(path,meter,uid):
    absolute(path);parent,name=path.rsplit('/',1);fds=[];primary=None;created=None;publisher=None
    try:
        fd,identity=open_dir(parent,meter,uid=uid);fds.append(fd)
        meter.charge(open_attempts=1,objects=1);meter.tick()
        os.mkdir(name,0o700,dir_fd=fd)
        created={'path':path,'created':True,'parent_identity':identity}
        os.fsync(fd);meter.tick()
        publisher=Publisher(path,meter,uid)
    except BaseException as error:primary=error
    primary=cleanup(fds,primary)
    if primary is not None:
        if publisher is not None:primary=publisher.close(primary)
        primary.central_output_prefix=created;raise primary
    return publisher

def validate_review(review,review_pin,sources,args):
    keys(review,('schema','task','commands','package','deployment','program','output','clock',
        'central_limits','failure_limits','other_reserve_bytes','maximum_deployment_bytes','maximum_program_bytes'))
    need(review['schema']=='motormint_selected_central_invocation_v1' and review['task']=='PAPER-paper-method-011'
         and review['package']==sources.manifest_pin,'selected complete portable identity')
    need(type(review['commands']) is list and set(review['commands'])<= {'prepare','run'}
         and args['command'] in review['commands'],'explicit whole operation selection')
    need(review['output']==args['output'] and review['program']['path']==args['program']
         and review['deployment']['path']==args['deployment'],'exact original operands')
    need(type(args['other_reserve_bytes']) is int and args['other_reserve_bytes']>=0
         and args['other_reserve_bytes']==review['other_reserve_bytes'],'retain unrelated work reserve')
    need(review['clock']==sources.meter.clock and review['central_limits']==sources.meter.limits,'one original clock/resource ledger')
    return review

def deployment(value,review):
    keys(value,('schema','enabled','uid','python','docker','cgroup_path','child_cgroup_path','gpu_devices',
        'ownership_token','normal_seconds','cleanup_seconds','runtime_output_bytes','runtime_final_reserve_bytes',
        'maximum_metadata_bytes','central_limits','failure_limits','clock','source_lease','qualification'))
    need(value['schema']=='motormint_central_deployment_v1' and value['enabled'] is True,'explicit qualified original deployment')
    need(value['clock']==review['clock'] and value['central_limits']==review['central_limits']
         and value['failure_limits']==review['failure_limits'],'deployment retains original allocations')
    need(value['qualification']=='independently_reviewed_original_runtime_and_all17_gates',
         'unresolved native/method/data gates do not silently become executable')
    keys(value['source_lease'],('root','read_only_exclusive','issuer_receipt_sha256'))
    need(value['source_lease']['read_only_exclusive'] is True and len(value['source_lease']['issuer_receipt_sha256'])==64,
         'explicit original source custody lease; local metadata is not proof of issuer competence')
    need(type(value['uid']) is int and value['uid']==os.getuid(),'selected owner')
    need(type(value['maximum_metadata_bytes']) is int and 1<=value['maximum_metadata_bytes']<=33554432,'bounded original metadata')
    for k in ('normal_seconds','cleanup_seconds','runtime_output_bytes','runtime_final_reserve_bytes'):
        need(type(value[k]) is int and value[k]>0,'positive selected finite '+k)
    need(value['runtime_final_reserve_bytes']<value['runtime_output_bytes'] and value['cleanup_seconds']<=60,'finite final reserve and cleanup')
    return value

class CompleteInvocation:
    def __init__(self,sources,runtime,template,dep,review,review_pin,publisher):
        self.sources=sources;self.runtime=runtime;self.deployment=dep;self.publisher=publisher
        self.review=review;self.outer=None;self.collected=None;self.started=False;self.runtime_output_created=False
        self.prepared=prepare(sources,runtime,template,dep,review,review_pin,publisher)
    def run(self):
        need(not self.started and 'run' in self.review['commands'],'one complete lifetime selected, no retry')
        self.started=True
        record=self.prepared['request_descriptor']
        raw,_=capture(record['path'],record['pin'],self.sources.meter,maximum=33554432)
        need(exact_json(raw,33554432)==self.prepared['request'],'actual produced request reopens identically')
        # The original supervisor requires its output root empty. Constructor
        # metadata remains in the separate parent directory.
        parent=self.publisher.fd
        self.sources.meter.charge(open_attempts=1,objects=1);self.sources.meter.tick()
        os.mkdir('runtime-output',0o700,dir_fd=parent);self.runtime_output_created=True;os.fsync(parent)
        self.outer=self.runtime.load('mintbench.supervisor').launch(
            self.prepared['specification'],self.prepared['specification_sha256'],
            selected_clock=self.prepared['selected_clock'])
        self.sources.meter.tick('outer')
        return self.outer
    def collect(self):self.collected=Products(self);return self.collected
    def reference(self):
        need(self.collected is not None,'one complete original invocation first');return self.collected.reference()
    def candidate(self):
        need(self.collected is not None,'one complete original invocation first');return self.collected.candidate()
    def grade(self):
        need(self.collected is not None,'original protected assessments first');return self.collected.grade()
    def report(self):
        need(self.collected is not None,'retained original reports first');return self.collected.report()

def execute(sources,arguments,review,review_pin,*,failure_meter):
    validate_review(review,review_pin,sources,arguments)
    meter=sources.meter;publisher=None;runtime=None;invocation=None;primary=None
    sensor=None;sensor_started=False;measured=None;measurement_failure=None;result=None;cleanup_failures=[]
    need(failure_meter.limits==review['failure_limits'] and failure_meter.clock==review['clock'],'separate original failure reserve')
    try:
        d=review['deployment'];keys(d,('path','pin'))
        raw,_=capture(d['path'],d['pin'],meter,maximum=review['maximum_deployment_bytes'])
        dep=exact_json(raw,review['maximum_deployment_bytes'])
        need(dep.get('enabled') is True,'deployment remains unconfigured; no programme/input/native read')
        dep=deployment(dep,review)
        need(dep['source_lease']['root']==sources.root,'lease covers actual installed source root')
        runtime=Runtime(sources)
        if arguments['command']=='run':
            sensor=runtime.load('mintbench.observer').CgroupObserver(dep['cgroup_path'],dep['gpu_devices'])
            sensor.begin('central_complete_programme',review['clock']['origin_ns']/1e9,review['clock']['scientific_ns']/1e9)
            sensor_started=True
        p=review['program'];keys(p,('path','pin'))
        raw,_=capture(p['path'],p['pin'],meter,maximum=review['maximum_program_bytes'],uid=dep['uid'])
        meter.charge(metadata_bytes=65*len(raw));template=exact_json(raw,review['maximum_program_bytes'])
        publisher=make_output(arguments['output'],meter,dep['uid'])
        invocation=CompleteInvocation(sources,runtime,template,dep,review,review_pin,publisher)
        if arguments['command']=='prepare':
            result={'schema':'motormint_central_preparation_v1','request':invocation.prepared['request_descriptor'],
                'outer_specification':invocation.prepared['specification_descriptor'],
                'case_count':invocation.prepared['case_count'],'pair_count':invocation.prepared['pair_count'],
                'all17_modules_validated':True,'operation':'complete invocation metadata construction',
                'scientific_execution':False,'qualified':False}
        else:
            invocation.run();invocation.collect();products={}
            for name,body in [('reference',invocation.reference()),('candidate',invocation.candidate()),
                              ('grade',invocation.grade()),('report',invocation.report())]:
                products[name]=publisher.put(name.upper()+'_PRODUCT_VIEW.json',body,
                    maximum=dep['maximum_metadata_bytes'],phase='outer')
            result={'schema':'motormint_central_complete_v1','outer':invocation.outer,
                'prepared_request':invocation.prepared['request_descriptor'],'products':products,
                'scope':sources.manifest['scope'],'source':sources.manifest_pin,
                'complete_observed_artifact_coverage':invocation.collected.complete,
                'scientific_execution':'original selected whole campaign attempted','qualified':False}
        # Actual complete source closure is reread after all constructor/runtime
        # work. This complements, rather than proves, the external immutable lease.
        for name,expected in sources.manifest['files'].items():
            capture(sources.root+'/'+name,expected,meter,maximum=1048576,phase='outer')
        meter.tick('outer')
    except BaseException as error:primary=error
    if sensor_started:
        try:measured=sensor.finish('central_complete_programme')
        except BaseException as error:
            measurement_failure=type(error).__name__+': '+str(error)[:300]
            if primary is None:primary=error
            else:primary.add_note('Inclusive central measurement: '+measurement_failure)
    if runtime is not None:
        try:runtime.close()
        except BaseException as error:
            cleanup_failures.append({'operation':'captured_runtime_close','reason':type(error).__name__+': '+str(error)[:300]})
            if primary is None:primary=error
            else:primary.add_note('Captured runtime namespace cleanup: '+type(error).__name__)
    if publisher is not None:primary=publisher.close(primary)
    if primary is None:
        try:meter.tick('outer')
        except BaseException as error:primary=error
    if primary is not None:
        prefix={'schema':'motormint_central_failure_prefix_v1','reason':type(primary).__name__+': '+str(primary)[:1000],
            'source':sources.manifest_pin,'review':review_pin,'meter':meter.snapshot(),
            'owned_output':getattr(primary,'central_output_prefix',None) if publisher is None else
                {'path':publisher.path,'created':True,'identity':publisher.identity,'closed':publisher.closed},
            'published':[] if publisher is None else publisher.records,
            'prepared':None if invocation is None else invocation.prepared['request_descriptor'],
            'outer':None if invocation is None else invocation.outer,
            'runtime_output_created':False if invocation is None else invocation.runtime_output_created,'inclusive_cost':measured,
            'measurement_failure':measurement_failure,'cleanup_failures':cleanup_failures+getattr(primary,'secondary',[]),'qualified':False}
        primary.central_failure=prefix
        # The real CLI owns retained diagnostic delivery; this exact prefix is
        # serialized there, not left accessible only on a live exception.
        raise primary
    result['inclusive_central_cost']=measured
    result['cost_boundary']='Starts before complete invocation construction and ends after original runtime, collection, product publication and final source recheck. Initial trusted source/deployment bootstrap and terminal receipt/namespace/FD-close tail are separately logical-custody work, not measured zero.'
    result['nested_original_outer_and_stage_counters_are_attribution_only']=True
    result['source_meter']=meter.snapshot()
    return result

