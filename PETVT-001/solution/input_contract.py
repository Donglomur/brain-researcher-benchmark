"""Explicit, source-documented arterial activity decay footing."""
import numpy as np

def parent_input(plasma,parent,times_min,footing,decay_lambda):
    if footing not in {"pet_time_zero","draw_time"}:
        raise ValueError("failed_precondition: blood activity decay footing is unresolved")
    activity=np.asarray(plasma,float)*np.asarray(parent,float)
    if footing=="draw_time":activity=activity*np.exp(decay_lambda*np.asarray(times_min,float))
    return activity
