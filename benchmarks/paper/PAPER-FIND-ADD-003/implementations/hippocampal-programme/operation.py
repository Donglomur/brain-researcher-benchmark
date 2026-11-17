"""Prospective operation admission; no default scientific panel or resource envelope."""
from pathlib import Path
import math
from core import ROLES,descriptor,need,identity,expected_counts
from staging import validate_files
from transport.contract import RESOURCE_KEYS

ACTIONS=('prepare_originals','prepare_fold','native_attempt','train_model','analytic_prior','evaluate_model','grade','report')


def positive(value,name):
    need(type(value) is int and value>0,'Explicit positive integer '+name)


def pinned_path(value):
    need(type(value) is dict and set(value)=={'path','bytes','sha256'},'Exact external file descriptor')
    need(Path(value['path']).is_absolute(),'Absolute external file path');descriptor({k:value[k] for k in ('bytes','sha256')})


def validate_operation(op):
    keys={'schema','task_id','limits','outer_read_bytes','outer_write_bytes','outer_retained_bytes','outer_cleanup_seconds','host_python','docker','source_manifest','engine_source_pin','controller_grace_seconds','controller_log_bytes','host_memory_bytes','recovery_limits','phase_resources','sources','programs','images','originals','identity_evidence','model_limits','preparation_limits','retention_reservation','runtime_audit','host_setup_seconds','controller_metadata_bytes','host_finish_seconds'}
    need(type(op) is dict and set(op)==keys and op['schema']=='h_operation_v1' and op['task_id']=='PAPER-FIND-ADD-003','Exact complete operation ABI')
    need(set(op['limits'])=={'wall_seconds','read_bytes','write_bytes','retained_bytes'},'Whole-program bounds')
    for k,v in op['limits'].items():positive(v,k)
    for k in ('outer_read_bytes','outer_write_bytes','outer_retained_bytes','outer_cleanup_seconds','controller_grace_seconds','controller_log_bytes','host_memory_bytes'):positive(op[k],k)
    positive(op['controller_metadata_bytes'],'controller_metadata_bytes');need(op['controller_metadata_bytes']<=8388608,'Fixed private entry request ceiling')
    need(op['outer_cleanup_seconds']<op['limits']['wall_seconds'],'Original cleanup time partition')
    for key,outer in [('read_bytes','outer_read_bytes'),('write_bytes','outer_write_bytes'),('retained_bytes','outer_retained_bytes')]:need(op[outer]<op['limits'][key],'Reserved outer source/custody partition '+key)
    need(type(op['host_python']) is dict and set(op['host_python'])=={'path','pin'},'Pinned host interpreter');descriptor(op['host_python']['pin'])
    need(set(op['docker'])=={'binary','binary_pin','socket'},'Explicit local Docker transport');descriptor(op['docker']['binary_pin'])
    for value in (op['host_python']['path'],op['docker']['binary'],op['docker']['socket']):need(type(value) is str and Path(value).is_absolute(),'Absolute installed host dependency')
    pinned_path(op['source_manifest']);descriptor(op['engine_source_pin']);pinned_path(op['identity_evidence']);pinned_path(op['runtime_audit'])
    need(set(op['host_finish_seconds'])==set(ACTIONS),'Every action has an explicit bounded post-capture host interval')
    for k,v in op['host_finish_seconds'].items():positive(v,'host_finish_seconds.'+k)
    need(set(op['host_setup_seconds'])==set(ACTIONS),'Every action has an explicit bounded host staging interval')
    for k,v in op['host_setup_seconds'].items():positive(v,'host_setup_seconds.'+k)
    need(set(op['phase_resources'])==set(ACTIONS),'All complete phase resource profiles')
    for action,r in op['phase_resources'].items():
        need(set(r)==RESOURCE_KEYS,'Complete transport profile '+action)
        for k,v in r.items():positive(v,action+'.'+k)
    need(set(op['recovery_limits'])=={'max_records','max_record_bytes','max_metadata_bytes','max_cli_calls','max_cli_bytes','source_read_bytes','host_write_bytes'},'Independent bounded recovery')
    for k,v in op['recovery_limits'].items():positive(v,k)
    need(set(op['sources'])=={'paper','contract','author','reference','native_reference','runner'},'Exact source exposure families')
    for name,s in op['sources'].items():
        need(set(s)=={'root','files'} and Path(s['root']).is_absolute(),'Exact staged source inventory');validate_files(s['files'])
    need(len(op['sources']['author']['files'])==19,'All nineteen authenticated author files in B/reference exposure')
    need(set(op['programs'])=={'A','B'},'Independently committed candidate programs before numeric views')
    for role,p in op['programs'].items():
        need(set(p)=={'root','files','native_argv','train_argv'},'Complete independent candidate source');validate_files(p['files'])
        for field in ('native_argv','train_argv'):need(type(p[field]) is list and p[field] and all(type(x) is str for x in p[field]) and p[field][0].startswith('/'),'Exact candidate argv')
    need(set(op['images'])=={'A','B','reference','operator'},'All isolated image identities')
    for role,image in op['images'].items():
        need(set(image)=={'image','inventory_sha256','boundary_audit','author_source_absent','operator_source_absent'},'Full image/source audit, not PYTHONPATH isolation')
        descriptor(image['boundary_audit']);descriptor({'bytes':0,'sha256':image['inventory_sha256']})
        need(type(image['image']) is str and image['image'].startswith('sha256:') and len(image['image'])==71,'Immutable installed image')
        if role=='A':need(image['author_source_absent'] is True and image['operator_source_absent'] is True,'A image excludes author and private operator implementation')
    need(type(op['originals']) is dict and set(op['originals'])=={'root','files'},'All original objects, exact closed inventory');validate_files(op['originals']['files'])
    expected={'all23behavior.mat':(29054400,'321192109e2ea9ec9e8095799aadcbf6f8d209be119d4c999dd1b110c3cbbce7'),'rawtrialsstand2torev2_n11.mat':(10720299345,'2ddee31087cd4ee4d6b133e02e05432a27d5fa5ee5beb81915fae65416b69f61'),'rawtrialsstand2torev2_nosmoothnoflooring_n11.mat':(12292854614,'2bf684b9416299e50dfe5c057392444ecc90c9fa6e49fe9fb7a98d1e850f3475')}
    need(op['originals']['files']=={k:{'bytes':v[0],'sha256':v[1]} for k,v in expected.items()},'Exactly all three original selected inputs')
    for name in ('model_limits','preparation_limits','retention_reservation'):need(type(op[name]) is dict and op[name],'Explicit full shape/work/resource policy')
    model=op['model_limits'];need(set(model)=={'max_model_bytes','max_array_bytes','graph_limits','max_training_metadata_bytes','max_training_array_bytes','max_query_metadata_bytes','max_query_array_bytes','roundtrip_atol','roundtrip_rtol'},'Complete typed model/training/query policy')
    for k,v in model.items():
        if k not in ('graph_limits','roundtrip_atol','roundtrip_rtol'):positive(v,k)
    for k in ('roundtrip_atol','roundtrip_rtol'):need(type(model[k]) in (int,float) and math.isfinite(model[k]) and model[k]>=0,'Prospectively fixed finite roundtrip tolerance')
    graph=model['graph_limits'];need(set(graph)=={'max_nodes','max_graph_bytes','max_constant_bytes','max_tensor_elements','max_peak_array_bytes','max_work_units','max_seconds'},'Complete graph policy; local deadline supplied only by trusted caller')
    for k,v in graph.items():
        if k=='max_seconds':need(type(v) in (int,float) and math.isfinite(v) and v>0,'Finite positive per-record elapsed allowance')
        else:positive(v,k)
    need(graph['max_nodes']<=10000,'Accepted bounded graph language')
    prep=op['preparation_limits'];need(set(prep)=={'max_metadata_bytes','max_array_bytes','session_input_bytes','max_grade_index_bytes','grade_limits'},'Complete private preparation/grading policy')
    for k,v in prep.items():
        if k!='grade_limits':positive(v,k)
    need(set(prep['grade_limits'])=={'max_prediction_bytes','max_native_bytes'},'Complete private metric source bounds')
    for k,v in prep['grade_limits'].items():positive(v,k)
    counts=expected_counts();whole_phase_seconds=sum(counts[a]*(op['host_setup_seconds'][a]+op['host_finish_seconds'][a]+sum(op['phase_resources'][a][k] for k in ('setup_seconds','producer_seconds','capture_seconds','cleanup_seconds'))) for a in ACTIONS)
    need(whole_phase_seconds+op['outer_cleanup_seconds']<=op['limits']['wall_seconds'],'Every complete phase envelope plus independent cleanup fits the original operation wall allocation')
    producer_read_upper=sum(counts[a]*op['phase_resources'][a]['source_read_bytes'] for a in ACTIONS);producer_write_upper=sum(counts[a]*op['phase_resources'][a]['host_write_bytes'] for a in ACTIONS)
    need(producer_read_upper<=op['limits']['read_bytes']-op['outer_read_bytes'] and producer_write_upper<=op['limits']['write_bytes']-op['outer_write_bytes'],'Complete producer reservation sum before any phase; host staging additionally charged')
    need(set(op['retention_reservation'])=={'all_model_bytes','model_count','captures_receipts_logs_bytes','preparation_bytes','concurrent_partial_bytes'},'Full set reservation, not one model')
    reservation=op['retention_reservation'];need(reservation['model_count']==9240,'All model slots')
    for k,v in reservation.items():positive(v,k)
    need(reservation['all_model_bytes']>=9240*op['model_limits']['max_model_bytes'],'Reserve every maximum admitted model until private evaluation')
    total=sum(v for k,v in reservation.items() if k!='model_count')
    need(reservation['all_model_bytes']+reservation['captures_receipts_logs_bytes']>=producer_write_upper,'Complete retained producer reservation sum, including every model capture and receipt')
    need(total<=op['limits']['retained_bytes']-op['outer_retained_bytes'],'Complete retention fits before first producer')
    from reservation import derive
    complete=derive(op)
    for k,v in complete['minima'].items():need(reservation[k]>=v,'Full derived reservation component '+k)
    return op


def runtime_binding(op):
    """Audit binds every prospective operation field except its own file pin."""
    return identity({k:v for k,v in op.items() if k!="runtime_audit"})
