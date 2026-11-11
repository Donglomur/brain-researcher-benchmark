"""Exercise preserved original strict collector/scorer against the new wrapper."""
from pathlib import Path
import sys,importlib
from .core import save,write_new,byte_pin,digest,need
from .protocol import PEOPLE,ARMS,ROLES
from .arrays import encode
def reconcile(panel,admitted,complete_grade,destination,budget):
    root=Path(destination);root.mkdir()
    source=Path(__file__).resolve().parents[1]
    original_path=list(sys.path);sys.path.insert(0,str(source/'legacy/public'))
    try:
        module=importlib.import_module('legacy.operator.scorer')
        collector=importlib.import_module('legacy.operator.collect')
        results={}
        for role in ROLES:
            role_dir=root/role;role_dir.mkdir();cases=[];array_bytes=0;case_metadata_bytes=0
            for person in PEOPLE:
                case=role_dir/person;case.mkdir();entries=[]
                for arm in ARMS:
                    name=person+'__'+arm+'.npz'
                    pin=write_new(case/name,encode({'prediction':admitted[(role,person,arm)].reshape(200,17,100)}),budget)
                    array_bytes+=pin['bytes']
                    entries.append({'person':person,'arm':arm,'file':name,**{k:pin[k] for k in ('bytes','sha256')}})
                case_pin=save(case/'case_predictions.json',{'schema':'neural056_case_predictions_v1',
                   'design_sha256':digest(panel.design),'query_image_ids':panel.design['query_image_ids'],'entries':entries},budget)
                case_metadata_bytes+=case_pin['bytes']
                cases.append(case)
            # Reserve the unchanged legacy routines' complete extra logical
            # copy/admission reads, hashes and writes before invoking them.
            # Native/cached OS I/O remains separately observed by the outer group.
            budget.reserve(read=2*array_bytes+case_metadata_bytes+65536,
                           hashed=2*array_bytes,written=array_bytes+65536)
            merged=role_dir/'collected';collector.collect(cases,merged)
            old=module.grade(merged,panel.design,panel.outer_target)
            metadata_bytes=(merged/'predictions.json').stat().st_size
            need(metadata_bytes<=65536,'complete legacy manifest reservation')
            budget.observe(read=2*array_bytes+case_metadata_bytes+metadata_bytes,
                           hashed=2*array_bytes,written=array_bytes+metadata_bytes)
            new=complete_grade['roles'][role]
            for arm in ARMS:
                for person in PEOPLE:
                    a=old['per_person'][arm][person];b=new['participant_coordinate_results'][arm][person]
                    flat=[x for row in a['scoring_correlation'] for x in row]
                    need(len(flat)==1700,'complete original correlation cells')
                    need(all((x is None and y is None) or (x is not None and y is not None and abs(x-y)<=1e-12)
                             for x,y in zip(flat,b['score'])),'original endpoint mismatch')
                    x=a['mean_all1700'];y=b['mean']
                    need((x is None and y is None) or (x is not None and y is not None and abs(x-y)<=1e-12),'original person mean mismatch')
            results[role]=old
        save(root/'LEGACY_RECONCILIATION.json',{'all_four_roles':True,'original_endpoint_agrees':True,
              'native_published_OLS_or_KernelPCA_reproduced':False,'results':results},budget)
        return {'original_endpoint_agrees':True,'roles':list(ROLES),'tolerance':1e-12}
    finally:sys.path[:]=original_path

