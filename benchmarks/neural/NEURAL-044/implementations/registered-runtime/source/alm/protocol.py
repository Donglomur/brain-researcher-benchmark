"""Validate frozen scientific choices before any numerical programme caller."""
from .contracts import require,finite

def prediction(p):
    require(p['window']==[-.5,-.1],'fixed retrospective premovement interval')
    require(type(p['minimum_frames']) is int and p['minimum_frames']>=2,'frame minimum')
    require(finite(p['logistic_c'])==1.0,'fixed reference C=1')
    require(isinstance(p['atlas_bins'],list),'anatomical axis list')
    return p

def perturbation(p):
    require(p['lag_edges']==[i/10 for i in range(11)],'fixed lag bins')
    require(p['distance_edges']==[25.,50.,100.,250.] and p['minimum_distance']==25.,'distance convention')
    require(p['caliper_scale']==.2,'matching convention')
    for key in ('ridge_alpha','response_alpha'):
        require(finite(p[key])==1.0,'fixed ridge parameter=1')
    require(isinstance(p['tuning_window'],list) and len(p['tuning_window'])==2 and
            [finite(v) for v in p['tuning_window']]==[0.0,1.0],'fixed contact tuning window [0,1)')
    require(p['tuning_splits'] and p['artifact_guard'],'actual tuning/artifact producer missing')
    require(type(p['max_design_bytes']) is int and p['max_design_bytes']>0,'native design capacity unissued')
    return p
