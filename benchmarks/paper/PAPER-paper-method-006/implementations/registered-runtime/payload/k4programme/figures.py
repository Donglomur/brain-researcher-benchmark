"""Actual selected-panel rendering, not invented historical panel definitions."""
from .common import Owner,require


def render_panel(series,*,definition,obligation_id,artifacts):
    # Coordinates, units, plotted support and layout are required. No auto-crop,
    # hidden percentile/binning, invented embedding, or zero-filled missing panel.
    require(definition['historical_definition_verified'] is False,
            'local-renderer-cannot-certify-history')
    require(definition['obligation_id']==obligation_id and definition['source_definition_pin'],
            'panel-definition-join')
    required={'kind','x_label','y_label','title','limits','size_inches','dpi','series_ids',
              'obligation_id','source_definition_pin','historical_definition_verified'}
    require(set(definition)==required,'complete-explicit-panel-definition')
    require(definition['kind'] in {'lines','scatter','image'},'missing-panel-renderer')
    require(set(series)==set(definition['series_ids']) and bool(series),'complete-panel-series')
    require(len(definition['limits'])==2 and all(len(a)==2 and a[0]<a[1] for a in definition['limits']),
            'panel-limits-required')
    require(len(definition['size_inches'])==2 and all(x>0 for x in definition['size_inches'])
            and type(definition['dpi']) is int and definition['dpi']>0,'panel-size-required')
    import numpy as np
    import matplotlib
    matplotlib.use('Agg',force=True)
    import matplotlib.pyplot as plt
    import io
    local=Owner();figure=None;buffer=None;body=None
    try:
        figure,ax=plt.subplots(figsize=definition['size_inches'],dpi=definition['dpi'])
        for name in definition['series_ids']:
            row=series[name];kind=definition['kind']
            if kind=='image':
                data=np.asarray(row['values'])
                require(data.ndim==2 and data.size>0 and np.all(np.isfinite(data)), 'image-support')
                require(row['vmin']<row['vmax'] and row['origin'] in {'upper','lower'},'image-scale')
                ax.imshow(data,extent=row['extent'],origin=row['origin'],vmin=row['vmin'],vmax=row['vmax'],
                          cmap=row['colormap'],interpolation='nearest',aspect=row['aspect'])
            else:
                x=np.asarray(row['x']);y=np.asarray(row['y'])
                require(x.ndim==y.ndim==1 and x.shape==y.shape and x.size>0
                        and np.all(np.isfinite(x)) and np.all(np.isfinite(y)), 'plotted-coordinate-support')
                require(len(row['support_ids'])==len(x),'plotted-support-identity')
                if kind=='lines':ax.plot(x,y,label=name,color=row['color'],linewidth=row['width'])
                else:ax.scatter(x,y,label=name,c=row['color'],s=row['size'])
        ax.set(xlabel=definition['x_label'],ylabel=definition['y_label'],title=definition['title'],
               xlim=definition['limits'][0],ylim=definition['limits'][1])
        buffer=io.BytesIO();figure.savefig(buffer,format='png',dpi=definition['dpi']);body=buffer.getvalue()
        artifacts.budget.charge('array',len(body))
    except BaseException as error:local.catch('panel-render',error)
    finally:
        if buffer is not None:local.close('panel-buffer-close',buffer)
        if figure is not None:
            try:plt.close(figure)
            except BaseException as error:local.catch('panel-figure-close',error)
    artifacts.owner.relay(local)
    return {'image':artifacts.write('PANEL.png',body),'obligation_id':obligation_id,
            'definition':definition,'historical_parity':False,'protected_validation':None}
