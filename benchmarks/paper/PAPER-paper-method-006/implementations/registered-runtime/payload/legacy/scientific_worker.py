"""Concrete finite native/source-summary worker; build-only phase never runs it.

Fixed invocation: python -I /opt/k4bench/scientific_worker.py /run/request.json
Immutable image supplies this complete source package. Inputs are strict JSON,
not pickle; author code is authenticated before importing native dependencies.
"""
import importlib.metadata
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import traceback

# -I intentionally removes script directory. The image path is fixed and pinned
# by the host image/environment admission, not controlled by the request.
sys.path.insert(0, '/opt/k4bench')
from native_worker import checked_pin, read_json, check
from k4bench.protocol import canonical, digest
from k4bench.scientific import SOURCE_OPERATIONS, request_contract, REPORTED_LIBRARIES
from k4bench.summaries import dispatch_summary


def encode_native(x):
    """Keep undefined native output explicit rather than JSON NaN or zero."""
    if isinstance(x, dict): return {str(k): encode_native(v) for k,v in x.items()}
    if isinstance(x, (list,tuple)): return [encode_native(v) for v in x]
    if hasattr(x, 'tolist'): return encode_native(x.tolist())
    if type(x) is float and not math.isfinite(x):
        return {'native_nonfinite': 'nan' if math.isnan(x) else ('positive-infinity' if x>0 else 'negative-infinity')}
    if x is None or type(x) in (bool,str,int,float): return x
    raise ValueError('unsupported native output type '+type(x).__name__)


def native_sources(request):
    root=Path('/opt/author');pins=request['source_pins'];paths=set()
    for p in pins:
        checked_pin(p,root);paths.add(p['path'])
    check(len(paths)==len(pins),'duplicate source member')
    check({str(p) for p in root.rglob('*.py')}<=paths,'unlisted native Python')
    check(not any(p.suffix in {'.pyc','.pyo','.so','.pyd','.dylib'} for p in root.rglob('*')),
          'unlisted compiled/cache author module')
    required={'numpy','numba','torch','scipy','tqdm'}
    check(set(request['library_versions'])>=required,'incomplete native environment lock')
    check(all(request['library_versions'][k]==v for k,v in REPORTED_LIBRARIES.items()),
          'reported native package version mismatch')
    if request['operation']=='native_gui_diagnostic_v4_0_2':
        check(request['library_versions'].get('PyQt5')=='5.15.9'
              and request['library_versions'].get('pyqtgraph')=='0.12.0'
              and 'matplotlib' in request['library_versions'],'complete reported GUI environment')
    for name,version in request['library_versions'].items():
        check(importlib.metadata.version(name)==version,'native environment mismatch '+name)
    check(sys.version==request['python_version'],'Python version mismatch')
    check(not any(k=='kilosort' or k.startswith('kilosort.') for k in sys.modules),'author code preloaded')
    sys.path.insert(0,str(root))


def native_operation(request, operands):
    native_sources(request)
    import numpy as np
    check(request['native_dtype'] in {'float32','float64'},'explicit native floating dtype')
    dtype=np.dtype(request['native_dtype'])
    op=request['operation'];bound=request['limits']['max_points']
    def array(name,kind=dtype):
        a=np.asarray(operands[name],dtype=kind)
        check(a.size<=bound,'native input shape cap')
        check(np.isfinite(a).all(),'nonfinite native operand')
        return a
    if op=='native_gui_diagnostic_v4_0_2':
        os.environ['QT_QPA_PLATFORM']='offscreen'
        from PyQt5 import QtWidgets
        import torch
        from kilosort.gui import sanity_plots as plots
        p=request['parameters'];values=operands['gui_operands']
        check(set(p)=={'scene','width','height','settings'},'explicit GUI render settings')
        check(type(p['width']) is int and type(p['height']) is int
              and 1<=p['width']<=8192 and 1<=p['height']<=8192
              and p['width']*p['height']<=bound,'GUI pixel cap')
        check(set(p['settings'])=={'fs','batch_size'} and p['settings']['fs']>0
              and type(p['settings']['batch_size']) is int and p['settings']['batch_size']>0,
              'GUI clock settings')
        def gui_array(name,kind=dtype):
            a=np.asarray(values[name],dtype=kind)
            check(a.size<=bound and np.isfinite(a).all(),'GUI operand bounds')
            return a
        # Conservative source work bound precedes native plotting. Rendering
        # wall/memory limits remain enforced by the surrounding native worker.
        point_sizes=[np.asarray(v).size for v in values.values()]
        check(all(n<=bound for n in point_sizes),'GUI complete input point cap')
        work_bound=p['width']*p['height']+100*sum(point_sizes)
        if p['scene']=='diagnostics':work_bound+=len(values['Wall0'])*len(values['clu0'])
        check(work_bound<=request['limits']['max_work'],'GUI work reservation')
        app=QtWidgets.QApplication([]);window=None;primary=None;cleanup_errors=[];result=None
        try:
            window=plots.PlotWindow(width=p['width'],height=p['height'])
            if p['scene']=='drift-amount':
                check(set(values)=={'dshift'},'GUI drift input roles')
                a=gui_array('dshift');check(a.ndim==2 and a.size>0,'GUI complete drift matrix')
                plots.plot_drift_amount(window,a,p['settings'])
            elif p['scene']=='drift-scatter':
                check(set(values)=={'st0'},'GUI scatter input roles')
                a=gui_array('st0');check(a.ndim==2 and a.shape[1]>=6,'GUI native spike feature schema')
                # Original plot mutates its amplitude column by clipping. The
                # operand file stays immutable; the native array is a copy.
                plots.plot_drift_scatter(window,a,p['settings'])
            elif p['scene']=='diagnostics':
                check(set(values)=={'wPCA','Wall0','clu0'},'GUI diagnostics input roles')
                a=gui_array('wPCA');wall=gui_array('Wall0');clu=gui_array('clu0',np.dtype('int64'))
                check(a.ndim==2 and wall.ndim==3 and clu.ndim==1 and clu.size>0
                      and all(type(x) is int for x in values['clu0'])
                      and int(clu.min())>=0 and int(clu.max())+1==wall.shape[0],
                      'GUI diagnostics native support')
                plots.plot_diagnostics(window,a,torch.from_numpy(wall),clu,p['settings'])
            else:raise ValueError('Unsupported GUI source scene')
            app.processEvents()
            image=window.grab().toImage();path=Path('/output/GUI_DIAGNOSTIC.png')
            check(not path.exists() and image.save(str(path),'PNG'),'GUI PNG export failed')
            size=path.stat().st_size;check(size<=request['limits']['output_bytes'],'GUI image output cap')
            sha=hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda:stream.read(65536),b''):sha.update(block)
            result={'scene':p['scene'],'width':image.width(),'height':image.height(),
                    'image':{'path':'GUI_DIAGNOSTIC.png','bytes':size,'sha256':sha.hexdigest()},
                    'source_functions':'kilosort.gui.sanity_plots',
                    'original_paper_GUI_event_script_reproduced':False}
        except BaseException as error:primary=error
        finally:
            for name,action in [('window-close',None if window is None else window.close),('application-quit',app.quit)]:
                if action is not None:
                    try:action()
                    except BaseException as error:
                        cleanup_errors.append({'operation':name,'type':type(error).__name__,'detail':str(error)})
        if primary is not None:
            primary.native_cleanup_errors=cleanup_errors
            raise primary
        if cleanup_errors:
            error=RuntimeError('GUI cleanup incomplete');error.native_cleanup_errors=cleanup_errors
            raise error
        return result
    if op=='native_ccg_v4_0_2':
        from kilosort import CCG
        a,b=array('spike_train_1'),array('spike_train_2')
        check(a.ndim==b.ndim==1,'CCG vectors required')
        check(a.size*b.size<=request['limits']['max_work'],'CCG worst-case pair work cap')
        p=request['parameters']
        check(set(p)=={'nbins','tbin','acg_threshold','ccg_threshold'},'explicit CCG parameters')
        check(type(p['nbins']) is int and p['nbins']==500,'source quality metrics require 500 bins')
        check(type(p['tbin']) in (int,float) and math.isfinite(p['tbin']) and p['tbin']>0,'CCG bin seconds')
        check(p['acg_threshold']==0.2 and p['ccg_threshold']==0.25,'literal exported CCG thresholds')
        # Empty/zero-duration behavior is the actual selected source outcome;
        # exceptions are retained, never converted into successful quality.
        h,t=CCG.compute_CCG(a,b,tbin=p['tbin'],nbins=p['nbins'])
        q,prob,baseline=CCG.CCG_metrics(a,b,h,t,nbins=p['nbins'],tbin=p['tbin'])
        return {'histogram':h,'duration_seconds':t,'Q12_contamination':q,
                'R12_probability':prob,'R00_baseline':baseline,
                'autocorrelation_refractory':bool(q<0.2 and prob<0.2),
                'cross_correlation_refractory':bool(q<0.25 and prob<0.05),
                'spike_counts':[int(a.size),int(b.size)],'central_bin_restored':True}
    if op=='native_bimodality_v4_0_2':
        from kilosort.swarmsplitter import bimod_score
        a=array('projection');check(a.ndim==1,'projection vector')
        check(a.size+400*400<=request['limits']['max_work'],'bimodality work cap')
        check(request['parameters']=={},'no native histogram override')
        return {'score':bimod_score(a),'input_count':int(a.size),'histogram_edges':400,'histogram_bins':399}
    if op=='native_split_projection_v4_0_2':
        from kilosort.swarmsplitter import check_split
        a=array('features');tree=array('tree',np.dtype('int64'));labels=array('cluster_labels',np.dtype('int64'))
        memberships=operands['cluster_membership']
        check(a.ndim==2 and a.shape[1]>0 and tree.ndim==2 and tree.shape[1]==3 and labels.ndim==1
              and a.shape[0]==labels.size,'native regression input shapes')
        # Require integral source identifiers before integer conversion.
        check(all(type(v) is int for row in operands['tree'] for v in row)
              and all(type(v) is int for v in operands['cluster_labels']), 'fractional native label')
        check(all(isinstance(row,list) and all(type(v) is int for v in row) for row in memberships),
              'cluster membership schema')
        check(len(memberships)<=bound and sum(map(len,memberships))<=bound,'membership size')
        check(np.all(tree>=0) and np.all(tree<len(memberships)),'tree membership index')
        kk=request['parameters']['tree_row'];check(type(kk) is int and 0<=kk<len(tree),'selected merge row')
        check(set(request['parameters'])=={'tree_row'},'no native regression policy override')
        n,f=a.shape
        check(n*f*f+f*f*f+400*400<=request['limits']['max_work'],'regression work cap')
        # Actual pinned function performs feature replacement, weights, ridge,
        # linear solve, projection and native float32 smoothed histogram.
        projection,score=check_split(a,kk,tree,labels,memberships)
        return {'projection':projection,'score':score,'projection_count':len(projection),
                'tree_row':kk,'features':f,'literal_last_feature_replaced':True,'ridge':0.01}
    raise ValueError('no registered native operation')


def run(request):
    request_contract(request)
    operands={}
    for role,entry in request['inputs'].items():
        checked_pin(entry['pin'],Path('/input'))
        operands[role]=read_json(Path(entry['pin']['path']),request['limits']['input_bytes'])
    if request['operation'] in SOURCE_OPERATIONS:
        result=encode_native(native_operation(request,operands))
    else:
        result=dispatch_summary(request,operands)
    out={'schema':'kilosort4_scientific_output_v3','operation':request['operation'],
         'request_digest':digest(request),'execution_context':request['execution_context'],
         'support_digest':request['support_digest'],'numerical_scope':request['numerical_scope'],
         'definition_digest':digest(request['definition']),
         'input_pins':{k:v['pin'] for k,v in request['inputs'].items()},
         'result':result,'historical_parity':False,'scientific_pass':None}
    body=canonical(out)+b'\n'
    auxiliary_bytes=result['image']['bytes'] if request['operation']=='native_gui_diagnostic_v4_0_2' else 0
    check(len(body)+auxiliary_bytes<=request['limits']['output_bytes'],'full constructor output cap; no prefix success')
    with Path('/output/SCIENTIFIC_OUTPUT.json').open('xb') as stream: stream.write(body)


def main():
    request=None
    try:
        check(sys.argv[1:]==['/run/request.json'],'fixed request path')
        request=read_json(Path('/run/request.json'),4*1024*1024)
        run(request)
    except BaseException as error:
        failure={'schema':'kilosort4_scientific_failure_v3','status':'failed',
                 'request_digest':None if request is None else digest(request),
                 'type':type(error).__name__,'detail':str(error),
                 'native_cleanup_errors':getattr(error,'native_cleanup_errors',[]),
                 'traceback':traceback.format_exc()[-32768:],'no_retry':True,'scientific_pass':None}
        try:
            with Path('/output/SCIENTIFIC_FAILURE.json').open('xb') as stream:
                stream.write(canonical(failure)+b'\n')
        except BaseException as custody:
            print(json.dumps({'original_failure':failure,'failure_receipt_error':str(custody)}),file=sys.stderr)
        raise


if __name__=='__main__':main()
