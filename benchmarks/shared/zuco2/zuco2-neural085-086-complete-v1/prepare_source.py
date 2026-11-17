"""Future source-selected full original projection, never enabled by build acceptance.
No cleaning/ICA/MARA/Hilbert/FRP substitute is implemented. Native unresolved
operators have structured dispositions even when released means are projected.
The independent outer caller must capture this worker's genuine completion;
its output is not by itself an admissible preparation receipt.
"""
import argparse,time
from pathlib import Path
from zuco.io import *
from zuco.budget import Ledger
from zuco.closure import final_file

def run(selection_path,output):
    selection=decode(read(selection_path,4*1024**2));exact(selection,['schema','scientific_preparation_authorized','budget','source_closure','material','events','bindings','ABI','overlap','event_dispositions','operator_qualification'])
    need(selection['schema']=='zuco2-source-preparation-selection-v1' and selection['scientific_preparation_authorized']is True,'source_preparation_not_authorized');ledger=Ledger(selection['budget']);start=time.process_time()
    def load(k):
        d=selection[k];descriptor(d);return decode(read(d['path'],d['bytes'],d,ledger.guard))
    closure=load('source_closure');materials=load('material');events=load('events');bindings=load('bindings');abi=load('ABI');overlap=load('overlap');dispositions=load('event_dispositions');qualification=load('operator_qualification');need(qualification['source_sha256']==digest(closure) and qualification['abi_sha256']==digest(abi) and qualification['exact_native_bindings_reviewed']is True,'source_preparation_qualification')
    from zuco.constants import PERSONS,CONDITIONS
    need(len(closure['files'])==36 and {(x['person'],x['condition'])for x in closure['files']}=={(p,c)for p in PERSONS for c in CONDITIONS},'full36_preparation')
    from zuco.extract import container_rows
    rows=[]
    for source in closure['files']:
        key=source['person']+':'+source['condition'];rows.extend(container_rows(source,materials,events[key],bindings[key],abi,ledger.guard))
    panel={'schema':'zuco2-panel-v1','source_sha256':digest(closure),'abi_sha256':digest(abi),'rows':rows,'event_dispositions':dispositions}
    from zuco.panel import validate
    validate(panel,closure,overlap,abi);out=path_guard(output);need(not out.exists(),'fresh_source_preparation');ledger.guard();out.mkdir(parents=True);panelpin=write(out/'PANEL.json',panel,ledger)
    from zuco.operators import native_dispositions
    ledger.charge_controller(time.process_time()-start);receipt={'source_sha256':digest(closure),'panel_pin':panelpin,'abi_sha256':digest(abi),'full_36_13302_scope':True,'native_unavailable':native_dispositions(),'scientifically_qualified':False,'requires_independent_original_process_and_operator_receipt':True};final_file(out/'PREPARATION_OUTPUT.json',receipt,ledger,selection['budget']['controller_cpu_reserve']);return receipt
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--selection',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.selection,a.output)
