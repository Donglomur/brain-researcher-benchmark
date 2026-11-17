"""Typed boundaries consumed by the fixed scientific caller.

These interfaces describe callbacks consumed by programme.py. Implementing an
ABC, returning a dictionary or naming a SHA does not authenticate anything:
The prospective host092 operator implements these boundaries through original
Linux ownership. An ABC, dictionary or matching digest still grants no authority.
"""
from abc import ABC,abstractmethod

class TrainingCapture(ABC):
    @property
    @abstractmethod
    def metadata(self):pass
    @property
    @abstractmethod
    def fit_counts(self):pass
    @property
    @abstractmethod
    def validation_counts(self):pass
    @abstractmethod
    def close(self):pass

class QueryCapture(ABC):
    @property
    @abstractmethod
    def counts(self):pass
    @abstractmethod
    def close(self):pass

class FrozenPredictions(ABC):
    @abstractmethod
    def read_reference(self,session_id):pass
    @abstractmethod
    def read_candidate(self,session_id):pass
    @abstractmethod
    def close(self):pass

class NativeHost(ABC):
    """Host interface with original source/cohort/axis/method joins.

    All dimensions are full, before buffer or decoder acquisition. Admission
    must bound exact CPython/interpreter/array overhead, complete captured
    metadata/strings/rows, all failed-evaluation records, native decoding,
    serialized outputs, candidate costs and immutable readback, in addition to
    the explicit algorithm's payload. No abstract estimator qualifies memory.
    """
    @abstractmethod
    def describe_complete_panel(self):pass
    @abstractmethod
    def admit_full_resources(self,plans):pass
    @abstractmethod
    def capture_original_index(self):pass
    @abstractmethod
    def freeze_design_and_issue_prediction_view(self,descriptor_projection):pass
    @abstractmethod
    def open_training(self,session_id):pass
    @abstractmethod
    def retain_reference_dispositions(self,session_id,reference,calls):pass
    @abstractmethod
    def freeze_fit_grid(self,references):pass
    @abstractmethod
    def record_validation_and_freeze_selection(self,references):pass
    @abstractmethod
    def freeze_refit_models(self,references):pass
    @abstractmethod
    def capture_complete_candidate_predictions(self,metadata):pass
    @abstractmethod
    def freeze_and_readback_all_predictions(self,references,candidates):pass
    @abstractmethod
    def open_private_query(self,frozen,session_id):pass
    @abstractmethod
    def publish_private_scores(self,frozen,result,attempt):pass
    @abstractmethod
    def release_observed_query_and_execute_original_investigation(self,frozen):pass
    @abstractmethod
    def export_phase_claim(self):pass
    @abstractmethod
    def retain_terminal_attempt(self,attempt):pass
