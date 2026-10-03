"""Fixed oracle closure; no arbitrary reader or code-path override."""
from pathlib import Path
import json
import os
import code_guard as guard

MODULE_PINS={'source_io':'b86e0c2af5ceffdde9aab1554f1df77bc1630b1c98a9f0333fe5b2140087d9ab','information_kernel':'eea1e01383865ca76bb11e94abe4edaf2a3d7dd1bed626f5ecc59ed56110127b','source_reader':'017285f01ad3d619c9bb5f1d43b836fc076bc89f1d12041c0499bbcce2d8bfa1','writer_v2':'ce9573db359e04d2e18177d5483ac517a1030fe4de1170090b8b5462e70c412e'}
DOCUMENT_PINS={
    'source':('source_manifest.json','0bc1ef69627c18177f8a15c76bd8dbe003a6bdaf75ba33a9e0aaa5be652ab722'),
    'method':('method_contract.json','c39f977f8a6d5c179107693d41c5312d37c00ce03a0ea2eebd0d00e3c4aa858a'),
    'schema':('output_schema.json','2a0ade879084d8e23b23fe62698718d048c663b414d1a36adf010f721b5e779b')}
PUBLIC_PATHS={key:'/app/'+spec[0] for key,spec in DOCUMENT_PINS.items()}

def main():
    context=guard.load_closure(Path(__file__).parent,MODULE_PINS,DOCUMENT_PINS,PUBLIC_PATHS)
    root='/app/data/ratplace';output=os.environ.get('OUTPUT_DIR','/app/output')
    out=guard.disjoint_output(output,root,Path(__file__).parent,PUBLIC_PATHS.values())
    guard.need(not os.path.lexists(out),'output_exists')
    try:
        context['modules']['writer_v2'].run(root,Path(__file__).parent,out)
        guard.recheck(context)
    except BaseException as error:
        if not os.path.lexists(out):out.mkdir(parents=True,exist_ok=False)
        if out.is_dir() and not os.path.lexists(out/'failure_report.json'):
            with (out/'failure_report.json').open('x') as f:
                json.dump({'status':'failed_precondition','error_type':type(error).__name__},f)
        raise
