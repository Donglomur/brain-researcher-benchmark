"""Closed real rendering routes for admitted original caller records; never guess missing calls."""
import importlib
import os
from pathlib import Path
from .guard import need,Unscorable,capture,strict,bare,encoded
from .array_io import verify_file

def render_bound(session,receipt,protocol,receipts,selected_values,publisher):
    from . import render_inputs
    from .guard import capture_created
    b=session.budget;recipe=strict(capture(session.root,receipt,b))
    need(recipe['schema']=='hundred_models_render_calls_v1','render caller manifest')
    need([x['figure'] for x in recipe['figures']]==list(range(1,23)),'all22 rendering obligations')
    outputs=[]
    # No dynamically named callable or candidate source is imported.
    modules={}
    for name in ('pandas','matplotlib','matplotlib.pyplot','net2brain.evaluations.plotting','repralign.utils.custom_plotting'):
        need(name in session.env['modules'],'complete renderer source closure')
        module=importlib.import_module(name);p=verify_file(session.root,session.env['modules'][name],b)
        need(Path(module.__file__).resolve()==p.resolve(),'renderer module source identity');modules[name]=module
    mpl=modules['matplotlib'];mpl.use('Agg');plt=modules['matplotlib.pyplot'];pd=modules['pandas'];original=modules['repralign.utils.custom_plotting'];Plotting=modules['net2brain.evaluations.plotting'].Plotting
    old=Path.cwd()
    try:
        for call in recipe['figures']:
            b.check();figure=call['figure']
            if not call['historical_caller_resolved']:
                outputs.append({'figure':figure,'status':'required_unscorable','gate':'G12/G13','reason':'Missing original caller/filter/rendering evidence'});continue
            # Figure1 is a conceptual scope obligation; no numerical reference plot is fabricated.
            if figure==1:
                outputs.append({'figure':1,'status':'semantic_scope_record','scope_receipt':call['scope_receipt']});continue
            kind=call['kind'];need(kind in ('best','depth','ranking','continuous'),'closed source rendering route')
            need(call['rows_source']=='complete_native_result_rows' and call['groupby'] in (None,'ModelType','ArchType','ModelTypeFolder'),'source-bound rendering inputs')
            selected=render_inputs.rows(session,protocol,receipts,selected_values,call)
            nulls=render_inputs.nulls(session,receipts,call)
            need({x['Model'] for x in selected}==set(call['models']) and {x['ROI'] for x in selected}==set(call['rois']),'complete caller model/ROI support')
            directory=publisher.root/f'figure_{figure:02}';directory.mkdir(mode=0o700);os.chdir(directory)
            df=pd.DataFrame(selected);plotter=Plotting([pd.DataFrame([x for x in selected if x['Condition']==condition]) for condition in call['conditions']]);before=set(plt.get_fignums());b.charge('write_bytes',call['maximum_output_bytes'])
            if kind=='best':original.bmd_plot_per_roi_group(plotter,normUNC=call['normalize_ceiling'],model_groups=call['groupby'],all_models_null_distribs=nulls if call['include_nulls'] else None)
            elif kind=='depth':original.bmd_plot_all_layers_line_roi_groups(plotter,model_groups=call['groupby'],separate=call['separate'],all_models_null_distribs=nulls if call['include_nulls'] else None)
            elif kind=='ranking':original.bmd_plot_every_model(plotter)
            else:
                need(call['continuous_variable'] in ('ModelFlops','ModelParams','ModelAccuracy'),'declared continuous source field')
                original.plot_against_continuous_variable(df,call['continuous_variable'])
            b.check();figures=set(plt.get_fignums())-before
            for index,fno in enumerate(sorted(figures)):plt.figure(fno).savefig(directory/f'panel_{index:02}.pdf');plt.close(fno)
            extent=sum(p.stat().st_size for p in directory.iterdir() if p.is_file());need(extent<=call['maximum_output_bytes'],'render output bound')
            artifacts=[]
            for p in sorted(directory.iterdir()):
                body,desc=capture_created(directory,p.name,b,cap=call['maximum_output_bytes']);artifacts.append(desc)
            need(bool(artifacts),'original call must produce actual nonempty output')
            outputs.append({'figure':figure,'status':'native_render_unqualified','output_directory':str(directory),'files':artifacts,'output_bytes':extent,'actual_source_call':kind,'historical_parity_proved':False})
    finally:
        os.chdir(old)
        plt.close('all')
    b.check();return outputs
