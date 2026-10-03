"""Fixed private closure. No I/O on import; final pins are bound after review."""
from pathlib import Path
import os
import code_guard as guard

MODULE_PINS={'source_io':'b86e0c2af5ceffdde9aab1554f1df77bc1630b1c98a9f0333fe5b2140087d9ab','information_kernel':'eea1e01383865ca76bb11e94abe4edaf2a3d7dd1bed626f5ecc59ed56110127b','artifact_reader':'0175be0891d2c16a832f2a2313ab300c157d2117f04fd1ff1a502dd14888624e',
             'source_reference':'ebe72e251c96c519e148cc3c6c6837b651d8e30e4c0435260b356c89703ea4ea','proof_v2':'020796d4a5c1db56fb9eac744d879495152a6128e4c00ca3a0657ed1f65beba5'}
DOCUMENT_PINS={
    'source':('source_manifest.json','0bc1ef69627c18177f8a15c76bd8dbe003a6bdaf75ba33a9e0aaa5be652ab722'),
    'method':('method_contract.json','c39f977f8a6d5c179107693d41c5312d37c00ce03a0ea2eebd0d00e3c4aa858a'),
    'schema':('output_schema.json','2a0ade879084d8e23b23fe62698718d048c663b414d1a36adf010f721b5e779b')}
PUBLIC_PATHS={key:'/app/'+spec[0] for key,spec in DOCUMENT_PINS.items()}

def validate(output=None):
    context=guard.load_closure(Path(__file__).parent,MODULE_PINS,DOCUMENT_PINS,PUBLIC_PATHS)
    modules=context['modules']
    root='/app/data/ratplace'
    out=output if output is not None else os.environ.get('OUTPUT_DIR','/app/output')
    guard.disjoint_output(out,root,Path(__file__).parent,PUBLIC_PATHS.values())
    reference=modules['source_reference'].reconstruct(root,Path(__file__).parent)
    result=modules['proof_v2'].validate_output_directory(out,reference)
    # Bind unchanged private code and public documents after reconstruction/replay.
    guard.recheck(context)
    return result
