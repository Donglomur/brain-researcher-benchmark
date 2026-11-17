"""Exact source joins before any original input or model producer is exposed."""
from core import need
from safe_io import strict
from source_bindings import AUTHOR_FILES,PAPER_FILES
from native.bridge import SOURCE_PINS


def admit(op,budget,cap):
    p=op['source_manifest'];body=budget.read_file(p['path'],{k:p[k] for k in ('bytes','sha256')},cap);manifest=strict(body)
    need(manifest.get('schema')=='h_complete_executable_source_v1','Complete pinned executable source inventory')
    rows=manifest['files'];files={r['path']:{k:r[k] for k in ('bytes','sha256')} for r in rows};need(len(files)==len(rows),'Unique executable member paths')
    need(op['sources']['reference']['files']==files,'Private operator/reference uses exactly the reviewed implementation')
    need(op['sources']['runner']['files']=={name.removeprefix('runner/'):d for name,d in files.items() if name.startswith('runner/')},'Shared public launcher/prior code exactly matches reviewed subset')
    need(op['sources']['contract']['files']=={name.removeprefix('public/'):d for name,d in files.items() if name.startswith('public/')},'Same exact original task and accepted public interface supplement in all roles')
    need(op['sources']['author']['files']==AUTHOR_FILES,'All19 original author files at exact original paths/bytes')
    need(op['sources']['paper']['files']==PAPER_FILES,'Same exact primary paper in every role')
    native={name:{'bytes':v[0],'sha256':v[1]} for name,v in SOURCE_PINS.items()}
    need(op['sources']['native_reference']['files']==native,'Exactly pinned native projection/exporter, no self-chosen reference')
    return {'schema':'h_complete_source_admission_v1','source_manifest':{k:p[k] for k in ('bytes','sha256')},'paper_members':1,'author_members':19,'native_reference_members':len(native),'complete_operator_members':len(files),'image_semantic_exclusion':'Separate pinned independent runtime/image audit required; hashes alone do not establish absence'}
