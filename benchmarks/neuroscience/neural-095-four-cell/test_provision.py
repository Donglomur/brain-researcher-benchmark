"""Invented adapter controls. Never opens the original NWB or accepted packet."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types

HERE = Path(__file__).absolute().parent
spec = importlib.util.spec_from_file_location('_portable_provision_tested', HERE / 'provision.py')
provision = importlib.util.module_from_spec(spec); spec.loader.exec_module(provision)

# This explicitly invented converter tests adapter control flow, not neuroscience.
FAKE_CORE = '''import json
from pathlib import Path
import numpy as np
def create(out):
    out=Path(out); out.mkdir(); (out/'public').mkdir(); (out/'private').mkdir()
    for name,n,start in [('train',748,0),('query',258,748)]:
        values={'case_id':np.array(['dmfc-'+str(i).zfill(6) for i in range(start,start+n)],dtype='U11'),
          'counts':np.zeros((n,4,40),dtype=np.uint32),'condition':np.arange(n,dtype=np.int64)%40,
          'context':(np.arange(n,dtype=np.int64)%40)//5,'nominal_ts_ms':np.full(n,800.,dtype=np.float64),
          'clock_seconds':np.arange(n,dtype=np.float64)}
        if name=='train': values.update(tp_ms=np.full(n,805.,dtype=np.float64),fold=np.arange(n,dtype=np.int64)%5)
        np.savez(out/'public'/ (name+'.npz'),**values)
        if name=='query':
            np.savez(out/'private/query_targets.npz',case_id=values['case_id'],tp_ms=np.full(n,805.),condition=values['condition'],context=values['context'])
            (out/'public_identity.json').write_text(json.dumps({'schema_version':1,'case_id':values['case_id'].tolist()}))
    common=['case_id','condition','context','nominal_ts_ms','clock_seconds','counts']
    (out/'public/schema.json').write_text(json.dumps({'train_n':748,'query_n':258,'public_keys':{'train':common+['tp_ms','fold'],'query':common}}))
    (out/'public/units.json').write_text('{"invented":true}')
    (out/'private/selection_lock.json').write_text('{"invented":true}')
    (out/'conversion_receipt.json').write_text('{"invented":true}')
'''
FAKE_CONVERTER = '''import argparse
from pathlib import Path
import core
def main():
    p=argparse.ArgumentParser();p.add_argument('--source');p.add_argument('--out');a=p.parse_args()
    core.create(a.out)
    # CHANGE
'''


def clear_modules():
    for name in ('core', '_dmfc_exact_converter', '_dmfc_exact_view_projection'):
        sys.modules.pop(name, None)


def main():
    results = []
    original_support = provision.SUPPORT
    original_pins = provision.SUPPORT_PINS
    with tempfile.TemporaryDirectory(prefix='dmfc-portable-invented-') as directory:
        root = Path(directory).resolve(); support = root / 'support'; support.mkdir()
        fake = types.ModuleType('_fake_dmfc_fixture'); exec(FAKE_CORE, fake.__dict__)
        base = root / 'expected-packet'; fake.create(base)
        project_source = (original_support / 'project.py').read_bytes()
        project = types.ModuleType('_invented_project'); exec(project_source, project.__dict__)
        original = {n:(base/'public'/n).read_bytes()for n in ('train.npz','query.npz','schema.json','units.json')}
        contract = b'{"invented":true}'
        views = provision.project_views(project, original, contract)
        assert len(views)==10 and views['neural/train.npz']==original['train.npz']
        train,_=project.members(original['train.npz'],project.TRAIN|{'counts'},748)
        cue,_=project.members(views['cue_only/train.npz'],project.TRAIN,748)
        assert 'counts' not in cue and all(cue[k]==train[k]for k in project.TRAIN)
        results.append('exact common NPY bytes and absent cue counts; neural archive unchanged')
        source=root/'invented.nwb';source.write_bytes(b'explicitly invented; not HDF5')
        base_names=['public/train.npz','public/query.npz','public/schema.json','public/units.json',
                    'public_identity.json','private/query_targets.npz','private/selection_lock.json']
        references={name:root/name for name in ('reference_grade.json','reference_commit.json','reference_audit.json')}
        for path in references.values():path.write_bytes(b'{"invented":true}')
        expected={'source':provision.pin(source.read_bytes()),'base_packet':{n:provision.pin((base/n).read_bytes())for n in base_names},
                  'views':{n:provision.pin(b)for n,b in views.items()},'references':{n:provision.pin(p.read_bytes())for n,p in references.items()}}
        bodies={'core.py':FAKE_CORE.encode(),'convert.py':FAKE_CONVERTER.encode(),'project.py':project_source,
                'contract.json':contract,'expected.json':json.dumps(expected).encode()}
        for name,body in bodies.items():(support/name).write_bytes(body)
        provision.SUPPORT=support
        def repin():
            provision.SUPPORT_PINS={n:(p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest())for n in bodies for p in [support/n]}
        repin(); clear_modules()
        output=root/'complete'; report=provision.provision(source,output,references)
        assert report['status']=='complete_exact_packet_and_view_parity' and len(list(output.rglob('*.*')))==25
        assert 'CC BY 4.0' in (output/'DATA_NOTICE.md').read_text()
        assert all((output/'evaluator'/n).read_bytes()==p.read_bytes()for n,p in references.items())
        results.append('whole invented17-artifact projection plus5evaluator operands completes without fits')
        clear_modules()
        references['reference_grade.json'].write_bytes(b'changed')
        try:provision.provision(source,root/'bad-reference',references)
        except ValueError:pass
        else:raise AssertionError('reference substitution')
        assert not(root/'bad-reference').exists()
        results.append('wrong reference identity refuses before conversion/output creation')
        references['reference_grade.json'].write_bytes(b'{"invented":true}')
        for name,change in [('source-mutated',"Path(a.source).write_bytes(b'changed source')"),
                            ('base-mutated',"(Path(a.out)/'public/units.json').write_bytes(b'changed units')")]:
            (support/'convert.py').write_text(FAKE_CONVERTER.replace('# CHANGE',change));repin();clear_modules()
            try:provision.provision(source,root/name,references)
            except ValueError:pass
            else:raise AssertionError(name)
            assert not(root/name/'PROVISIONING_RECEIPT.json').exists() and not(root/name/'views').exists()
            results.append(name+' refuses before view/evaluator release')
            source.write_bytes(b'explicitly invented; not HDF5')
        clear_modules(); (support/'convert.py').write_text(FAKE_CONVERTER);repin()
        try:provision.provision(source,output,references)
        except ValueError:pass
        else:raise AssertionError('overwrite')
        results.append('existing complete output is not overwritten or reused')
        provision.SUPPORT=original_support;provision.SUPPORT_PINS=original_pins;clear_modules()
    print(json.dumps({'status':'invented_provisioning_adapter_controls_passed','checks':results,
                      'original_payload_read':False,'real_converter_executed':False,'model_fits':0},indent=2))


if __name__=='__main__':
    sys.dont_write_bytecode=True
    main()
