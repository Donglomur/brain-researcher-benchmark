"""Actual retained-author-class adapter for five original comparator cohorts.

Scientific class bodies are not rewritten into a weak substitute. The adapter
selects exact pinned import/function/class/constant AST nodes, redirects only
explicit checkpoint path literals to admitted state capabilities, and supplies
whole original loaders to the actual Lightning training methods. Any missing
node, source global, checkpoint, environment ABI or recipe refuses qualification.
No author main script, data downloader or test-validation loop is executed.
"""
import ast,hashlib,sys,types
from pathlib import Path
from .protocol import need,fields,digest,identity,Refusal

WRAPPERS={
 'BENDR':{'BCIC-2A':'finetune_BENDR_BCIC2A.py','BCIC-2B':'finetune_BENDR_BCIC2B.py','Sleep-EDFx':'finetune_BENDR_SleepEDF.py','KaggleERN':'finetune_BENDR_KaggleERN.py','PhysioP300':'finetune_BENDR_PhysioP300.py'},
 'BIOT':{'BCIC-2A':'linear_probe_BIOT_BCIC2A.py','BCIC-2B':'linear_probe_BIOT_BCIC2B.py','Sleep-EDFx':'finetune_BIOT_SleepEDF.py','KaggleERN':'linear_probe_BIOT_KaggleERN.py','PhysioP300':'linear_probe_BIOT_PhysioP300.py'},
 'LaBraM':{'BCIC-2A':'linear_probe_LaBraM_BCIC2A.py','BCIC-2B':'linear_probe_LaBraM_BCIC2B.py','Sleep-EDFx':'finetune_LaBraM_SleepEDF.py','KaggleERN':'linear_probe_LaBraM_KaggleERN.py','PhysioP300':'linear_probe_LaBraM_PhysioP300.py'},
 'EEGPT':{'BCIC-2A':'linear_probe_EEGPT_BCIC2A.py','BCIC-2B':'linear_probe_EEGPT_BCIC2B.py','Sleep-EDFx':'finetune_EEGPT_SleepEDF.py','KaggleERN':'linear_probe_EEGPT_KaggleERN.py','PhysioP300':'linear_probe_EEGPT_PhysioP300.py'}}


def build_original_class(author_root,method,dataset,recipe):
    fields(recipe,('source_sha256','selected_nodes','class_name','checkpoint_literal_bindings','qualified_globals','constructor_kwargs','qualification'),'complete original class/source binding')
    need(method in WRAPPERS and dataset in WRAPPERS[method],'actual retained original comparator source; absent Temple/EEGNet producers are not invented')
    path=Path(author_root)/'downstream'/WRAPPERS[method][dataset];raw=path.read_bytes();need(hashlib.sha256(raw).hexdigest()==recipe['source_sha256'],'exact retained original source body');digest(recipe['qualification']);text=raw.decode('utf8');tree=ast.parse(text);selected=[]
    need(recipe['selected_nodes'] and len({r['index'] for r in recipe['selected_nodes']})==len(recipe['selected_nodes']),'complete selected original module dependency nodes')
    for row in recipe['selected_nodes']:
        fields(row,('index','sha256'),'exact original node');node=tree.body[row['index']];body=ast.get_source_segment(text,node).encode('utf8');need(hashlib.sha256(body).hexdigest()==row['sha256'],'same actual original node body')
        need(isinstance(node,(ast.Import,ast.ImportFrom,ast.FunctionDef,ast.ClassDef,ast.Assign,ast.AnnAssign)),'no original module-level trainer/data loop')
        if isinstance(node,(ast.Assign,ast.AnnAssign)):
            # Constants must be literal. Configuration expressions with native
            # reads or loaders cannot enter source-only class extraction.
            ast.literal_eval(node.value)
        selected.append(node)
    bindings=recipe['checkpoint_literal_bindings'];need(all(type(k) is str and k and type(v) is str and v.startswith('/state/') for k,v in bindings.items()),'only explicit readonly checkpoint capability literal redirects')
    observed={k:0 for k in bindings}
    class Redirect(ast.NodeTransformer):
        def visit_Constant(self,node):
            if type(node.value) is str and node.value in bindings:observed[node.value]+=1;return ast.copy_location(ast.Constant(bindings[node.value]),node)
            return node
    chosen=Redirect().visit(ast.Module(body=selected,type_ignores=[]));ast.fix_missing_locations(chosen);need(all(observed.values()),'every checkpoint redirect matches actual retained source')
    name='_eegpt_original_'+recipe['source_sha256'];module=types.ModuleType(name);module.__file__=str(path);sys.modules[name]=module
    # Values here are selected source/recipe constants, never arbitrary caller
    # callbacks or imported objects. Exact numerical recipe qualification binds
    # them before outcomes and distinguishes H from corrected P selection.
    for key,value in recipe['qualified_globals'].items():need(type(key) is str and not key.startswith('__') and type(value) in (str,int,float,bool,list,dict,type(None)),'plain original qualified globals');module.__dict__[key]=value
    sys.path.insert(0,str(Path(author_root)/'downstream'))
    try:exec(compile(chosen,str(path),'exec'),module.__dict__)
    finally:sys.path.pop(0)
    cls=module.__dict__.get(recipe['class_name']);need(isinstance(cls,type),'actual selected original model class');return cls(**recipe['constructor_kwargs']),{'original_source':recipe['source_sha256'],'selected_node_pins':recipe['selected_nodes'],'checkpoint_redirect_counts':observed,'class_name':recipe['class_name'],'qualification':recipe['qualification'],'scientific_class_body_rewritten':False}


def fit_original(model,train_loader,validation_loader,recipe,output):
    import torch
    import pytorch_lightning as pl
    fields(recipe,('epochs','precision','accelerator','devices','monitor','monitor_mode','seed','gradient_clip_val','qualification'),'actual original native training recipe');digest(recipe['qualification'])
    need(recipe['monitor_mode']=='max' and recipe['devices']==1,'explicit qualified original comparator selection policy');need(type(recipe['seed']) is int,'original seed resolved before actual model initialization, not reset after construction')
    class AllSelectionRecords(pl.Callback):
        def __init__(self):self.records=[]
        def on_validation_end(self,trainer,pl_module):
            if trainer.sanity_checking:return
            epoch=trainer.current_epoch;metrics={k:float(v.detach().cpu()) if hasattr(v,'detach') else float(v) for k,v in trainer.callback_metrics.items()};path=Path(output)/('native-%04d.pt'%epoch)
            need(not path.exists(),'one original completed epoch state')
            torch.save({'state_dict':pl_module.state_dict(),'optimizer_states':[o.state_dict() for o in trainer.optimizers],'epoch':epoch,'selected_recipe':recipe},path)
            self.records.append({'epoch':epoch,'metrics':metrics,'checkpoint':str(path)})
    records=AllSelectionRecords();trainer=pl.Trainer(max_epochs=recipe['epochs'],accelerator=recipe['accelerator'],devices=1,precision=recipe['precision'],gradient_clip_val=recipe['gradient_clip_val'],callbacks=[records],logger=False,enable_checkpointing=False,enable_progress_bar=False,enable_model_summary=False,deterministic=True,num_sanity_val_steps=0,default_root_dir=str(output))
    trainer.fit(model,train_dataloaders=train_loader,val_dataloaders=validation_loader)
    need(records.records and len(records.records)==recipe['epochs'],'every actual original epoch selection record retained');eligible=[r for r in records.records if recipe['monitor'] in r['metrics'] and __import__('math').isfinite(r['metrics'][recipe['monitor']])]
    need(eligible,'actual qualified full-validation selection, no query fallback');selected=max(eligible,key=lambda r:(r['metrics'][recipe['monitor']],-r['epoch']))
    return {'selected_checkpoint':selected['checkpoint'],'selected_epoch':selected['epoch'],'all_epoch_records':records.records,'original_natural_trainer_completion':True,'historical_parity':False,'query_labels_used_for_P_selection':False}
