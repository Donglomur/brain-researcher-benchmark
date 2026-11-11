"""Full logical extents and actual call accounting; not a physical-memory claim."""
from .constants import MODELS,MAX_UPDATES,LINE_ATTEMPTS

def session_plan(nfit,nval,nquery,units,categories):
    for x in (nfit,nval,nquery,units,categories):
        if type(x)is not int or x<=0:raise ValueError('positive complete dimensions')
    if categories>nfit:raise ValueError('FIT vocabulary cannot exceed FIT rows')
    n=nfit+nval+nquery;p=1+categories+16;train=nfit+nval
    # Arrays are explicit array('d')/'q' buffers. No BLAS/LAPACK/NumPy solver,
    # diagonal(mu), broadcasted N*p temporary or implicit inverse is used.
    extents={
      'training_count_capture_int64':train*units,
      'private_query_count_capture_int64':nquery*units,
      'full_design_float64':n*p,
      'hessian_float64':p*p,
      'cholesky_float64':p*p,
      'gradient_float64':p,'beta_float64':p,'direction_float64':p,'trial_beta_float64':p,
      'train_eta_float64':train,'train_mu_float64':train,
      'reference_predictions_float64':len(MODELS)*nquery*units,
      'candidate_predictions_float64':nquery*units,
      'frozen_prediction_readback_float64':6*nquery*units,
      'freeze_serialization_payload':6*nquery*units,
      'reference_refit_coefficients_float64':units*(17+(1+categories)+(17+categories)+2*(5+categories)),
      'all_grid_coefficients_float64':9*units*(17+(1+categories)+(17+categories)+2*(5+categories)),
      'grid_freeze_readback_float64':9*units*(17+(1+categories)+(17+categories)+2*(5+categories)),
      'grid_serialization_payload':9*units*(17+(1+categories)+(17+categories)+2*(5+categories)),
      'mean_deviances_float64':6*units}
    # Raw error objects can retain Python traceback frames and their buffers.
    # Include all50 fits' buffers and all20 designs conservatively; never
    # assume successful deallocation while retaining original exceptions.
    extents.update({
      'retained_fit_workspace_float64':50*units*(2*p*p+4*p+2*train),
      'retained_stage_designs_float64':20*n*p,
      'unit_gains_float64':6*units,
      'area_summary_float64':6*6,
      'pair_summary_float64':6*30})
    # Conservative simultaneous payload includes phases that are actually
    # disjoint; it must never be reduced because a preceding fit failed.
    fits=50*units
    return {'shape':{'FIT':nfit,'VALIDATION':nval,'QUERY':nquery,'units':units,'categories':categories},
      'array_elements':extents,'logical_array_payload_bytes':8*sum(extents.values()),
      'required_fit_dispositions':fits,'grid_fits':45*units,'refits':5*units,
      'full_design_constructions':20,'training_capture_passes':3,
      'fit_objective_calls_max':fits*(1+MAX_UPDATES*LINE_ATTEMPTS),
      'gradient_hessian_calls_max':fits*(MAX_UPDATES+1),
      'cholesky_solves_max':fits*MAX_UPDATES,
      'validation_deviance_calls':45*units,'query_predict_calls':5*units,
      'private_query_deviance_calls':6*units,
      'maximum_nonfinite_line_search_failure_occurrences':fits*MAX_UPDATES*LINE_ATTEMPTS,
      'fixed_fit_slot_records':fits,
      'maximum_fit_validation_prediction_failure_occurrences':fits+45*units+5*units,
      'per_unit_matched_pair_memberships_bound':15*units,
      'max_objective_rows':train,'max_predict_rows':max(nval,nquery),
      'conservative_scalar_arithmetic_bound':fits*((1+MAX_UPDATES*LINE_ATTEMPTS)*train*(2*p+8)+(MAX_UPDATES+1)*train*(2*p*p+4*p)+MAX_UPDATES*(4*p*p*p+8*p*p))+45*units*nval*(2*p+12)+5*units*nquery*(2*p+4)+6*units*nquery*12,
      'library_workspace':'No BLAS/LAPACK workspace. CPython math.exp/log and array allocation/metadata/allocator overhead require separately source-bound host admission.',
      'required_external_byte_bounds':('python_metadata','allocator_and_scalar_overhead','decoder_peak','io_buffers','writer_buffers','all_fit_logs_and_errors','complete_outputs'),
      'physical_memory_qualified':False}

class Calls:
    """No deduplication: each attempted evaluation increments before its body."""
    def __init__(self):self.counts={};self.failures=[]
    def enter(self,name):self.counts[name]=self.counts.get(name,0)+1
    def failure(self,where,error):self.failures.append({'where':where,'error':error})

class Attempt:
    """Raw first plus ordered independent cleanup occurrences, including same object."""
    def __init__(self):self.first=None;self.events=[];self.calls=Calls();self.completed=False
    def fail(self,where,error):
        self.events.append({'where':where,'error':error})
        if self.first is None:self.first=error
    def cleanup(self,where,callback):
        try:callback()
        except BaseException as error:self.fail(where,error)
    def finish(self):
        if self.first is not None:raise self.first
        self.completed=True
