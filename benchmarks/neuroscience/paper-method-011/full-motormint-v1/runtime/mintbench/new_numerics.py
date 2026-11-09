"""Frozen independent extension comparison; old banks remain unchanged."""
import hashlib,importlib.util
from pathlib import Path
from .validation import decode,encoded,need,digest,close_numbers


def evaluate(kind,payload,*,maximum_bytes):
    root=Path(__file__).resolve().parent.parent
    bindings=decode((root/'NEW_BANK_BINDINGS.json').read_bytes())
    raw=encoded(payload);need(len(raw)<=maximum_bytes,'selected new numerical ceiling')
    values=[];failures=[]
    for pin in bindings['banks']:
        path=root/pin['path'];body=path.read_bytes()
        need(len(body)==pin['bytes'] and hashlib.sha256(body).hexdigest()==pin['sha256'],'frozen independent new bank')
        name='mintbench.new_numerics_a' if pin['path'].startswith('mintbench/') else 'motormint_new_bank_b'
        spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);exec(compile(body,str(path),'exec',dont_inherit=True),module.__dict__)
        independent=decode(raw)
        try:values.append(module.evaluate(kind,independent));failures.append(None)
        except ValueError as error:values.append(None);failures.append(str(error))
        need(encoded(independent)==raw,'new numerical inputs immutable')
    if any(failures):
        need(all(failures),'independent new bank validity disagreement')
        raise ValueError('invalid new numerical input: '+'; '.join(failures))
    close_numbers(values[0],values[1])
    return {'value':values[0],'bank_agreement':True,'payload_sha256':digest(payload),'historical_equivalence':False}
