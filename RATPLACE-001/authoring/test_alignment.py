import importlib.util
from pathlib import Path
import numpy as np

spec=importlib.util.spec_from_file_location("alignment",Path(__file__).resolve().parents[1]/"solution/alignment.py")
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)

def test_gap_spike_is_not_snapped_to_running_time():
    times=np.array([0.,1.,10.,11.])
    assert a.sample_indices(times,[.2,5.,10.2],[True]*4,1.).tolist()==[0,2]

def test_stationary_samples_are_excluded_before_binning():
    assert a.sample_indices([0.,1.,2.],[.1,1.1,2.1],[True,False,True],1.).tolist()==[0,2]

def test_elapsed_shift_stays_in_own_epoch():
    result=a.shifted_spikes([1.,101.],[(0.,60.),(100.,160.)],np.random.default_rng(0),20.)
    assert 0<=result[0]<60 and 100<=result[1]<160
    assert 20<=result[0]-1<=40
