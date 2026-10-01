import importlib.util
from pathlib import Path
import numpy as np


def test_partition_removes_diagonal(monkeypatch):
    p=Path(__file__).parents[1]/"solution/partition_contract.py"
    spec=importlib.util.spec_from_file_location("partition_contract",p)
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    class Recorder:
        def __init__(self,**kwargs):
            assert kwargs=={"n_clusters":7,"n_init":10,"random_state":0}
        def fit(self,features):
            assert np.all(np.diag(features)==0)
            self.labels_=np.arange(len(features))%7
            return self
    monkeypatch.setattr(m,"KMeans",Recorder)
    source=np.eye(8)*99
    assert len(m.age_blind_partition(source))==8
    assert np.all(np.diag(source)==99)
